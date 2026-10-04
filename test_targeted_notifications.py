import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from rest_framework.test import APIClient
from apps.users.models import User
from apps.operations.models import VolunteerProfile, Task, VolunteerPurpose
from apps.notifications.models import Notification

def run_tests():
    print("==================================================")
    print("WARIVEDH TARGETED NOTIFICATION & TASK ASSIGNMENT TESTS")
    print("==================================================")

    # 1. Setup Admin
    admin_user = User.objects.filter(role__in=["ADMIN", "STAFF"]).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(
            email="admin@warivedh.com",
            username="admin",
            password="adminpassword123",
            role="ADMIN"
        )
    print(f"[OK] Admin User: {admin_user.email}")

    # 2. Setup 3 Volunteers (Volunteer A, Volunteer B, Volunteer C)
    volunteers_data = [
        {"email": "volunteer_a@warivedh.com", "username": "volunteer_a", "name": "Volunteer A", "location": "Alandi"},
        {"email": "volunteer_b@warivedh.com", "username": "volunteer_b", "name": "Volunteer B", "location": "Saswad"},
        {"email": "volunteer_c@warivedh.com", "username": "volunteer_c", "name": "Volunteer C", "location": "Jejuri"},
    ]

    vol_users = []
    vol_profiles = []
    vol_clients = []

    for v in volunteers_data:
        first, last = v["name"].split(" ", 1)
        user, _ = User.objects.get_or_create(
            email=v["email"],
            defaults={"username": v["username"], "first_name": first, "last_name": last, "role": "VOLUNTEER"}
        )
        user.first_name = first
        user.last_name = last
        user.set_password("password123")
        user.save()

        profile, _ = VolunteerProfile.objects.get_or_create(
            user=user,
            defaults={"status": "AVAILABLE", "preferred_location": v["location"], "purposes": ["GENERAL_HELP"]}
        )

        client = APIClient()
        client.force_authenticate(user=user)

        vol_users.append(user)
        vol_profiles.append(profile)
        vol_clients.append(client)
        print(f"[OK] Setup Volunteer: {v['name']} ({user.email}, Profile ID: {profile.id})")

    admin_client = APIClient()
    admin_client.force_authenticate(user=admin_user)

    # Clear previous notifications for these test users for clean assertion
    for u in vol_users:
        Notification.objects.filter(recipient=u).delete()
    print("[OK] Test volunteer notification inboxes cleared for clean isolation testing.")

    # 3. Create and assign:
    # Task 1 -> Volunteer A (via direct assignment on create)
    # Task 2 -> Volunteer B (via TaskAssignView endpoint)
    # Task 3 -> Volunteer C (via direct assignment on create)
    print("\n--- STEP 1: Assigning Task 1 -> Vol A, Task 2 -> Vol B, Task 3 -> Vol C ---")
    
    # Task 1: Direct assignment on create
    t1_res = admin_client.post("/api/operations/tasks/", {
        "title": "Crowd Management at Alandi Ghat",
        "description": "Ensure queue discipline near temple entrance.",
        "purpose": "CROWD_MANAGEMENT",
        "priority": "HIGH",
        "location": "Alandi",
        "assigned_volunteer": vol_profiles[0].id
    }, format="json")
    assert t1_res.status_code == 201, f"Failed to create Task 1: {t1_res.json()}"
    t1_id = t1_res.json()["task_id"]
    print(f"[OK] Task 1 ({t1_id}) assigned directly to {volunteers_data[0]['name']}")

    # Task 2: Create first, then assign via /api/operations/tasks/<id>/assign/
    t2_create_res = admin_client.post("/api/operations/tasks/", {
        "title": "Water Distribution at Saswad Palkhi Ground",
        "description": "Distribute clean water bottles to warkaris.",
        "purpose": "WATER_DISTRIBUTION",
        "priority": "MEDIUM",
        "location": "Saswad",
    }, format="json")
    assert t2_create_res.status_code == 201
    t2_pk = t2_create_res.json()["id"]
    t2_id = t2_create_res.json()["task_id"]

    t2_assign_res = admin_client.post(f"/api/operations/tasks/{t2_pk}/assign/", {
        "volunteer_id": vol_profiles[1].id
    }, format="json")
    assert t2_assign_res.status_code == 200, f"Failed to assign Task 2: {t2_assign_res.json()}"
    print(f"[OK] Task 2 ({t2_id}) assigned via TaskAssignView to {volunteers_data[1]['name']}")

    # Task 3: Direct assignment on create
    t3_res = admin_client.post("/api/operations/tasks/", {
        "title": "Medical First Aid Support at Jejuri",
        "description": "Assist medical team at first-aid tent.",
        "purpose": "FIRST_AID",
        "priority": "HIGH",
        "location": "Jejuri",
        "assigned_volunteer": vol_profiles[2].id
    }, format="json")
    assert t3_res.status_code == 201, f"Failed to create Task 3: {t3_res.json()}"
    t3_id = t3_res.json()["task_id"]
    print(f"[OK] Task 3 ({t3_id}) assigned directly to {volunteers_data[2]['name']}")

    # 4. Verify inboxes for Vol A, Vol B, Vol C via API (/api/notifications/)
    print("\n--- STEP 2: Verifying API Response Isolation for Volunteers A, B, C ---")
    
    # Volunteer A API check
    notifs_a = vol_clients[0].get("/api/notifications/").json()
    titles_a = [n["title"] for n in notifs_a if n["notification_type"] == "TASK_ASSIGNED"]
    print(f"Volunteer A Notifications count: {len(titles_a)}")
    assert any("Crowd Management" in t for t in titles_a), "Volunteer A must have Task 1"
    assert not any("Water Distribution" in t for t in titles_a), "Volunteer A must NOT have Task 2"
    assert not any("Medical First Aid" in t for t in titles_a), "Volunteer A must NOT have Task 3"
    print("  [PASS] Volunteer A received ONLY Task 1 notification!")

    # Volunteer B API check
    notifs_b = vol_clients[1].get("/api/notifications/").json()
    titles_b = [n["title"] for n in notifs_b if n["notification_type"] == "TASK_ASSIGNED"]
    print(f"Volunteer B Notifications count: {len(titles_b)}")
    assert not any("Crowd Management" in t for t in titles_b), "Volunteer B must NOT have Task 1"
    assert any("Water Distribution" in t for t in titles_b), "Volunteer B must have Task 2"
    assert not any("Medical First Aid" in t for t in titles_b), "Volunteer B must NOT have Task 3"
    print("  [PASS] Volunteer B received ONLY Task 2 notification!")

    # Volunteer C API check
    notifs_c = vol_clients[2].get("/api/notifications/").json()
    titles_c = [n["title"] for n in notifs_c if n["notification_type"] == "TASK_ASSIGNED"]
    print(f"Volunteer C Notifications count: {len(titles_c)}")
    assert not any("Crowd Management" in t for t in titles_c), "Volunteer C must NOT have Task 1"
    assert not any("Water Distribution" in t for t in titles_c), "Volunteer C must NOT have Task 2"
    assert any("Medical First Aid" in t for t in titles_c), "Volunteer C must have Task 3"
    print("  [PASS] Volunteer C received ONLY Task 3 notification!")

    # 5. Step 3: Assign Task 4 -> Volunteer A
    print("\n--- STEP 3: Assigning Task 4 -> Volunteer A ---")
    t4_res = admin_client.post("/api/operations/tasks/", {
        "title": "Route Guidance at Dive Ghat",
        "description": "Guide elderly warkaris along slope.",
        "purpose": "ROUTE_GUIDANCE",
        "priority": "HIGH",
        "location": "Dive Ghat",
        "assigned_volunteer": vol_profiles[0].id
    }, format="json")
    assert t4_res.status_code == 201
    t4_id = t4_res.json()["task_id"]
    print(f"[OK] Task 4 ({t4_id}) assigned to Volunteer A")

    # 6. Step 4: Verify inboxes again
    print("\n--- STEP 4: Verifying Inboxes after Task 4 Assignment ---")
    
    # Volunteer A
    notifs_a = vol_clients[0].get("/api/notifications/").json()
    titles_a = [n["title"] for n in notifs_a if n["notification_type"] == "TASK_ASSIGNED"]
    print(f"Volunteer A Notifications count: {len(titles_a)}")
    assert any("Crowd Management" in t for t in titles_a), "Volunteer A must have Task 1"
    assert any("Route Guidance" in t for t in titles_a), "Volunteer A must have Task 4"
    assert not any("Water Distribution" in t for t in titles_a), "Volunteer A must NOT have Task 2"
    assert not any("Medical First Aid" in t for t in titles_a), "Volunteer A must NOT have Task 3"
    print("  [PASS] Volunteer A has Task 1 AND Task 4 notifications!")

    # Volunteer B
    notifs_b = vol_clients[1].get("/api/notifications/").json()
    titles_b = [n["title"] for n in notifs_b if n["notification_type"] == "TASK_ASSIGNED"]
    print(f"Volunteer B Notifications count: {len(titles_b)}")
    assert not any("Crowd Management" in t for t in titles_b), "Volunteer B must NOT have Task 1"
    assert not any("Route Guidance" in t for t in titles_b), "Volunteer B must NOT have Task 4"
    assert any("Water Distribution" in t for t in titles_b), "Volunteer B must have Task 2"
    assert not any("Medical First Aid" in t for t in titles_b), "Volunteer B must NOT have Task 3"
    print("  [PASS] Volunteer B has ONLY Task 2 notification (No Task 1, 3, or 4)!")

    # Volunteer C
    notifs_c = vol_clients[2].get("/api/notifications/").json()
    titles_c = [n["title"] for n in notifs_c if n["notification_type"] == "TASK_ASSIGNED"]
    print(f"Volunteer C Notifications count: {len(titles_c)}")
    assert not any("Crowd Management" in t for t in titles_c), "Volunteer C must NOT have Task 1"
    assert not any("Route Guidance" in t for t in titles_c), "Volunteer C must NOT have Task 4"
    assert not any("Water Distribution" in t for t in titles_c), "Volunteer C must NOT have Task 2"
    assert any("Medical First Aid" in t for t in titles_c), "Volunteer C must have Task 3"
    print("  [PASS] Volunteer C has ONLY Task 3 notification (No Task 1, 2, or 4)!")

    # 7. Check Self Tasks Feed Isolation (/api/operations/volunteer/my-tasks/)
    print("\n--- STEP 5: Verifying Volunteer Task Feed Isolation (/api/operations/volunteer/my-tasks/) ---")
    tasks_feed_a = vol_clients[0].get("/api/operations/volunteer/my-tasks/").json()
    tasks_feed_b = vol_clients[1].get("/api/operations/volunteer/my-tasks/").json()
    tasks_feed_c = vol_clients[2].get("/api/operations/volunteer/my-tasks/").json()

    assert all(t["assigned_volunteer_name"] == "Volunteer A" for t in tasks_feed_a if t.get("assigned_volunteer_name")), "Feed A isolated"
    assert all(t["assigned_volunteer_name"] == "Volunteer B" for t in tasks_feed_b if t.get("assigned_volunteer_name")), "Feed B isolated"
    assert all(t["assigned_volunteer_name"] == "Volunteer C" for t in tasks_feed_c if t.get("assigned_volunteer_name")), "Feed C isolated"
    print(f"  [PASS] Volunteer A Task Feed count: {len(tasks_feed_a)} (All assigned to Vol A)")
    print(f"  [PASS] Volunteer B Task Feed count: {len(tasks_feed_b)} (All assigned to Vol B)")
    print(f"  [PASS] Volunteer C Task Feed count: {len(tasks_feed_c)} (All assigned to Vol C)")

    print("\n==================================================")
    print("ALL TARGETED NOTIFICATION ISOLATION TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
