#!/usr/bin/env python3
"""Local UI preview with explicitly labelled sample data. No app writes or model calls."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import evaluate, normalize_task

TITLES = ["Finalize onboarding flow", "Check payment retry behaviour", "Approve launch artwork", "Publish API migration guide",
          "Review mobile checkout", "Confirm release checklist", "Close feedback loop", "Sign off accessibility fixes",
          "Prepare customer announcement", "Complete integration tests", "Update help centre", "Review signup analytics"]


def sample_rows():
    today = datetime.now(timezone.utc)
    rows = []
    for i, title in enumerate(TITLES):
        due = today + timedelta(days=(i % 7) - 3)
        task = {"id": i + 1, "title": title, "project_id": (i % 3) + 1, "owner_id": i % 4,
                "column_id": 1, "date_due": int(due.timestamp()), "priority": i % 3,
                "time_estimated": [2, 4, 3, 6][i % 4], "is_active": "1"}
        rows.append(normalize_task(task, ["Website launch", "Mobile app", "Developer platform"][i % 3],
                                   {"1": "Alex", "2": "Maya", "3": "Sam"}, {"1": "In progress"}))
    return rows


HTML = '''<!doctype html><html><head><meta charset="utf-8"><title>Graft · renderer preview</title>
<style>body{margin:0;background:#f1f2ee;color:#30372d;font:15px -apple-system,sans-serif}aside{width:220px;padding:28px}h1{font-size:24px}p{line-height:1.6;color:#66715e}select{padding:10px;width:100%;margin:10px 0}small{font-size:12px}.tag{font-size:11px;letter-spacing:1px;background:#e0e7d7;padding:8px;display:inline-block;border-radius:6px}</style></head>
<body><aside><span class="tag">DEVELOPMENT PREVIEW</span><h1>Graft</h1><p>This page previews the real renderer using sample records. It is not connected to Kanboard or a model.</p><label>Example feature<select id="example"><option value="release-room">Release room</option><option value="unassigned">Unassigned queue</option></select></label><p id="status"><small>Action proposals appear here. No app records can be changed in this preview.</small></p></aside>
<script src="/renderer.js"></script><script>
async function load(){const p=await(await fetch('/packet?example='+document.querySelector('#example').value)).json();graftMountV1(p,{clientId:'preview',preview:true});}
document.querySelector('#example').addEventListener('change',()=>{window.__graftV1?.remove();load()});load();
setInterval(()=>{const events=window.__graftV1?.drain()||[];if(events.length)document.querySelector('#status').textContent='Preview only: '+JSON.stringify(events[0]);},1000);
setInterval(load,6000);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/": body, kind = HTML.encode(), "text/html; charset=utf-8"
        elif self.path == "/renderer.js": body, kind = (ROOT / "desktop/renderer.js").read_bytes(), "text/javascript; charset=utf-8"
        elif self.path.startswith("/packet"):
            spec = json.loads((ROOT / "examples/release-room.json").read_text())
            if "example=unassigned" in self.path:
                spec["title"] = "Give every task an owner"
                spec["description"] = "An assignment queue assembled from the same reusable engine."
                spec["query"]["filters"] = [{"field": "owner_id", "op": "eq", "value": 0}]
                spec["widgets"] = [spec["widgets"][0], spec["widgets"][2]]
                spec["widgets"][1]["group_by"] = "project"
            origin = f"http://127.0.0.1:{self.server.server_port}"
            packet = {"id": "preview", "revision": 1, "origin": origin, "app_url": origin,
                      "view": evaluate(spec, sample_rows()), "assignable": {str(i): {"1": "Alex", "2": "Maya", "3": "Sam"} for i in range(1, 4)}}
            body, kind = json.dumps(packet).encode(), "application/json"
        else: self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8461); args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Graft renderer preview (sample data): http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()
