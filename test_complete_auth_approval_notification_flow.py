import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from rest_framework.test import APIClient
from apps.users.models import User, OrganizerApplication, EmailLog
from apps.operations.models import VolunteerApplication, VolunteerProfile, Task
from apps.notifications.models import Notification

def run_master_suite():
    print("==================================================================")
    print("WARIVEDH MASTER AUTH + APPROVAL + EMAIL + TASK NOTIFICATION SUITE")
    print("==================================================================")

    # 1. Setup Admin Account
    admin_user, _ = User.objects.get_or_create(
        email="admin@warivedh.com",
        defaults={
            "username": "admin",
            "role": "ADMIN",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        }
    )
    admin_user.set_password("admin123")
    admin_user.is_active = True
    admin_user.is_staff = True
    admin_user.role = "ADMIN"
    admin_user.save()

    admin_client = APIClient()
    admin_client.force_authenticate(user=admin_user)
    public_client = APIClient()

    print(f"[OK] Admin Setup: {admin_user.email} (Role: {admin_user.role})")

    # ==============================================================================
    # PART 1: VOLUNTEER APPLICATION -> PENDING -> LOGIN BLOCKED -> APPROVE / REJECT
    # ==============================================================================
    print("\n--- TEST 1: Volunteer Application & Login Enforcement ---")

    # Clean old test records
    test_vol_emails = ["vol_a_test@warivedh.com", "vol_b_test@warivedh.com", "vol_c_test@warivedh.com"]
    VolunteerApplication.objects.filter(email__in=test_vol_emails).delete()
    User.objects.filter(email__in=test_vol_emails).delete()

    # Volunteer A applies
    app_a_res = public_client.post("/api/operations/volunteer-applications/", {
        "full_name": "Volunteer Alpha",
        "email": "vol_a_test@warivedh.com",
        "mobile_number": "9876543210",
        "age": 24,
        "preferred_duty_area": "Alandi Temple Route",
        "preferred_purpose": "CROWD_MANAGEMENT",
        "skills": ["First Aid", "Marathi", "Crowd Control"],
        "availability": "All 15 days",
    }, format="json")
    assert app_a_res.status_code == 201, f"Expected 201, got {app_a_res.status_code}: {app_a_res.json()}"
    app_a_id = app_a_res.json()["application_id"]
    print(f"[PASS] Volunteer A Application Created: {app_a_id} (Status: PENDING)")

    # Volunteer B applies
    app_b_res = public_client.post("/api/operations/volunteer-applications/", {
        "full_name": "Volunteer Beta",
        "email": "vol_b_test@warivedh.com",
        "mobile_number": "9876543211",
        "age": 22,
        "preferred_duty_area": "Saswad Ghat",
        "preferred_purpose": "WATER_DISTRIBUTION",
        "skills": ["Water supply"],
    }, format="json")
    assert app_b_res.status_code == 201
    app_b_id = app_b_res.json()["application_id"]
    print(f"[PASS] Volunteer B Application Created: {app_b_id} (Status: PENDING)")

    # Volunteer C applies
    app_c_res = public_client.post("/api/operations/volunteer-applications/", {
        "full_name": "Volunteer Gamma",
        "email": "vol_c_test@warivedh.com",
        "mobile_number": "9876543212",
        "age": 26,
        "preferred_duty_area": "Jejuri Route",
        "preferred_purpose": "FIRST_AID",
        "skills": ["Nursing"],
    }, format="json")
    assert app_c_res.status_code == 201
    app_c_id = app_c_res.json()["application_id"]
    print(f"[PASS] Volunteer C Application Created: {app_c_id} (Status: PENDING)")

    # Verify Volunteer A CANNOT login while PENDING
    pending_login_res = public_client.post("/api/users/login/", {
        "email": "vol_a_test@warivedh.com",
        "password": "anypassword123"
    }, format="json")
    assert pending_login_res.status_code == 400
    print(f"[PASS] Volunteer A Login Blocked while PENDING: {pending_login_res.json().get('non_field_errors', pending_login_res.json())}")

    # ==============================================================================
    # PART 2: ADMIN APPROVES VOLUNTEER A & VOLUNTEER C, REJECTS VOLUNTEER B
    # ==============================================================================
    print("\n--- TEST 2: Admin Volunteer Application Review & Approval Emails ---")

    # Approve Volunteer A
    approve_a_res = admin_client.post(f"/api/operations/volunteer-applications/{app_a_id}/review/", {
        "decision": "APPROVED",
        "review_note": "Verified ID and medical credentials."
    }, format="json")
    assert approve_a_res.status_code == 200
    print(f"[PASS] Volunteer A APPROVED by Admin!")

    # Reject Volunteer B
    reject_b_res = admin_client.post(f"/api/operations/volunteer-applications/{app_b_id}/review/", {
        "decision": "REJECTED",
        "review_note": "Incomplete contact details and unavailable during critical dates."
    }, format="json")
    assert reject_b_res.status_code == 200
    print(f"[PASS] Volunteer B REJECTED by Admin!")

    # Approve Volunteer C
    approve_c_res = admin_client.post(f"/api/operations/volunteer-applications/{app_c_id}/review/", {
        "decision": "APPROVED",
        "review_note": "Certified nurse, assigned to Jejuri Medical Desk."
    }, format="json")
    assert approve_c_res.status_code == 200
    print(f"[PASS] Volunteer C APPROVED by Admin!")

    # Verify Volunteer A User Account is Active and Can Set Password / Login
    vol_a_user = User.objects.get(email="vol_a_test@warivedh.com")
    assert vol_a_user.role == "VOLUNTEER"
    assert vol_a_user.is_active is True
    vol_a_user.set_password("vol_password_123")
    vol_a_user.save()

    vol_a_login = public_client.post("/api/users/login/", {
        "email": "vol_a_test@warivedh.com",
        "password": "vol_password_123"
    }, format="json")
    assert vol_a_login.status_code == 200
    vol_a_token = vol_a_login.json()["access"]
    print(f"[PASS] Volunteer A Logged in Successfully! Role: {vol_a_login.json()['user']['role']}")

    # Verify Rejected Volunteer B CANNOT login
    vol_b_login = public_client.post("/api/users/login/", {
        "email": "vol_b_test@warivedh.com",
        "password": "some_password"
    }, format="json")
    assert vol_b_login.status_code == 400
    print(f"[PASS] Rejected Volunteer B Login Denied: {vol_b_login.json().get('non_field_errors', vol_b_login.json())}")

    # Setup Volunteer C password
    vol_c_user = User.objects.get(email="vol_c_test@warivedh.com")
    vol_c_user.set_password("vol_c_password_123")
    vol_c_user.save()

    vol_c_login = public_client.post("/api/users/login/", {
        "email": "vol_c_test@warivedh.com",
        "password": "vol_c_password_123"
    }, format="json")
    assert vol_c_login.status_code == 200
    vol_c_token = vol_c_login.json()["access"]
    print(f"[PASS] Volunteer C Logged in Successfully!")

    # ==============================================================================
    # PART 3: ORGANIZER APPLICATION -> PENDING -> APPROVE / REJECT FLOW
    # ==============================================================================
    print("\n--- TEST 3: Organizer Application & Approval Flow ---")

    test_org_emails = ["org_alpha@warivedh.com", "org_beta@warivedh.com"]
    OrganizerApplication.objects.filter(email__in=test_org_emails).delete()
    User.objects.filter(email__in=test_org_emails).delete()

    # Organizer A applies
    org_a_res = public_client.post("/api/users/organizer-applications/", {
        "full_name": "Pramukh Ramdas Patil",
        "email": "org_alpha@warivedh.com",
        "mobile_number": "9822001122",
        "dindi_name": "Shree Tukaram Maharaj Palkhi Dindi No. 12",
        "dindi_type": "Major Dindi",
        "expected_warkaris": 8500,
        "starting_location": "Dehu",
        "destination": "Pandharpur",
        "organization_name": "Dehu Sansthan Mitra Mandal",
        "emergency_contact": "9822001199",
    }, format="json")
    assert org_a_res.status_code == 201
    org_a_id = org_a_res.json()["application_id"]
    print(f"[PASS] Organizer A Application Created: {org_a_id} (Status: PENDING)")

    # Organizer B applies
    org_b_res = public_client.post("/api/users/organizer-applications/", {
        "full_name": "Pramukh Suresh Shinde",
        "email": "org_beta@warivedh.com",
        "mobile_number": "9822003344",
        "dindi_name": "Local Pune Bhajan Dindi",
        "dindi_type": "Local Dindi",
        "expected_warkaris": 200,
        "starting_location": "Pune",
        "destination": "Pandharpur",
        "organization_name": "Pune Mandal",
        "emergency_contact": "9822003399",
    }, format="json")
    assert org_b_res.status_code == 201
    org_b_id = org_b_res.json()["application_id"]
    print(f"[PASS] Organizer B Application Created: {org_b_id} (Status: PENDING)")

    # Verify Organizer A CANNOT login while PENDING
    org_a_pending_login = public_client.post("/api/users/login/", {
        "email": "org_alpha@warivedh.com",
        "password": "anypassword"
    }, format="json")
    assert org_a_pending_login.status_code == 400
    print(f"[PASS] Organizer A Login Blocked while PENDING: {org_a_pending_login.json().get('non_field_errors', org_a_pending_login.json())}")

    # Admin APPROVES Organizer A
    org_a_approve = admin_client.post(f"/api/users/organizer-applications/{org_a_id}/review/", {
        "decision": "APPROVED"
    }, format="json")
    assert org_a_approve.status_code == 200
    print(f"[PASS] Organizer A APPROVED by Committee!")

    # Admin REJECTS Organizer B
    org_b_reject = admin_client.post(f"/api/users/organizer-applications/{org_b_id}/review/", {
        "decision": "REJECTED",
        "rejection_reason": "Duplicate registration for the same route segment."
    }, format="json")
    assert org_b_reject.status_code == 200
    print(f"[PASS] Organizer B REJECTED by Committee!")

    # Verify Organizer A User Account is Active and Can Login
    org_a_user = User.objects.get(email="org_alpha@warivedh.com")
    assert org_a_user.role == "ORGANIZER"
    assert org_a_user.is_active is True
    org_a_user.set_password("org_password_123")
    org_a_user.save()

    org_a_login = public_client.post("/api/users/login/", {
        "email": "org_alpha@warivedh.com",
        "password": "org_password_123"
    }, format="json")
    assert org_a_login.status_code == 200
    print(f"[PASS] Organizer A Logged in Successfully! Role: {org_a_login.json()['user']['role']}")

    # Verify Rejected Organizer B CANNOT login
    org_b_login = public_client.post("/api/users/login/", {
        "email": "org_beta@warivedh.com",
        "password": "some_password"
    }, format="json")
    assert org_b_login.status_code == 400
    print(f"[PASS] Rejected Organizer B Login Denied: {org_b_login.json().get('non_field_errors', org_b_login.json())}")

    # ==============================================================================
    # PART 4: TASK ASSIGNMENT & TARGETED NOTIFICATIONS (ZERO CROSS-LEAKAGE)
    # ==============================================================================
    print("\n--- TEST 4: Task Assignment & Targeted Notification Privacy ---")

    vol_a_profile = vol_a_user.volunteer_profile
    vol_c_profile = vol_c_user.volunteer_profile

    vol_a_client = APIClient()
    vol_a_client.credentials(HTTP_AUTHORIZATION=f"Bearer {vol_a_token}")

    vol_c_client = APIClient()
    vol_c_client.credentials(HTTP_AUTHORIZATION=f"Bearer {vol_c_token}")

    # Clear notification inboxes for clean test
    Notification.objects.filter(recipient__in=[vol_a_user, vol_c_user]).delete()

    # Admin creates Task 1 -> Assigned to Volunteer A
    task_1_res = admin_client.post("/api/operations/tasks/", {
        "title": "Alandi Temple Queue Coordination",
        "description": "Manage gate 2 queue line.",
        "purpose": "CROWD_MANAGEMENT",
        "priority": "HIGH",
        "location": "Alandi Mandir Gate 2",
        "assigned_volunteer": vol_a_profile.id,
    }, format="json")
    assert task_1_res.status_code == 201
    task_1_id = task_1_res.json()["task_id"]
    print(f"[PASS] Task 1 ({task_1_id}) Assigned to Volunteer A")

    # Admin creates Task 2 -> Assigned to Volunteer C
    task_2_res = admin_client.post("/api/operations/tasks/", {
        "title": "Jejuri Medical First Aid Tent Support",
        "description": "Assist primary health center doctor.",
        "purpose": "FIRST_AID",
        "priority": "CRITICAL",
        "location": "Jejuri Palkhi Ground Tent 4",
        "assigned_volunteer": vol_c_profile.id,
    }, format="json")
    assert task_2_res.status_code == 201
    task_2_id = task_2_res.json()["task_id"]
    print(f"[PASS] Task 2 ({task_2_id}) Assigned to Volunteer C")

    # Verify Volunteer A's Notifications (/api/notifications/)
    notifs_a = vol_a_client.get("/api/notifications/").json()
    titles_a = [n["title"] for n in notifs_a if n["notification_type"] == "TASK_ASSIGNED"]
    assert any("Alandi Temple Queue" in t for t in titles_a), "Vol A must have Task 1"
    assert not any("Jejuri Medical" in t for t in titles_a), "Vol A must NOT have Task 2"
    print(f"[PASS] Volunteer A sees Task 1 notification ONLY (No Task 2 leak)!")

    # Verify Volunteer C's Notifications (/api/notifications/)
    notifs_c = vol_c_client.get("/api/notifications/").json()
    titles_c = [n["title"] for n in notifs_c if n["notification_type"] == "TASK_ASSIGNED"]
    assert any("Jejuri Medical" in t for t in titles_c), "Vol C must have Task 2"
    assert not any("Alandi Temple Queue" in t for t in titles_c), "Vol C must NOT have Task 1"
    print(f"[PASS] Volunteer C sees Task 2 notification ONLY (No Task 1 leak)!")

    # ==============================================================================
    # PART 5: TASK REASSIGNMENT NOTIFICATION ISOLATION
    # ==============================================================================
    print("\n--- TEST 5: Task Reassignment Notification Clean Isolation ---")

    task_1_pk = task_1_res.json()["id"]
    # Reassign Task 1 from Volunteer A -> Volunteer C
    reassign_res = admin_client.post(f"/api/operations/tasks/{task_1_pk}/assign/", {
        "volunteer_id": vol_c_profile.id
    }, format="json")
    assert reassign_res.status_code == 200
    print(f"[PASS] Task 1 ({task_1_id}) Reassigned from Volunteer A to Volunteer C!")

    # Volunteer C should now receive Task 1 notification
    notifs_c_after = vol_c_client.get("/api/notifications/").json()
    titles_c_after = [n["title"] for n in notifs_c_after if n["notification_type"] == "TASK_ASSIGNED"]
    assert any("Alandi Temple Queue" in t for t in titles_c_after), "Vol C must now have Task 1"
    assert any("Jejuri Medical" in t for t in titles_c_after), "Vol C must still have Task 2"
    print(f"[PASS] Volunteer C received the new assignment notification for Task 1!")

    # ==============================================================================
    # PART 6: EMAIL LOGGING VERIFICATION
    # ==============================================================================
    print("\n--- TEST 6: Email Logs & SMTP Service Verification ---")
    logs = EmailLog.objects.filter(recipient__in=test_vol_emails + test_org_emails)
    print(f"Total Email Logs generated for test run: {logs.count()}")
    for log in logs:
        print(f"  [EMAIL LOG] Type: {log.email_type} -> {log.recipient} ({log.status})")

    assert logs.filter(email_type="VOLUNTEER_APPLICATION_RECEIVED").exists()
    assert logs.filter(email_type="VOLUNTEER_APPLICATION_APPROVED").exists()
    assert logs.filter(email_type="VOLUNTEER_APPLICATION_REJECTED").exists()
    assert logs.filter(email_type="ORGANIZER_APPLICATION_RECEIVED").exists()
    assert logs.filter(email_type="ORGANIZER_APPLICATION_APPROVED").exists()
    assert logs.filter(email_type="ORGANIZER_APPLICATION_REJECTED").exists()
    print("[PASS] All 6 Email types logged and dispatched correctly!")

    print("\n==================================================================")
    print("SUCCESS: ALL MASTER AUTH, APPROVAL, EMAIL & NOTIFICATION TESTS PASSED!")
    print("==================================================================")

if __name__ == "__main__":
    run_master_suite()
