#!/usr/bin/env python3
"""
Tripletex AI Accounting Agent - NM i AI 2026
v4: Simple agentic loop - LLM decides API calls, sees results, acts again.
"""

import json
import logging
import os
import re
import traceback
from datetime import datetime
from pathlib import Path

import requests as http_requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("tripletex-agent")

ENV = {}
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

OPENROUTER_KEY = ENV.get("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))

app = FastAPI(title="Tripletex AI Agent", version="4.0.0")

SYSTEM_PROMPT = """You are an accounting agent that executes tasks in Tripletex (Norwegian ERP) via its REST API.
You will receive an accounting task and must complete it by making API calls.

## How to respond
Return a JSON object with a list of API calls to execute:
```json
{"calls": [{"method": "GET|POST|PUT|DELETE", "path": "/endpoint", "params": {}, "body": {}}], "done": false}
```

When you need to see results before continuing, set "done": false. You'll receive the results and can make more calls.
When the task is complete, set "done": true.

## Key Tripletex API patterns
- Auth is handled for you (Basic Auth with session token)
- Base URL is handled - just specify the path (e.g. "/customer")
- GET responses have: {"values": [...]} for lists, {"value": {...}} for single items
- POST/PUT responses have: {"value": {...}} with created/updated entity
- Use query params for filtering: GET /customer?name=Acme&count=10
- Pagination: ?from=0&count=100

## Common endpoints you WILL need:

### READ data (GET)
- GET /customer?name=X&count=10 — search customers
- GET /employee?count=10 — list employees
- GET /product?name=X&number=Y — search products
- GET /supplier?name=X — search suppliers
- GET /invoice?customerId=X&count=20 — list invoices
- GET /order?customerId=X — list orders
- GET /department — list departments
- GET /ledger/account?count=500 — list chart of accounts
- GET /ledger/posting?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD&count=1000 — general ledger postings
- GET /ledger/voucher?dateFrom=X&dateTo=Y — list vouchers
- GET /project?count=50 — list projects
- GET /project/{id}/activity — list project activities

### CREATE data (POST)
- POST /customer — body: {name, email?, organizationNumber?, phoneNumber?, isCustomer: true}
- POST /employee — body: {firstName, lastName, userType: "NO_ACCESS", department: {id: X}, email?, dateOfBirth?}
  * IMPORTANT: Always include department (GET /department first to find id) and userType: "NO_ACCESS"
- POST /product — body: {name, number?, priceExcludingVatCurrency?, description?}
- POST /supplier — body: {name, email?, organizationNumber?}
- POST /contact — body: {firstName, lastName, customer: {id: X}, email?}
- POST /department — body: {name, departmentNumber?}
- POST /project — body: {name, number, isInternal: true, projectManager: {id: EMPLOYEE_ID}}
  * IMPORTANT: Always include projectManager (GET /employee first to find an id)
- POST /order — body: {customer: {id: X}, orderDate: "YYYY-MM-DD", deliveryDate: "YYYY-MM-DD", orderLines: [{description, count, unitPriceExcludingVatCurrency}]}
- POST /activity — body: {name, number, activityType: "PROJECT_GENERAL_ACTIVITY"}
  * Then link to project: POST /project/projectActivity — body: {activity: {id: ACT_ID}, project: {id: PROJ_ID}}

### INVOICING
- PUT /order/{id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=false — invoice an order

### JOURNAL ENTRIES / VOUCHERS
- POST /ledger/voucher — body: {date: "YYYY-MM-DD", description: "...", postings: [{row: 1, account: {id: ACCT_ID}, amount: X, amountCurrency: X, amountGross: X, amountGrossCurrency: X, description: "..."}]}
  * CRITICAL: Each posting needs row, amount, amountCurrency, amountGross, amountGrossCurrency (all same value)
  * Positive amount = debit, negative = credit
  * Total must balance to 0
  * Look up account IDs first with GET /ledger/account
  * For postings to account 1500 (Kundefordringer), include customer: {id: X}
  * For postings to account 2400 (Leverandørgjeld), include supplier: {id: X}

## Strategy
1. ALWAYS start by reading relevant data (GET) to understand the current state
2. Then create/update entities based on what you found
3. For complex tasks, break into steps: read → analyze → act
4. Use IDs from previous responses in subsequent calls

## Important
- Dates must be YYYY-MM-DD format
- The task may be in Norwegian, English, German, Spanish, Portuguese, French, or Nynorsk
- Be precise with amounts and account numbers from the prompt
- When creating employees, ALWAYS get department first
- When creating projects, ALWAYS get an employee first for projectManager"""


def call_llm(messages: list) -> dict:
    """Call LLM and parse JSON response."""
    try:
        r = http_requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": messages,
                "temperature": 0,
                "max_tokens": 4000,
            },
            timeout=45,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        logger.info(f"  LLM: {content[:400]}")

        # Extract JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
        return {"calls": [], "done": True}
    except Exception as e:
        logger.error(f"  LLM error: {e}")
        return {"calls": [], "done": True}


