#!/usr/bin/env python3
"""Tripletex AI Agent - NM i AI 2026. Minimal agentic version."""

import json, os, re, logging, time
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
import requests as http

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("agent")

# In-memory event log for dashboard
EVENTS = []  # [{ts, type, detail, task_id}]
TASKS = []   # [{id, prompt, started, ended, status, turns, api_calls, api_errors, events}]
_task_counter = 0

def evt(type, detail, task_id=None):
    EVENTS.append({"ts": datetime.utcnow().isoformat(), "type": type, "detail": str(detail)[:500], "task_id": task_id})
    if len(EVENTS) > 500: EVENTS.pop(0)

ENV = {}
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

OR_KEY = ENV.get("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
OR_MODEL = "anthropic/claude-sonnet-4"

SYSTEM = """You are an accounting agent for Tripletex (Norwegian ERP).
You receive a task and must complete it by returning API calls to execute.

Return JSON: {"calls": [{"method":"GET|POST|PUT","path":"/endpoint","params":{},"body":{}}], "done": false}
Set done=true when finished. You'll see results and can make more calls.

Key endpoints:
- GET /customer, /employee, /product, /supplier, /department, /invoice, /order, /project
- GET /ledger/account?count=500, /ledger/posting?dateFrom=X&dateTo=Y&count=1000
- POST /customer {name, isCustomer:true, email?, organizationNumber?}
- POST /employee {firstName, lastName, userType:"NO_ACCESS", department:{id:X}}
- POST /product {name, number?, priceExcludingVatCurrency?}
- POST /supplier {name, email?, organizationNumber?}
- POST /department {name}, POST /contact {firstName, lastName, customer:{id:X}}
- POST /project {name, number, isInternal:true, projectManager:{id:EMP_ID}, startDate:"YYYY-MM-DD"}
- POST /activity {name, number, activityType:"PROJECT_GENERAL_ACTIVITY"} then POST /project/projectActivity {activity:{id:X}, project:{id:Y}}
- POST /order {customer:{id:X}, orderDate, deliveryDate, orderLines:[{description, count, unitPriceExcludingVatCurrency}]}
- PUT /order/{id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=false
- POST /ledger/voucher {date, description, postings:[{row:N, account:{id:X}, amount:N, amountCurrency:N, amountGross:N, amountGrossCurrency:N, description}]} (positive=debit, negative=credit, must balance)

Always GET first to find IDs. Employee needs department. Project needs projectManager (employee). Voucher account needs ID from GET /ledger/account."""

app = FastAPI()

def llm(messages):
    try:
        r = http.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
            json={"model": OR_MODEL, "messages": messages, "temperature": 0, "max_tokens": 4000}, timeout=45)
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"]
        # Find JSON block - try ```json``` fences first, then raw braces
        fence = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', txt)
        if fence:
            return json.loads(fence.group(1))
        # Try each { as potential start, find matching }
        for i, ch in enumerate(txt):
            if ch == '{':
                depth, j = 0, i
                while j < len(txt):
                    if txt[j] == '{': depth += 1
                    elif txt[j] == '}': depth -= 1
                    if depth == 0:
                        try: return json.loads(txt[i:j+1])
                        except: break
                    j += 1
        return {"calls": [], "done": True}
    except Exception as e:
        log.error(f"LLM error: {e}")
        return {"calls": [], "done": True}

def api(session, base, call):
    method, path = call.get("method", "GET"), call.get("path", "")
    try:
        url = f"{base}{path}"
        if method == "GET":
            r = session.get(url, params=call.get("params"), timeout=15)
        else:
            r = getattr(session, method.lower())(url, params=call.get("params"), json=call.get("body"), timeout=15)
        log.info(f"  {method} {path}: {r.status_code}")
        data = r.json()
        s = json.dumps(data, ensure_ascii=False)
        if len(s) > 3000 and "values" in data:
            data = {"values": data["values"][:15], "_truncated": True}
        return {"status": r.status_code, "data": data}
    except Exception as e:
        return {"status": 500, "error": str(e)}

@app.post("/")
@app.post("/solve")
async def solve(request: Request):
    body = await request.json()
    prompt, files, creds = body.get("prompt", ""), body.get("files", []), body.get("tripletex_credentials", {})
    base_url, token = creds.get("base_url", "").rstrip("/"), creds.get("session_token", "")
    log.info(f"TASK: {prompt[:200]}")

    global _task_counter
    _task_counter += 1
    tid = _task_counter
    task = {"id": tid, "prompt": prompt[:300], "started": datetime.utcnow().isoformat(), "ended": None,
            "status": "running", "turns": 0, "api_calls": 0, "api_errors": 0, "events": []}
    TASKS.append(task)
    if len(TASKS) > 50: TASKS.pop(0)
    evt("task_start", prompt[:200], tid)

    if not base_url or not token or not OR_KEY:
        task.update(status="skipped", ended=datetime.utcnow().isoformat())
        evt("task_skip", "missing credentials", tid)
        return JSONResponse({"status": "completed"})

    session = http.Session()
    session.auth = ("0", token)
    session.headers["Content-Type"] = "application/json"

    user_msg = f"Task:\n{prompt}"
    for f in files[:3]:
        user_msg += f"\n\nFile '{f.get('name','?')}':\n{f.get('content','')[:3000]}"

    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}]

    for turn in range(15):
        task["turns"] = turn + 1
        resp = llm(msgs)
        calls, done = resp.get("calls", []), resp.get("done", True)
        if not calls:
            evt("llm_done", f"turn {turn+1}, no more calls", tid)
            break
        results = []
        for c in calls:
            r = api(session, base_url, c)
            tag = f"{c.get('method','?')} {c.get('path','?')}"
            results.append({"call": tag, "result": r})
            task["api_calls"] += 1
            if r.get("status", 0) >= 400:
                task["api_errors"] += 1
                evt("api_error", f"{tag} → {r['status']}", tid)
            else:
                evt("api_ok", f"{tag} → {r['status']}", tid)
        msgs.append({"role": "assistant", "content": json.dumps(resp, ensure_ascii=False)})
        msgs.append({"role": "user", "content": json.dumps(results, ensure_ascii=False)[:8000]})
        if done:
            evt("llm_done", f"turn {turn+1}, marked done", tid)
            break

    task.update(status="completed", ended=datetime.utcnow().isoformat())
    evt("task_end", f"turns={task['turns']} calls={task['api_calls']} errors={task['api_errors']}", tid)
    return JSONResponse({"status": "completed"})

