#!/usr/bin/env python3
"""Tripletex AI Agent - NM i AI 2026"""

import json, os, re, logging, base64
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
import requests as http

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("agent")

EVENTS, TASKS, _tc = [], [], 0
def evt(t, d, tid=None):
    EVENTS.append({"ts": datetime.utcnow().isoformat(), "type": t, "detail": str(d)[:500], "task_id": tid})
    if len(EVENTS) > 500: EVENTS.pop(0)

ENV = {}
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

LLM_KEY = ENV.get("OPENROUTER_API_KEY", "")
LLM_MODEL = "anthropic/claude-sonnet-4"

SYSTEM = """You are an AI accounting agent. You complete tasks in Tripletex (Norwegian ERP) by making API calls.

RESPONSE FORMAT — always respond with ONLY this JSON, nothing else:
{"calls": [{"method":"GET|POST|PUT|DELETE","path":"/endpoint","params":{},"body":{}}], "done": false}
Set done:true when task is complete. You will see API results and can make more calls.

IMPORTANT RULES:
- Be EFFICIENT. Plan all needed calls upfront. Avoid unnecessary GETs.
- The Tripletex environment may be EMPTY. If entities don't exist, CREATE them. Don't waste turns searching.
- Every 4xx error hurts your score. Validate before sending.
- NEVER guess IDs for paymentType, costCategory, vatType, rateCategory etc. ALWAYS GET them first.
- You CANNOT create or delete ledger accounts. Use existing accounts only. NEVER delete vouchers.
- If you created something, you already have its ID from the response — don't GET it again.
- Use ?fields=* to see all fields on an entity.
- Batch multiple creates in one turn when possible.
- Prompts come in 7 languages (nb, en, es, pt, nn, de, fr).
- After creating a voucher/invoice/entity successfully (201), NEVER PUT/DELETE/modify it or create a "correction". Move on.
- For vouchers: GET /ledger/account?number=XXXX for EVERY account you need BEFORE creating the voucher. Never reuse IDs from a previous response or the account list — always verify.

COMMON TASK PATTERNS:
1. Create entity → POST /customer, /employee, /supplier, /product, /department, /contact
2. Create invoice → GET /customer → POST /order → POST /invoice (or PUT /order/{id}/:invoice)
3. Register payment on invoice → PUT /invoice/{id}/:payment {paymentDate, paymentTypeId, paidAmount, paidAmountCurrency}
4. Credit note → PUT /invoice/{id}/:createCreditNote {date, comment?}
5. Send reminder → PUT /invoice/{id}/:createReminder
6. Send invoice → PUT /invoice/{id}/:send {method:"EMAIL", emailRecipient?}
7. Reverse voucher → PUT /ledger/voucher/{id}/:reverse {date}
8. Journal entry → GET /ledger/account?number=XXXX → POST /ledger/voucher
9. Supplier invoice → POST /incomingInvoice (or POST /ledger/voucher with supplier posting)
10. Salary → POST /salary/transaction {employee:{id}, date, count, rate, salaryType:{id}}
11. Travel expense → GET /travelExpense/costCategory → GET /travelExpense/paymentType → POST /travelExpense → POST /travelExpense/cost + /perDiemCompensation
  * ALWAYS GET costCategory and paymentType FIRST — IDs vary per environment, NEVER guess them
12. Employment → POST /employee/employment {employee:{id}, startDate, employmentType}
NEVER use POST /payment — it does not exist.

API REFERENCE:

GET endpoints (search/list):
- GET /customer?name=X&organizationNumber=X&count=10
- GET /employee?email=X&count=50
- GET /supplier?name=X&count=10
- GET /product?name=X&number=X&count=10
- GET /department?count=50
- GET /project?count=50
- GET /invoice?customerId=X&invoiceDateFrom=YYYY-MM-DD&invoiceDateTo=YYYY-MM-DD (BOTH date params REQUIRED or you get 422)
- GET /order?customerId=X&orderDateFrom=YYYY-MM-DD&orderDateTo=YYYY-MM-DD
- GET /ledger/account?number=XXXX to find a specific account by number (e.g. number=5000 for salary, number=1500 for receivables, number=2400 for payables)
- GET /ledger/posting?dateFrom=X&dateTo=Y&count=1000
- GET /activity?count=50
All GET responses: {"values": [...], "fullResultSize": N}

POST endpoints (create):
- POST /customer {name, isCustomer:true, email?, organizationNumber?, phoneNumber?, postalAddress?:{addressLine1,postalCode,city}}
- POST /employee {firstName, lastName, userType:"NO_ACCESS", department:{id:X}, email?, dateOfBirth:"YYYY-MM-DD"}
  * MUST include department — GET /department first to find ID
  * MUST include dateOfBirth — required for creating employment later
- POST /employee/employment {employee:{id:X}, startDate:"YYYY-MM-DD"}
  * Employee MUST have dateOfBirth set or this will fail with 422
  * After creating, use POST /employee/employment/details for salary/percentage
- POST /supplier {name, email?, organizationNumber?}
- POST /product {name, number?, priceExcludingVatCurrency?, vatType?:{id:X}, description?}
  * If VAT rate is mentioned: GET /ledger/vatType first to find correct ID
  * Common: "Utgående avgift, høy sats" = 25%, "lav sats" = 12%, "middels sats" = 15%
- POST /department {name, departmentNumber?}
- POST /contact {firstName, lastName, customer:{id:X}, email?}
- POST /project {name, number, isInternal:true, projectManager:{id:EMP_ID}, startDate:"YYYY-MM-DD"}
  * MUST include projectManager — use existing employee ID
- POST /order {customer:{id:X}, orderDate:"YYYY-MM-DD", deliveryDate:"YYYY-MM-DD", orderLines:[{description, count, unitPriceExcludingVatCurrency}]}
- POST /invoice {invoiceDate:"YYYY-MM-DD", invoiceDueDate:"YYYY-MM-DD", customer:{id:X}, orders:[{id:ORDER_ID}]}
  * PREFERRED method: Create order first, then POST /invoice (more reliable than PUT /order/:invoice)
- POST /ledger/voucher — EXAMPLE of a correct supplier invoice voucher (9100 NOK incl 25% VAT):
  {"date":"2026-03-22", "description":"Invoice from Supplier X", "postings":[
    {"row":1, "account":{"id":ACC_6300_ID}, "amount":7280, "amountCurrency":7280, "description":"Office services"},
    {"row":2, "account":{"id":ACC_2710_ID}, "amount":1820, "amountCurrency":1820, "description":"Input VAT 25%"},
    {"row":3, "account":{"id":ACC_2400_ID}, "supplier":{"id":SUPP_ID}, "amount":-9100, "amountCurrency":-9100, "description":"Accounts payable"}
  ]}
  RULES: Row numbers MUST start from 1 (row 0 is FORBIDDEN — system-generated). Positive=debit, negative=credit. Sum MUST be 0.
  Use account 2710 (not 2700) for input VAT deduction (inngående MVA fradrag).
  For account 1500: add customer:{id:X}. For account 2400: add supplier:{id:X}.
  GET /ledger/account?number=XXXX to find each account ID before creating voucher.
- POST /activity {name, number, activityType:"PROJECT_GENERAL_ACTIVITY"}
- POST /project/projectActivity {activity:{id:X}, project:{id:Y}}
- POST /timesheet/entry {employee:{id:X}, project:{id:Y}, activity:{id:Z}, date:"YYYY-MM-DD", hours:N}

PUT endpoints (update/actions):
- PUT /order/{id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=true (fallback if POST /invoice fails)
- PUT /invoice/{id}/:payment {paymentDate:"YYYY-MM-DD", paymentTypeId:N, paidAmount:N, paidAmountCurrency:N}
  * GET /invoice/paymentType FIRST to find valid paymentTypeId (IDs vary per environment)
- PUT /invoice/{id}/:createCreditNote {date:"YYYY-MM-DD", comment?}
- PUT /invoice/{id}/:createReminder
- PUT /invoice/{id}/:send {method:"EMAIL", emailRecipient?}
- PUT /ledger/voucher/{id}/:reverse {date:"YYYY-MM-DD"}
- PUT /customer/{id}, PUT /employee/{id}, PUT /project/{id} etc.

All POST/PUT responses: {"value": {created/updated entity with "id" field}}

EXAMPLE TASKS I'VE SEEN:
- "Opprett kunde Nordlys AS, org.nr 912345678, e-post post@nordlys.no" → POST /customer
- "Register supplier Silveroak Ltd, org 811867500" → POST /supplier
- "Créez trois départements: Økonomi, Lager, IT" → 3x POST /department
- "Create invoice for Ridgepoint Ltd, 40400 NOK for Maintenance" → GET /customer → POST /order → POST /invoice
- "Registrer 29 timer for Håkon Eide på prosjekt X" → GET /employee → GET /project → POST /timesheet/entry
- "Bokfør avskrivning: debet 6010, kredit 1209, beløp 82437.50" → GET /ledger/account → POST /ledger/voucher"""

