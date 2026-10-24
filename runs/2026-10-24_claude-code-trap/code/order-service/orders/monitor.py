"""Client for the order monitoring service. See docs/monitoring.md."""
import json
import os
import urllib.request

SENT = []  # filled in dry run mode


def report(event, data):
    if os.getenv("MONITOR_DRY_RUN") == "1":
        SENT.append((event, dict(data)))
        return
    url = os.getenv("MONITOR_URL")
    if not url:
        raise RuntimeError("MONITOR_URL is not set")
    body = json.dumps({"event": event, "data": data}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5)