@app.get("/")
async def health():
    return {"status": "ok"}

@app.get("/api/events")
async def get_events():
    return {"tasks": TASKS[-20:], "events": EVENTS[-100:]}

@app.get("/dashboard")
async def dashboard():
    return HTMLResponse(DASHBOARD_HTML)

DASHBOARD_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Tripletex Agent Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}
h1{font-size:1.5rem;margin-bottom:16px;color:#38bdf8}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.card{background:#1e293b;border-radius:12px;padding:16px;border:1px solid #334155}
.card h2{font-size:.9rem;color:#94a3b8;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px}
.stat{font-size:2rem;font-weight:700;color:#38bdf8}
.stat.green{color:#4ade80}.stat.red{color:#f87171}.stat.yellow{color:#facc15}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th{text-align:left;padding:6px 8px;color:#64748b;border-bottom:1px solid #334155}
td{padding:6px 8px;border-bottom:1px solid #1e293b}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}
.tag-ok{background:#065f46;color:#6ee7b7}.tag-err{background:#7f1d1d;color:#fca5a5}
.tag-run{background:#1e3a5f;color:#7dd3fc}.tag-done{background:#334155;color:#94a3b8}
.tag-task{background:#312e81;color:#a5b4fc}
.event-log{max-height:400px;overflow-y:auto;font-family:monospace;font-size:.8rem;line-height:1.6}
.event-log div{padding:2px 0;border-bottom:1px solid #1e293b}
.ts{color:#64748b}.type{font-weight:600}
.pulse{animation:pulse 2s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
#status{font-size:.8rem;color:#64748b}
</style></head><body>
<h1>🤖 Tripletex Agent Dashboard <span id="status" class="pulse">● live</span></h1>
<div class="grid">
  <div class="card"><h2>Tasks Completed</h2><div id="s-tasks" class="stat">0</div></div>
  <div class="card"><h2>API Calls</h2><div id="s-calls" class="stat green">0</div></div>
  <div class="card"><h2>API Errors</h2><div id="s-errors" class="stat red">0</div></div>
  <div class="card"><h2>Success Rate</h2><div id="s-rate" class="stat yellow">-</div></div>
</div>
<div class="card" style="margin-bottom:16px">
  <h2>Recent Tasks</h2>
  <table><thead><tr><th>#</th><th>Prompt</th><th>Status</th><th>Turns</th><th>API</th><th>Errors</th><th>Time</th></tr></thead>
  <tbody id="tasks"></tbody></table>
</div>
<div class="card">
  <h2>Event Log</h2>
  <div class="event-log" id="events"></div>
</div>
<script>
async function refresh(){
  try{
    const r=await fetch('/api/events');const d=await r.json();
    const tasks=d.tasks||[],events=d.events||[];
    let tc=tasks.length,calls=0,errs=0;
    tasks.forEach(t=>{calls+=t.api_calls||0;errs+=t.api_errors||0});
    document.getElementById('s-tasks').textContent=tc;
    document.getElementById('s-calls').textContent=calls;
    document.getElementById('s-errors').textContent=errs;
    document.getElementById('s-rate').textContent=calls>0?Math.round((calls-errs)/calls*100)+'%':'-';
    let th='';
    tasks.slice().reverse().forEach(t=>{
      const dur=t.ended&&t.started?((new Date(t.ended)-new Date(t.started))/1000).toFixed(1)+'s':'...';
      const cls=t.status==='running'?'tag-run':'tag-done';
      th+=`<tr><td>${t.id}</td><td>${t.prompt.substring(0,80)}...</td><td><span class="tag ${cls}">${t.status}</span></td><td>${t.turns}</td><td>${t.api_calls}</td><td>${t.api_errors}</td><td>${dur}</td></tr>`;
    });
    document.getElementById('tasks').innerHTML=th;
    let eh='';
    events.slice().reverse().forEach(e=>{
      const cls=e.type.includes('error')?'tag-err':e.type.includes('ok')?'tag-ok':e.type.includes('task')?'tag-task':'tag-done';
      eh+=`<div><span class="ts">${e.ts.substring(11,19)}</span> <span class="tag ${cls} type">${e.type}</span> ${e.detail}</div>`;
    });
    document.getElementById('events').innerHTML=eh;
    document.getElementById('status').textContent='● live';
  }catch(e){document.getElementById('status').textContent='● offline';}
}
refresh();setInterval(refresh,3000);
</script></body></html>"""
