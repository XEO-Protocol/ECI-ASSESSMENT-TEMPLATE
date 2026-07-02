"""Minimal external agent using the pull (polling) integration.

Run the backend, then:  python examples/example_agent.py

It polls for events awaiting assessment, "inspects" the snapshot bytes
(a real agent would pass them to a vision model or a multimodal LLM),
and submits a hedged, advisory assessment. Swap `assess()` for a real
model call to build a genuine monitoring agent.
"""

import time

import httpx

BASE = "http://127.0.0.1:8765"

RISK_BY_SEVERITY = {"info": "none", "warning": "low", "alert": "medium"}


def assess(payload: dict, snapshot: bytes | None) -> dict:
    event = payload["event"]
    looked = f"reviewed a {len(snapshot)}-byte snapshot" if snapshot else "no snapshot available"
    return {
        "event_id": event["id"],
        "agent_name": "example-agent",
        "summary": (
            f"Automated second look ({looked}): the situation appears "
            f"consistent with '{event['type']}', but this may be a false "
            "alarm. A human should review the snapshot."
        ),
        "risk_level": RISK_BY_SEVERITY.get(event["severity"], "low"),
        "recommended_action": "Please review the event snapshot in the app.",
        "requires_user_confirmation": True,
    }


def main() -> None:
    print(f"Polling {BASE}/api/agent/pending — Ctrl+C to stop")
    while True:
        try:
            pending = httpx.get(f"{BASE}/api/agent/pending", timeout=10).json()
            for payload in pending:
                snapshot = None
                if payload.get("snapshot_url"):
                    snapshot = httpx.get(payload["snapshot_url"], timeout=10).content
                assessment = assess(payload, snapshot)
                httpx.post(payload["assessment_url"], json=assessment, timeout=10)
                print(f"assessed {payload['event']['id']} ({payload['event']['type']})")
        except httpx.HTTPError as exc:
            print(f"backend not reachable: {exc}")
        time.sleep(5)


if __name__ == "__main__":
    main()