def execute_api_call(session, base_url: str, call: dict) -> dict:
    """Execute a single API call against Tripletex."""
    method = call.get("method", "GET").upper()
    path = call.get("path", "")
    params = call.get("params", {})
    body = call.get("body", None)

    url = f"{base_url}{path}"

    try:
        if method == "GET":
            r = session.get(url, params=params, timeout=15)
        elif method == "POST":
            r = session.post(url, json=body, timeout=15)
        elif method == "PUT":
            r = session.put(url, json=body, params=params, timeout=15)
        elif method == "DELETE":
            r = session.delete(url, timeout=15)
        else:
            return {"status": 400, "error": f"Unknown method: {method}"}

        logger.info(f"  {method} {path}: {r.status_code}")

        result = {"status": r.status_code}
        try:
            resp_json = r.json()
            # Truncate large responses to save context
            resp_str = json.dumps(resp_json, ensure_ascii=False)
            if len(resp_str) > 3000:
                # For large GET responses, keep just first few items
                if "values" in resp_json:
                    values = resp_json["values"]
                    result["data"] = {"values": values[:15], "totalCount": len(values)}
                else:
                    result["data"] = json.loads(resp_str[:3000] + "...")
            else:
                result["data"] = resp_json
        except:
            result["text"] = r.text[:500]

        if r.status_code >= 400:
            logger.error(f"    Error: {r.text[:300]}")

        return result
    except Exception as e:
        logger.error(f"    Exception: {e}")
        return {"status": 500, "error": str(e)}


async def handle_solve(body: dict) -> JSONResponse:
    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})
    base_url = creds.get("base_url", "").rstrip("/")
    session_token = creds.get("session_token", "")

    logger.info("=" * 70)
    logger.info("TASK RECEIVED")
    logger.info(f"  Prompt: {prompt[:500]}")
    logger.info(f"  Files: {len(files)}")
    logger.info(f"  Base URL: {base_url}")
    logger.info("=" * 70)

    if not base_url or not session_token:
        return JSONResponse({"status": "completed"})

    # Set up Tripletex session
    session = http_requests.Session()
    session.auth = ("0", session_token)
    session.headers["Content-Type"] = "application/json"

    # Build initial user message
    user_msg = f"Complete this accounting task:\n\n{prompt}"
    if files:
        for f in files[:3]:
            user_msg += f"\n\nFile '{f.get('name', '?')}':\n{f.get('content', '')[:3000]}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    # Agent loop: LLM plans → execute → feed results → repeat
    max_turns = 5
    total_calls = 0

    for turn in range(max_turns):
        logger.info(f"\n[TURN {turn + 1}/{max_turns}]")

        response = call_llm(messages)
        calls = response.get("calls", [])
        is_done = response.get("done", False)

        if not calls and is_done:
            logger.info("  LLM says done (no more calls)")
            break

        if not calls:
            logger.info("  No calls returned, finishing")
            break

        # Execute all calls and collect results
        results = []
        for j, call in enumerate(calls):
            logger.info(f"  Call {j+1}/{len(calls)}: {call.get('method', '?')} {call.get('path', '?')}")
            result = execute_api_call(session, base_url, call)
            results.append({
                "call": f"{call.get('method', '?')} {call.get('path', '?')}",
                "result": result
            })
            total_calls += 1

        # Feed results back to LLM
        results_msg = json.dumps(results, ensure_ascii=False, default=str)
        # Truncate if too long
        if len(results_msg) > 8000:
            results_msg = results_msg[:8000] + "\n...(truncated)"

        messages.append({"role": "assistant", "content": json.dumps(response, ensure_ascii=False)})
        messages.append({"role": "user", "content": f"API results:\n{results_msg}\n\nContinue with next steps, or set done=true if the task is complete."})

        if is_done:
            logger.info("  LLM marked done after this batch")
            break

    logger.info(f"\n{'='*70}")
    logger.info(f"TASK COMPLETE — {total_calls} API calls across {min(turn+1, max_turns)} turns")
    logger.info(f"{'='*70}")

    return JSONResponse({"status": "completed"})


# ── Routes ─────────────────────────────────────────────────────
@app.get("/")
async def health():
    return {"status": "ok", "service": "tripletex-ai-agent", "version": "4.0.0"}

@app.post("/")
async def solve_root(request: Request):
    return await handle_solve(await request.json())

@app.post("/solve")
async def solve(request: Request):
    return await handle_solve(await request.json())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
