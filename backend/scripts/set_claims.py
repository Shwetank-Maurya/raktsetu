"""Create Firebase Auth demo users and set role custom claims (Admin SDK).
Usage: FIREBASE_PROJECT_ID=... GOOGLE_APPLICATION_CREDENTIALS=sa.json python -m scripts.set_claims [--password X]
Roles: hospital_user | bank_manager | regional_coordinator | admin; scope via facility_id / region_id."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import firebase_admin  # noqa: E402
import psycopg2  # noqa: E402
from firebase_admin import auth  # noqa: E402

from app.config import get_settings  # noqa: E402

USERS = [
    ("coordinator@raktsetu.demo", "Regional Coordinator", "regional_coordinator", None, "STATE"),
    ("bank@raktsetu.demo", "Blood Bank Manager", "bank_manager", "BB-01", None),
    ("hospital@raktsetu.demo", "Transfusion Officer", "hospital_user", "LH-01", None),
    ("admin@raktsetu.demo", "Platform Admin", "admin", None, "STATE"),
]


def main(password: str) -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": get_settings().firebase_project_id or os.environ["FIREBASE_PROJECT_ID"]})
    cur = psycopg2.connect(get_settings().sync_database_url_direct.replace("postgresql+psycopg2://", "postgresql://")).cursor()
    cur.execute("SELECT code, id FROM facilities")
    fac = dict(cur.fetchall())
    cur.execute("SELECT id FROM regions WHERE level = 'state' LIMIT 1")
    state = cur.fetchone()[0]
    for email, name, role, fcode, rcode in USERS:
        try:
            u = auth.get_user_by_email(email)
        except auth.UserNotFoundError:
            u = auth.create_user(email=email, password=password, display_name=name)
        claims = {"role": role, "facility_id": fac.get(fcode) if fcode else None, "region_id": state if rcode else None}
        auth.set_custom_user_claims(u.uid, claims)
        print(f"{email}: {claims}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", default=os.environ.get("DEMO_USER_PASSWORD", "RaktSetu@2026"))
    main(ap.parse_args().password)