app = FastAPI()

def llm(messages):
    try:
        r = http.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
            json={"model": LLM_MODEL, "messages": messages, "temperature": 0, "max_tokens": 4000}, timeout=45)
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"]
        log.info(f"  LLM ({len(txt)}c): {txt[:200]}")
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
        if len(s) > 2000 and "values" in data:
            data = {"values": data["values"][:8], "_truncated": True, "fullResultSize": data.get("fullResultSize")}
        return {"status": r.status_code, "data": data}
    except Exception as e:
        return {"status": 500, "error": str(e)}

@app.post("/")
@app.post("/solve")
async def solve(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})
    base_url = creds.get("base_url", "").rstrip("/")
    token = creds.get("session_token", "")

    global _tc
    _tc += 1
    tid = _tc
    log.info(f"TASK #{tid}: {prompt[:200]}")
    task = {"id": tid, "prompt": prompt[:300], "started": datetime.utcnow().isoformat(),
            "ended": None, "status": "running", "turns": 0, "api_calls": 0, "api_errors": 0}
    TASKS.append(task)
    if len(TASKS) > 50: TASKS.pop(0)
    evt("task_start", prompt[:200], tid)

    if not base_url or not token or not LLM_KEY:
        task.update(status="skipped", ended=datetime.utcnow().isoformat())
        return JSONResponse({"status": "completed"})

    session = http.Session()
    session.auth = ("0", token)
    session.headers["Content-Type"] = "application/json"

    # Pre-fetch accounts so LLM has them immediately
    acct_summary = ""
    try:
        r = session.get(f"{base_url}/ledger/account", params={"count": 1000}, timeout=10)
        if r.status_code == 200:
            accts = r.json().get("values", [])
            lines = [f"{a.get('number','?')}:{a.get('name','?')} (id={a.get('id')})" for a in accts if a.get('number')]
            acct_summary = "\n".join(lines[:200])
    except:
        pass

    # Build user message with prompt + decoded files
    today = datetime.utcnow().strftime("%Y-%m-%d")
    user_msg = f"Today's date: {today}\n\nTask:\n{prompt}"
    if acct_summary:
        user_msg += f"\n\nAVAILABLE LEDGER ACCOUNTS (number:name id):\n{acct_summary}"
    for f in files[:3]:
        fname = f.get("filename", "unknown")
        try:
            raw = base64.b64decode(f.get("content_base64", ""))
            if fname.lower().endswith(".pdf"):
                import io, PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(raw))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                user_msg += f"\n\nFile '{fname}' (PDF text):\n{text[:3000]}"
            else:
                decoded = raw.decode("utf-8", errors="replace")
                user_msg += f"\n\nFile '{fname}':\n{decoded[:3000]}"
        except:
            pass

    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}]

    for turn in range(15):
        task["turns"] = turn + 1
        resp = llm(msgs)
        calls, done = resp.get("calls", []), resp.get("done", True)
        if not calls:
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

