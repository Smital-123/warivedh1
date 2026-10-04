import os
import sys
import django

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from rest_framework.test import APIClient
from apps.users.models import User
from apps.routes.models import BlockedRoad, RouteClosure
from apps.operations.models import VolunteerProfile, VolunteerApplication, Task
from apps.notifications.models import Notification

def run_tests():
    print("========================================")
    print("WARIVEDH E2E INTEGRATION VERIFICATION")
    print("========================================")

    client = APIClient()

    # 1. Verify Active Blocked Roads
    print("\n--- 1. Testing Blocked Roads Endpoint ---")
    res = client.get("/api/roads/blocked/?status=ACTIVE")
    assert res.status_code == 200, f"Blocked roads failed: {res.status_code}"
    blocked_data = res.json()
    print(f"Active Blocked Roads Returned: {len(blocked_data)}")
    for r in blocked_data:
        print(f"  - [{r['id']}] {r['road_name']}: ({r['start_latitude']}, {r['start_longitude']}) -> ({r['end_latitude']}, {r['end_longitude']}) [Active: {r['is_active']}, Status: {r['status']}]")
    assert len(blocked_data) >= 2, "Expected at least 2 active blocked roads"

    # 2. Verify Route Calculation with Blocked Detection & Safe Detour
    print("\n--- 2. Testing Route Calculation (Pune -> Saswad) ---")
    calc_res = client.get("/api/roads/calculate/?start=Pune&destination=Saswad")
    assert calc_res.status_code == 200, f"Route calc failed: {calc_res.status_code}"
    route_json = calc_res.json()
    print(f"Route blocked detected: {route_json.get('route_blocked')}")
    print(f"Message: {route_json.get('message')}")
    print(f"Alternative Detours Found: {len(route_json.get('alternative_routes', []))}")
    assert route_json.get("route_blocked") == True, "Expected route to be detected as blocked"
    assert len(route_json.get("alternative_routes", [])) > 0, "Expected at least 1 safe detour"

    # 3. Create Admin and Volunteer Users for Flow Testing
    print("\n--- 3. Testing Volunteer Registration & Admin Approval ---")
    admin_user, _ = User.objects.get_or_create(username="admin_e2e", defaults={"email": "admin_e2e@warivedh.com", "role": "ADMIN", "is_staff": True})
    
    vol_app, _ = VolunteerApplication.objects.get_or_create(
        email="test_volunteer@wari.org",
        defaults={
            "full_name": "Ramesh Patil",
            "mobile_number": "9876543210",
            "age": 28,
            "preferred_duty_area": "Dive Ghat, Saswad",
            "skills": ["First Aid", "Crowd Control"],
            "preferred_purpose": "CROWD_MANAGEMENT",
            "status": "PENDING",
        }
    )

    # Approve via API
    client.force_authenticate(user=admin_user)
    review_res = client.post(
        f"/api/admin/volunteer-applications/{vol_app.application_id}/review/",
        {"decision": "APPROVED", "review_note": "Verified credentials"}
    )
    assert review_res.status_code == 200, f"Approval failed: {review_res.status_code}"
    
    vol_user = User.objects.get(email="test_volunteer@wari.org")
    assert vol_user.role == "VOLUNTEER", f"Expected user role VOLUNTEER, got {vol_user.role}"
    vol_profile = VolunteerProfile.objects.get(user=vol_user)
    print(f"Volunteer Profile Created: {vol_profile} (Status: {vol_profile.status})")

    # 4. Create Task and Assign to Volunteer
    print("\n--- 4. Testing Task Creation & Assignment to Volunteer ---")
    task_res = client.post(
        "/api/admin/tasks/",
        {
            "title": "Emergency Crowd Management at Dive Ghat",
            "description": "Assist pilgrims walking uphill and guide traffic away from blocked sections.",
            "purpose": "CROWD_MANAGEMENT",
            "priority": "HIGH",
            "location": "Dive Ghat Top Checkpoint",
            "assigned_volunteer": vol_profile.id,
        }
    )
    assert task_res.status_code == 201, f"Task creation failed: {task_res.status_code}"
    created_task = task_res.json()
    task_id = created_task["id"]
    print(f"Task Created & Assigned: #{created_task['task_id']} '{created_task['title']}' to {created_task['assigned_volunteer_name']}")

    # 5. Verify Notification was Generated for Volunteer
    print("\n--- 5. Testing Volunteer Notification Dispatch ---")
    notif = Notification.objects.filter(recipient=vol_user).first()
    assert notif is not None, "Expected notification to be created for volunteer"
    print(f"Notification Found in DB: [{notif.notification_type}] '{notif.title}' - '{notif.message}' (is_read={notif.is_read})")

    # 6. Volunteer logs in and views their tasks
    print("\n--- 6. Testing Volunteer Self Task Endpoints ---")
    client.force_authenticate(user=vol_user)
    my_tasks_res = client.get("/api/operations/volunteer/my-tasks/")
    assert my_tasks_res.status_code == 200, f"My tasks failed: {my_tasks_res.status_code}"
    my_tasks = my_tasks_res.json()
    print(f"Volunteer sees active tasks: {len(my_tasks)}")
    assert any(t["id"] == task_id for t in my_tasks), "Assigned task not found in volunteer task list"

    # 7. Volunteer accepts and starts task
    accept_res = client.post(f"/api/operations/volunteer/tasks/{task_id}/action/", {"action": "ACCEPT"})
    assert accept_res.status_code == 200, f"Accept failed: {accept_res.status_code}"
    print(f"Task status after ACCEPT: {accept_res.json().get('task_status')}")

    # 8. Volunteer marks task as COMPLETED with completion note
    complete_res = client.post(
        f"/api/operations/volunteer/tasks/{task_id}/action/",
        {"action": "COMPLETE", "completion_note": "Crowd safely directed and water distributed to 300 pilgrims."}
    )
    assert complete_res.status_code == 200, f"Complete failed: {complete_res.status_code}"
    print(f"Task status after COMPLETE: {complete_res.json().get('task_status')}")
    print(f"Volunteer Status after COMPLETE: {complete_res.json().get('volunteer_status')}")

    print("\n========================================")
    print("ALL E2E INTEGRATION TESTS PASSED SUCCESSFULLY! ✓")
    print("========================================")

if __name__ == "__main__":
    run_tests()
