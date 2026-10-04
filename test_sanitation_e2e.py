import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from decimal import Decimal
from rest_framework.test import APIClient
from apps.users.models import User
from apps.operations.models import VolunteerProfile, Task
from apps.sanitation.models import SanitationReport
from apps.notifications.models import Notification

def run_tests():
    print("==================================================")
    print("WARIVEDH SANITATION & WASTE MANAGEMENT E2E TESTS")
    print("==================================================")

    # 1. Setup API Clients for Admin and Volunteer
    admin_user = User.objects.filter(role__in=["ADMIN", "STAFF"]).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(
            email="admin@warivedh.com",
            username="admin",
            password="adminpassword123",
            role="ADMIN"
        )
    print(f"[OK] Using Admin: {admin_user.email} (Role: {admin_user.role})")

    volunteer_user = User.objects.filter(role="VOLUNTEER").first()
    if not volunteer_user:
        volunteer_user = User.objects.create_user(
            email="volunteer_san@warivedh.com",
            username="volunteer_san",
            password="volunteerpassword123",
            role="VOLUNTEER"
        )
    vol_profile, _ = VolunteerProfile.objects.get_or_create(
        user=volunteer_user,
        defaults={"status": "AVAILABLE", "preferred_location": "Saswad Route"}
    )
    print(f"[OK] Using Volunteer: {volunteer_user.email} (ID: {vol_profile.id})")

    public_client = APIClient()
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin_user)
    volunteer_client = APIClient()
    volunteer_client.force_authenticate(user=volunteer_user)

    # 2. Test: Civilian submits sanitation report (Public, no auth)
    print("\n--- TEST 1: Civilian / Warkari Report Submission ---")
    report_payload = {
        "title": "Severe Waterlogging and Garbage Accumulation near Saswad Checkpost",
        "issue_type": "GARBAGE_OVERFLOW",
        "description": "Pilgrims facing major difficulty navigating through wet garbage and discarded packaging.",
        "location_name": "Saswad Octroi Checkpost, Saswad",
        "latitude": "18.348000",
        "longitude": "74.032000",
        "priority": "HIGH",
    }
    create_res = public_client.post("/api/sanitation/reports/", report_payload, format="multipart")
    assert create_res.status_code == 201, f"Expected 201, got {create_res.status_code}: {create_res.json()}"
    report_data = create_res.json()
    report_id = report_data["report_id"]
    report_code = report_data["report_code"]
    print(f"[OK] Report created successfully! Report ID: {report_id}, Code: {report_code}, Status: {report_data['status']}")
    assert report_code.startswith("SAN-"), f"Expected SAN- prefix, got {report_code}"

    # 3. Test: Check Database Record
    print("\n--- TEST 2: Database Record Verification ---")
    db_report = SanitationReport.objects.get(id=report_id)
    assert db_report.title == report_payload["title"]
    assert db_report.status == SanitationReport.Status.REPORTED
    assert db_report.priority == "HIGH"
    print(f"[OK] DB Record verified in Django ORM: #{db_report.report_code} ({db_report.title})")

    # 4. Test: Admin Stats API
    print("\n--- TEST 3: Admin Statistics API ---")
    stats_res = admin_client.get("/api/sanitation/stats/")
    assert stats_res.status_code == 200
    stats_data = stats_res.json()
    print(f"[OK] Stats API verified: Total={stats_data['total']}, Reported={stats_data['reported']}, Assigned={stats_data['assigned']}, InProgress={stats_data['in_progress']}, Resolved={stats_data['resolved']}")
    assert stats_data["total"] >= 1
    assert stats_data["reported"] >= 1

    # 5. Test: Admin Detail View
    print("\n--- TEST 4: Admin Report Detail View ---")
    detail_res = admin_client.get(f"/api/sanitation/reports/{report_id}/")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["report_code"] == report_code
    print(f"[OK] Report Detail API verified: #{detail_data['report_code']} at {detail_data['location_name']}")

    # 6. Test: Admin Assigns Report to Volunteer
    print("\n--- TEST 5: Admin Task Assignment to Volunteer ---")
    assign_payload = {
        "volunteer_id": vol_profile.id,
        "instructions": "Please bring 2 waste disposal bags and coordinate with local municipal vehicle.",
        "priority": "HIGH",
    }
    assign_res = admin_client.post(f"/api/sanitation/reports/{report_id}/assign/", assign_payload, format="json")
    assert assign_res.status_code == 200, f"Expected 200, got {assign_res.status_code}: {assign_res.json()}"
    assign_data = assign_res.json()
    assert assign_data["status"] == "ASSIGNED"
    print(f"[OK] Task assigned to {assign_data['assigned_volunteer']['name']}! Linked Task ID: {assign_data['task_id']}")

    # Verify Volunteer received TASK_ASSIGNED notification
    notif = Notification.objects.filter(recipient=volunteer_user, notification_type=Notification.NotificationType.TASK_ASSIGNED).first()
    assert notif is not None, "Volunteer should have received TASK_ASSIGNED notification"
    print(f"[OK] Volunteer Notification verified: '{notif.title.encode('ascii', 'replace').decode()}'")

    # 7. Test: Volunteer views task in /api/operations/volunteer/my-tasks/
    print("\n--- TEST 6: Volunteer Self Tasks Queue ---")
    vol_tasks_res = volunteer_client.get("/api/operations/volunteer/my-tasks/")
    assert vol_tasks_res.status_code == 200
    vol_tasks = vol_tasks_res.json()
    matched_task = next((t for t in vol_tasks if t["task_id"] == assign_data["task_id"]), None)
    assert matched_task is not None, f"Task {assign_data['task_id']} not found in volunteer tasks"
    print(f"[OK] Task found in Volunteer's task feed: #{matched_task['task_id']} '{matched_task['title']}' (Status: {matched_task['status']})")

    # 8. Test: Volunteer Starts Task
    print("\n--- TEST 7: Volunteer Starts Task (IN_PROGRESS) ---")
    start_res = volunteer_client.post(f"/api/operations/volunteer/tasks/{matched_task['id']}/action/", {"action": "START"}, format="json")
    assert start_res.status_code == 200, f"Expected 200, got {start_res.status_code}: {start_res.json()}"
    db_report.refresh_from_db()
    assert db_report.status == SanitationReport.Status.IN_PROGRESS, f"Expected IN_PROGRESS, got {db_report.status}"
    print(f"[OK] Task started! Sanitation report status automatically synchronized to: {db_report.status}")

    # 9. Test: Volunteer Completes Task with Resolution Note
    print("\n--- TEST 8: Volunteer Completes Task (RESOLVED) ---")
    resolution_text = "Swept entire 200m perimeter, collected 4 bags of plastic and food waste, sprayed disinfectant."
    complete_res = volunteer_client.post(
        f"/api/operations/volunteer/tasks/{matched_task['id']}/action/",
        {"action": "COMPLETE", "note": resolution_text},
        format="json"
    )
    assert complete_res.status_code == 200
    db_report.refresh_from_db()
    assert db_report.status == SanitationReport.Status.RESOLVED, f"Expected RESOLVED, got {db_report.status}"
    assert db_report.resolution_note == resolution_text
    assert db_report.resolved_at is not None
    print(f"[OK] Task completed! Sanitation report #{db_report.report_code} status: {db_report.status}")
    print(f"[OK] Resolution note saved: '{db_report.resolution_note}'")
    print(f"[OK] Resolved timestamp: {db_report.resolved_at}")

    # 10. Test: Filter & Search APIs
    print("\n--- TEST 9: Filter & Search Functionality ---")
    search_res = admin_client.get(f"/api/sanitation/reports/?search=Saswad")
    assert search_res.status_code == 200
    assert len(search_res.json()) >= 1
    print(f"[OK] Search by location 'Saswad' returned {len(search_res.json())} reports")

    status_filter_res = admin_client.get(f"/api/sanitation/reports/?status=RESOLVED")
    assert status_filter_res.status_code == 200
    assert all(r["status"] == "RESOLVED" for r in status_filter_res.json())
    print(f"[OK] Filter by status 'RESOLVED' returned {len(status_filter_res.json())} correctly filtered records")

    # 11. Test: Validation & Error Handling
    print("\n--- TEST 10: Validation & Error Handling ---")
    invalid_res = public_client.post("/api/sanitation/reports/", {"issue_type": "INVALID_TYPE"}, format="json")
    assert invalid_res.status_code == 400
    print("[OK] Invalid payload rejected with HTTP 400 as expected")

    print("\n==================================================")
    print("ALL 10 END-TO-END SANITATION TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
