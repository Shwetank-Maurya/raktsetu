"""One-shot Firebase provisioning with the Admin service account (idempotent, safe to re-run).

  python -m scripts.firebase_setup [--password X] [--write-frontend-env]

1. Registers a Firebase Web App (if none) and prints its public web config
2. Enables Email/Password sign-in (Identity Toolkit admin API)
3. Creates demo users with role custom claims (same as scripts/set_claims.py)
4. Deploys infra/firestore.rules (Firebase Rules API)
5. Optionally writes the VITE_FIREBASE_* values into frontend/.env

Needs GOOGLE_APPLICATION_CREDENTIALS (service account JSON) and FIREBASE_PROJECT_ID.
Web config values are public by design (they identify the project; security comes from Auth + rules).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import google.auth  # noqa: E402
import google.auth.transport.requests  # noqa: E402

from app.config import get_settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCOPES = ["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/firebase"]


def session():
    creds, _ = google.auth.default(scopes=SCOPES)
    return google.auth.transport.requests.AuthorizedSession(creds)


def web_app(s, project: str) -> dict:
    base = f"https://firebase.googleapis.com/v1beta1/projects/{project}"
    apps = s.get(f"{base}/webApps").json().get("apps", [])
    if not apps:
        op = s.post(f"{base}/webApps", json={"displayName": "RaktSetu Web"}).json()
        if "error" in op:
            raise SystemExit(f"cannot create web app: {op['error'].get('message')}")
        for _ in range(30):
            if op.get("done"):
                break
            time.sleep(2)
            op = s.get(f"https://firebase.googleapis.com/v1beta1/{op['name']}").json()
        apps = s.get(f"{base}/webApps").json().get("apps", [])
        print("created web app:", apps[0]["appId"] if apps else op)
    cfg = s.get(f"https://firebase.googleapis.com/v1beta1/{apps[0]['name']}/config").json()
    return cfg


def enable_email_auth(s, project: str) -> str:
    url = f"https://identitytoolkit.googleapis.com/admin/v2/projects/{project}/config"
    r = s.patch(url, params={"updateMask": "signIn.email.enabled,signIn.email.passwordRequired"},
                json={"signIn": {"email": {"enabled": True, "passwordRequired": True}}})
    if r.status_code == 404 or "CONFIGURATION_NOT_FOUND" in r.text:
        init = s.post(f"https://identitytoolkit.googleapis.com/v2/projects/{project}/identityPlatform:initializeAuth", json={})
        if not init.ok:
            return f"needs one click: Firebase console -> Authentication -> Get started ({init.text[:120]})"
        r = s.patch(url, params={"updateMask": "signIn.email.enabled,signIn.email.passwordRequired"},
                    json={"signIn": {"email": {"enabled": True, "passwordRequired": True}}})
    return "email/password enabled" if r.ok else f"failed: {r.status_code} {r.text[:200]}"


def deploy_rules(s, project: str) -> str:
    src = (ROOT / "infra" / "firestore.rules").read_text()
    base = f"https://firebaserules.googleapis.com/v1/projects/{project}"
    rs = s.post(f"{base}/rulesets", json={"source": {"files": [{"name": "firestore.rules", "content": src}]}})
    if not rs.ok:
        return f"ruleset failed: {rs.status_code} {rs.text[:160]}"
    name = rs.json()["name"]
    rel = f"projects/{project}/releases/cloud.firestore"
    r = s.patch(f"https://firebaserules.googleapis.com/v1/{rel}", json={"release": {"name": rel, "rulesetName": name}})
    if r.status_code == 404:
        r = s.post(f"{base}/releases", json={"name": rel, "rulesetName": name})
    return "firestore rules deployed" if r.ok else f"release failed: {r.status_code} {r.text[:160]}"


def write_frontend_env(cfg: dict, password: str) -> None:
    p = ROOT / "frontend" / ".env"
    text = p.read_text() if p.exists() else ""
    values = {
        "VITE_FIREBASE_API_KEY": cfg.get("apiKey", ""), "VITE_FIREBASE_AUTH_DOMAIN": cfg.get("authDomain", ""),
        "VITE_FIREBASE_PROJECT_ID": cfg.get("projectId", ""), "VITE_FIREBASE_APP_ID": cfg.get("appId", ""),
        "VITE_FIREBASE_MESSAGING_SENDER_ID": cfg.get("messagingSenderId", ""),
        "VITE_FIREBASE_MEASUREMENT_ID": cfg.get("measurementId", ""), "VITE_DEMO_PASSWORD": password,
    }
    for k, v in values.items():
        if re.search(rf"^{k}=.*$", text, re.M):
            text = re.sub(rf"^{k}=.*$", f"{k}={v}", text, flags=re.M)
        else:
            text += f"\n{k}={v}"
    p.write_text(text.strip() + "\n")
    print("wrote", p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", default="RaktSetu@Demo2026")
    ap.add_argument("--write-frontend-env", action="store_true")
    a = ap.parse_args()
    project = get_settings().firebase_project_id
    if not project:
        raise SystemExit("set FIREBASE_PROJECT_ID")
    s = session()
    cfg = web_app(s, project)
    print("web config keys:", sorted(cfg))
    print("auth:", enable_email_auth(s, project))
    from scripts.set_claims import main as set_claims

    try:
        set_claims(a.password)
    except Exception as exc:  # noqa: BLE001
        print("demo users failed:", exc)
    print("rules:", deploy_rules(s, project))
    if a.write_frontend_env:
        write_frontend_env(cfg, a.password)
    print(json.dumps({k: cfg.get(k) for k in ("projectId", "authDomain", "appId")}, indent=1))


if __name__ == "__main__":
    main()
