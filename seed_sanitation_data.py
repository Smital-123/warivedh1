import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from decimal import Decimal
from django.utils import timezone
from apps.sanitation.models import SanitationReport, SmartBin
from apps.operations.models import VolunteerProfile, Task, VolunteerPurpose
from apps.users.models import User

def seed_sanitation():
    print("Seeding realistic Wari sanitation reports...")

    # Get sample volunteer if exists
    volunteer = VolunteerProfile.objects.filter(is_active=True).first()
    admin_user = User.objects.filter(role__in=["ADMIN", "STAFF"]).first()

    SAMPLE_DATA = [
        {
            "title": "Overflowing Public Dustbins near Alandi Indrayani Ghat",
            "issue_type": "NO_DUSTBIN",
            "location_name": "Alandi Indrayani River Ghat, Pune",
            "latitude": Decimal("18.677500"),
            "longitude": Decimal("73.896900"),
            "priority": "HIGH",
            "status": "REPORTED",
            "description": "Pilgrims have discarded leaf plates and plastic water pouches near the ghat steps. Dustbins are completely overflowing and require urgent clearing before the morning dindi procession.",
        },
        {
            "title": "Severe Garbage Accumulation at Hadapsar Gadital Chowk",
            "issue_type": "GARBAGE_OVERFLOW",
            "location_name": "Hadapsar Gadital Palkhi Halt, Pune",
            "latitude": Decimal("18.508900"),
            "longitude": Decimal("73.926000"),
            "priority": "CRITICAL",
            "status": "ACKNOWLEDGED",
            "description": "Massive heap of food packets, tea cups, and wet waste accumulated near the public distribution stalls. Heavy pedestrian crowd passing nearby.",
        },
        {
            "title": "Mobile Toilet Flush Failure and Overflow at Dive Ghat Top",
            "issue_type": "TOILET_PROBLEM",
            "location_name": "Dive Ghat Summit Camp, Saswad Road",
            "latitude": Decimal("18.423000"),
            "longitude": Decimal("73.985000"),
            "priority": "CRITICAL",
            "status": "ASSIGNED",
            "description": "Three mobile sanitation units near the summit checkpoint have non-functional water supplies and overflowing waste tanks causing severe odor along the main walking lane.",
        },
        {
            "title": "Broken Drinking Water Pipeline Causing Mud and Wastage",
            "issue_type": "DIRTY_WATER",
            "location_name": "Saswad City Entrance Tanker Point, Saswad",
            "latitude": Decimal("18.344400"),
            "longitude": Decimal("74.030500"),
            "priority": "HIGH",
            "status": "IN_PROGRESS",
            "description": "Fresh water pipeline tap connection is broken, leading to potable water leakage and slippery mud formation on the main bypass where thousands of warkaris are walking.",
        },
        {
            "title": "Blocked Road Drainage Overflowing on Jejuri Temple Path",
            "issue_type": "DRAINAGE_PROBLEM",
            "location_name": "Jejuri Khandoba Foothills, Jejuri",
            "latitude": Decimal("18.274500"),
            "longitude": Decimal("74.156800"),
            "priority": "HIGH",
            "status": "REPORTED",
            "description": "Drainage gutter blocked by discarded single-use bags. Dirty sewage water is spilling onto the pedestrian pathway leading to the main temple chowk.",
        },
        {
            "title": "Unclean Resting Ground & Plastic Waste at Lonand Station Road",
            "issue_type": "ROAD_CLEANING",
            "location_name": "Lonand Palkhi Talav Grounds, Lonand",
            "latitude": Decimal("18.046000"),
            "longitude": Decimal("74.192000"),
            "priority": "MEDIUM",
            "status": "ACKNOWLEDGED",
            "description": "Post-afternoon lunch halt, grounds are littered with disposable plates, packaging cartons, and coconut shells. Ground requires sweeping and garbage bagging.",
        },
        {
            "title": "Unsegregated Waste Heaps near Phaltan APMC Market",
            "issue_type": "WASTE_SEGREGATION",
            "location_name": "Phaltan APMC Mandi Camp, Phaltan",
            "latitude": Decimal("17.987000"),
            "longitude": Decimal("74.432000"),
            "priority": "MEDIUM",
            "status": "IN_PROGRESS",
            "description": "Vegetable waste from community kitchens mixed with plastic packaging. Waste segregation drums need to be placed and segregated collection vehicle dispatched.",
        },
        {
            "title": "Overflowing Dustbins and Stagnant Water at Malshiras Camp",
            "issue_type": "GARBAGE_OVERFLOW",
            "location_name": "Malshiras ZP School Ground, Malshiras",
            "latitude": Decimal("17.842000"),
            "longitude": Decimal("74.912000"),
            "priority": "HIGH",
            "status": "REPORTED",
            "description": "Bins near the community dining tents are packed to capacity. Liquid food waste leaking onto soil.",
        },
        {
            "title": "Mobile Toilet Maintenance Required at Velapur Ringan Ground",
            "issue_type": "TOILET_PROBLEM",
            "location_name": "Velapur Ringan Maidan, Velapur",
            "latitude": Decimal("17.760000"),
            "longitude": Decimal("75.050000"),
            "priority": "MEDIUM",
            "status": "RESOLVED",
            "description": "Water tank refill required for 10 mobile units installed along the Ringan circle arena.",
            "resolution_note": "Municipal water tanker refilled all 10 unit overhead tanks. Disinfectant powder sprayed across the perimeter.",
        },
        {
            "title": "Garbage Clearance along Pandharpur VIP VIP Ghat Approach",
            "issue_type": "ROAD_CLEANING",
            "location_name": "Chandrabhaga VIP Ghat Path, Pandharpur",
            "latitude": Decimal("17.677500"),
            "longitude": Decimal("75.328000"),
            "priority": "CRITICAL",
            "status": "RESOLVED",
            "description": "Heavy accumulation of flowers, garlands, and discarded footwear near the river entrance.",
            "resolution_note": "Rapid response sanitation volunteer squad cleared 8 tractor loads of flower waste and disinfected path.",
        },
        {
            "title": "Medical First Aid Waste Discarded at Phaltan Ringan",
            "issue_type": "OTHER",
            "location_name": "Phaltan Ringan Chowk, Phaltan",
            "latitude": Decimal("17.982000"),
            "longitude": Decimal("74.428000"),
            "priority": "HIGH",
            "status": "REPORTED",
            "description": "Used bandages and antiseptic bottles found discarded near the temporary medical camp counter. Bio-hazard box disposal needed.",
        },
    ]

    created_records = []
    for item in SAMPLE_DATA:
        # Check if already exists by location and title
        report, created = SanitationReport.objects.get_or_create(
            location_name=item["location_name"],
            title=item["title"],
            defaults={
                "issue_type": item["issue_type"],
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "priority": item["priority"],
                "status": item["status"],
                "description": item["description"],
                "resolution_note": item.get("resolution_note", ""),
                "resolved_at": timezone.now() if item["status"] == "RESOLVED" else None,
                "resolved_by": admin_user if item["status"] == "RESOLVED" else None,
            }
        )

        if not report.report_code:
            report.report_code = f"SAN-{report.id:05d}"
            report.save(update_fields=["report_code"])

        # For ASSIGNED or IN_PROGRESS, link to sample volunteer if available
        if item["status"] in ("ASSIGNED", "IN_PROGRESS") and volunteer and not report.assigned_volunteer:
            task, _ = Task.objects.get_or_create(
                title=f"Sanitation: {report.title}",
                defaults={
                    "description": report.description,
                    "purpose": VolunteerPurpose.OTHER,
                    "priority": report.priority,
                    "location": report.location_name,
                    "assigned_volunteer": volunteer,
                    "status": Task.TaskStatus.IN_PROGRESS if item["status"] == "IN_PROGRESS" else Task.TaskStatus.ASSIGNED,
                }
            )
            report.assigned_volunteer = volunteer
            report.task = task
            report.save(update_fields=["assigned_volunteer", "task"])

        created_records.append((report.report_code or f"SAN-{report.id:05d}", report.title, report.location_name, report.status, report.priority))

    print(f"Successfully ensured {len(created_records)} sample sanitation records:")
    for code, title, loc, st, pri in created_records:
        print(f"  - [{code}] {title[:40]}... @ {loc} ({st}, Priority: {pri})")

if __name__ == "__main__":
    seed_sanitation()