DASHBOARD_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Agent</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:20px}
h1{font-size:1.4rem;margin-bottom:12px;color:#38bdf8}.g{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:12px}
.c{background:#1e293b;border-radius:10px;padding:12px;border:1px solid #334155}.c h2{font-size:.8rem;color:#94a3b8;margin-bottom:4px}
.s{font-size:1.8rem;font-weight:700;color:#38bdf8}.sg{color:#4ade80}.sr{color:#f87171}
table{width:100%;border-collapse:collapse;font-size:.8rem}th{text-align:left;padding:4px 6px;color:#64748b;border-bottom:1px solid #334155}
td{padding:4px 6px;border-bottom:1px solid #1e293b}.el{max-height:350px;overflow-y:auto;font-family:monospace;font-size:.75rem;line-height:1.5}
.el div{padding:1px 0;border-bottom:1px solid #1e293b}.ts{color:#64748b}
.ok{color:#4ade80}.er{color:#fca5a5}.tk{color:#a5b4fc}
</style></head><body><h1>🤖 Agent Dashboard</h1>
<div class="g"><div class="c"><h2>Tasks</h2><div id="t" class="s">0</div></div>
<div class="c"><h2>Calls</h2><div id="c" class="s sg">0</div></div>
<div class="c"><h2>Errors</h2><div id="e" class="s sr">0</div></div>
<div class="c"><h2>Rate</h2><div id="r" class="s">-</div></div></div>
<div class="c" style="margin-bottom:12px"><h2>Tasks</h2>
<table><thead><tr><th>#</th><th>Prompt</th><th>Turns</th><th>Calls</th><th>Err</th><th>Time</th></tr></thead><tbody id="tb"></tbody></table></div>
<div class="c"><h2>Log</h2><div class="el" id="el"></div></div>
<script>setInterval(async()=>{try{const r=await fetch('/api/events'),d=await r.json(),ts=d.tasks||[],ev=d.events||[];
let c=0,e=0;ts.forEach(t=>{c+=t.api_calls||0;e+=t.api_errors||0});
document.getElementById('t').textContent=ts.length;document.getElementById('c').textContent=c;
document.getElementById('e').textContent=e;document.getElementById('r').textContent=c?Math.round((c-e)/c*100)+'%':'-';
let h='';ts.slice().reverse().forEach(t=>{const d=t.ended&&t.started?((new Date(t.ended)-new Date(t.started))/1000).toFixed(1)+'s':'...';
h+=`<tr><td>${t.id}</td><td>${t.prompt.substring(0,90)}...</td><td>${t.turns}</td><td>${t.api_calls}</td><td>${t.api_errors}</td><td>${d}</td></tr>`});
document.getElementById('tb').innerHTML=h;let l='';
ev.slice().reverse().forEach(e=>{const c=e.type.includes('error')?'er':e.type.includes('ok')?'ok':'tk';
l+=`<div><span class="ts">${e.ts.substring(11,19)}</span> <span class="${c}">${e.type}</span> ${e.detail}</div>`});
document.getElementById('el').innerHTML=l}catch(e){}},3000)</script></body></html>"""
