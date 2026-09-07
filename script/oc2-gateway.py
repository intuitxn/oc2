#!/usr/bin/env python3
"""oc2-gateway — the lean gateway, extracted from what hermes got right.

One process: an HTTP intake on the LAN that accepts jobs from any agent or
human tool, queues them, runs them on the node (sandboxed), and reports state.
Platforms (buzz, discord, ...) become adapters in front of this intake; hermes
still owns the live platform connections today, so this gateway starts as the
node's LAN job surface and grows adapters from there.

Endpoints (token = ~/.opencode2-profiles/work/state/gateway-token):
  POST /job            {task, agent?, dir?, tier?}  -> {"id": ...}
  GET  /job/<id>       -> {"id","state","output"}   states: queued|running|done|error
  GET  /health         -> {"healthy":true,...}

State: ~/.opencode2-profiles/work/state/gateway-state.json (heartbeat, platforms)
Queue: ~/.opencode2-profiles/work/state/gateway-jobs/<id>.json
"""

import json
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE_DIR = os.path.expanduser("~/.opencode2-profiles/work/state")
JOBS_DIR = os.path.join(STATE_DIR, "gateway-jobs")
STATE_FILE = os.path.join(STATE_DIR, "gateway-state.json")
TOKEN_FILE = os.path.join(STATE_DIR, "gateway-token")
AGENT = os.path.expanduser("~/opencode2/script/oc2-agent.sh")
PORT = int(os.environ.get("OC2_GATEWAY_PORT", "4099"))

os.makedirs(JOBS_DIR, exist_ok=True)
TOKEN = ""
if os.path.exists(TOKEN_FILE):
    TOKEN = open(TOKEN_FILE).read().strip()
if not TOKEN:
    TOKEN = uuid.uuid4().hex
    with open(TOKEN_FILE, "w") as f:
        os.chmod(TOKEN_FILE, 0o600)
        f.write(TOKEN)


def load_jobs():
    out = []
    for name in sorted(os.listdir(JOBS_DIR)):
        try:
            out.append(json.load(open(os.path.join(JOBS_DIR, name))))
        except Exception:
            pass
    return out


def save_state():
    st = {
        "kind": "oc2-gateway",
        "gateway_state": "running",
        "pid": os.getpid(),
        "start_time": time.time(),
        "platforms": {
            "lan-http": {"state": "connected"},
            "buzz": {"state": "hermes-owned", "note": "live platform adapter pending owner relay identity"},
        },
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    json.dump(st, open(STATE_FILE, "w"), indent=1)


def worker():
    while True:
        for job in load_jobs():
            if job["state"] == "queued":
                job["state"] = "running"
                job["started"] = time.time()
                json.dump(job, open(job["_path"], "w"), indent=1)
                cmd = ["sh", AGENT, job["task"], "--sandbox"]
                if job.get("agent"):
                    cmd += ["--agent", job["agent"]]
                if job.get("dir"):
                    cmd += ["--dir", job["dir"]]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                    job["state"] = "done" if r.returncode == 0 else "error"
                    job["output"] = (r.stdout + r.stderr)[-8000:]
                except subprocess.TimeoutExpired:
                    job["state"] = "error"
                    job["output"] = "job timed out (900s)"
                except Exception as e:
                    job["state"] = "error"
                    job["output"] = str(e)
                job["finished"] = time.time()
                json.dump(job, open(job["_path"], "w"), indent=1)
                save_state()
        time.sleep(2)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        return self.headers.get("authorization", "") == f"Bearer {TOKEN}"

    def do_GET(self):
        if self.path == "/health":
            clock = 0
            try:
                import sqlite3

                db = sqlite3.connect(os.path.expanduser("~/.opencode2-profiles/work/data/opencode/opencode-local.db"))
                row = db.execute("SELECT value FROM lamport_clock WHERE id = 1").fetchone()
                clock = row[0] if row else 0
            except Exception:
                pass
            return self._json(200, {"healthy": True, "gateway": "oc2", "jobs": len(load_jobs()), "lamport": clock})
        if self.path.startswith("/job/"):
            jid = self.path.split("/job/")[1].split("/")[0]
            path = os.path.join(JOBS_DIR, f"{jid}.json")
            if not os.path.exists(path):
                return self._json(404, {"error": "no such job"})
            job = json.load(open(path))
            return self._json(200, {k: v for k, v in job.items() if not k.startswith("_")})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/job":
            return self._json(404, {"error": "not found"})
        if not self._authed():
            return self._json(401, {"error": "unauthorized"})
        length = int(self.headers.get("content-length", "0"))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad json"})
        task = str(body.get("task", "")).strip()
        if not task:
            return self._json(400, {"error": "task required"})
        jid = uuid.uuid4().hex[:12]
        job = {
            "id": jid,
            "state": "queued",
            "task": task,
            "agent": body.get("agent"),
            "dir": body.get("dir"),
            "tier": body.get("tier", "seatbelt"),
            "created": time.time(),
            "_path": os.path.join(JOBS_DIR, f"{jid}.json"),
        }
        json.dump(job, open(job["_path"], "w"), indent=1)
        save_state()
        return self._json(200, {"id": jid, "state": "queued"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    save_state()
    threading.Thread(target=worker, daemon=True).start()
    print(f"oc2-gateway listening on 0.0.0.0:{PORT} (token in {TOKEN_FILE})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
