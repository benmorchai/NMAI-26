#!/usr/bin/env python3
"""Tripletex AI Agent - NM i AI 2026. Minimal agentic version."""

import json, os, re, logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests as http

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("agent")

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
        m = re.search(r'\{[\s\S]*\}', txt)
        return json.loads(m.group()) if m else {"calls": [], "done": True}
    except Exception as e:
        log.error(f"LLM error: {e}")
        return {"calls": [], "done": True}

def api(session, base, call):
    method, path = call.get("method", "GET"), call.get("path", "")
    try:
        r = getattr(session, method.lower())(f"{base}{path}", params=call.get("params"), json=call.get("body"), timeout=15)
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

    if not base_url or not token or not OR_KEY:
        return JSONResponse({"status": "completed"})

    session = http.Session()
    session.auth = ("0", token)
    session.headers["Content-Type"] = "application/json"

    user_msg = f"Task:\n{prompt}"
    for f in files[:3]:
        user_msg += f"\n\nFile '{f.get('name','?')}':\n{f.get('content','')[:3000]}"

    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}]

    for turn in range(5):
        resp = llm(msgs)
        calls, done = resp.get("calls", []), resp.get("done", True)
        if not calls:
            break
        results = [{"call": f"{c.get('method','?')} {c.get('path','?')}", "result": api(session, base_url, c)} for c in calls]
        msgs.append({"role": "assistant", "content": json.dumps(resp, ensure_ascii=False)})
        msgs.append({"role": "user", "content": json.dumps(results, ensure_ascii=False)[:8000]})
        if done:
            break

    return JSONResponse({"status": "completed"})

@app.get("/")
async def health():
    return {"status": "ok"}
