"""Post-deploy smoke test + pre-demo warm-up. Usage: python -m scripts.smoke https://your-app.web.app
Hits /readyz (wakes Neon from scale-to-zero), logs in as each demo role, fetches risk/map/kpis,
calls the copilot and checks RBAC scoping. Exit code 1 on any failure."""

import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def main() -> int:
    ok = True
    with httpx.Client(timeout=60) as c:
        t0 = time.time()
        r = c.get(f"{BASE}/api/readyz")
        print(f"readyz {r.status_code} in {time.time() - t0:.1f}s")
        ok &= r.status_code == 200
        for who in ("coordinator", "bank", "hospital"):
            tok = c.post(f"{BASE}/api/auth/demo-login", json={"user": who}).json()["token"]
            h = {"Authorization": f"Bearer {tok}"}
            for path in ("/api/kpis", "/api/risk?limit=5", "/api/map/risk", "/api/inventory/matrix", "/api/transfers?status=proposed"):
                t0 = time.time()
                r = c.get(BASE + path, headers=h)
                print(f"{who:12s} {path:32s} {r.status_code} {1000 * (time.time() - t0):.0f} ms")
                ok &= r.status_code == 200
            if who == "hospital":
                n = len(c.get(f"{BASE}/api/inventory/matrix", headers=h).json()["facilities"])
                print(f"hospital sees {n} facility (expect 1)")
                ok &= n == 1
        r = c.post(f"{BASE}/api/copilot/chat", headers=h, json={"message": "Which group is most at risk?"})
        print("copilot", r.status_code, r.json().get("fallback"))
        ok &= r.status_code == 200
    print("SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
