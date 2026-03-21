#!/usr/bin/env python3
"""
Tripletex AI Accounting Agent - NM i AI 2026 v3

Uses OpenRouter (Claude Sonnet) to interpret accounting prompts
and execute Tripletex API calls with error recovery.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("tripletex-agent")

# --- Config ---
ENV_FILE = Path(__file__).parent.parent / ".env"


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


ENV = load_env()
OPENROUTER_API_KEY = ENV.get("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
LLM_MODEL = "anthropic/claude-sonnet-4"

app = FastAPI(title="Tripletex AI Agent", version="0.3.0")


# ============================================================
# TRIPLETEX API CLIENT
# ============================================================

class TripletexClient:
    def __init__(self, base_url: str, session_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = ("0", session_token)
        self.session.headers["Content-Type"] = "application/json"
        self.call_count = 0
        self.errors = 0
        self.log = []  # Full request/response log for LLM error recovery

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def get(self, path: str, params: dict = None) -> dict:
        self.call_count += 1
        url = self._url(path)
        logger.info(f"  GET {path} params={params}")
        try:
            resp = self.session.get(url, params=params, timeout=30)
        except Exception as e:
            logger.error(f"  GET EXCEPTION: {e}")
            self.errors += 1
            return {"status_code": 500, "body": {}, "error": str(e)}
        result = self._handle_response(resp, "GET", path)
        return result

    def post(self, path: str, data: dict) -> dict:
        self.call_count += 1
        url = self._url(path)
        logger.info(f"  POST {path}")
        logger.info(f"    Body: {json.dumps(data, ensure_ascii=False)[:800]}")
        try:
            resp = self.session.post(url, json=data, timeout=30)
        except Exception as e:
            logger.error(f"  POST EXCEPTION: {e}")
            self.errors += 1
            return {"status_code": 500, "body": {}, "error": str(e)}
        result = self._handle_response(resp, "POST", path, data)
        return result

    def put(self, path: str, data: dict) -> dict:
        self.call_count += 1
        url = self._url(path)
        logger.info(f"  PUT {path}")
        logger.info(f"    Body: {json.dumps(data, ensure_ascii=False)[:800]}")
        try:
            resp = self.session.put(url, json=data, timeout=30)
        except Exception as e:
            logger.error(f"  PUT EXCEPTION: {e}")
            self.errors += 1
            return {"status_code": 500, "body": {}, "error": str(e)}
        result = self._handle_response(resp, "PUT", path, data)
        return result

    def _handle_response(self, resp, method, path, sent_data=None):
        try:
            body = resp.json() if resp.text else {}
        except Exception:
            body = {"raw": resp.text[:500]}

        if resp.status_code >= 400:
            self.errors += 1
            error_msg = ""
            if isinstance(body, dict):
                error_msg = body.get("message", "")
                validations = body.get("validationMessages", [])
                if validations:
                    error_msg += " | Validations: " + json.dumps(validations, ensure_ascii=False)
            logger.error(f"  {method} {path} → {resp.status_code}: {error_msg[:500]}")
            entry = {
                "method": method, "path": path,
                "status": resp.status_code, "error": error_msg,
                "sent_data": sent_data,
            }
        else:
            logger.info(f"  {method} {path} → {resp.status_code} OK")
            # Extract created ID
            created_id = None
            if isinstance(body, dict):
                val = body.get("value", body)
                if isinstance(val, dict):
                    created_id = val.get("id")
            if created_id:
                logger.info(f"    Created ID: {created_id}")
            entry = {
                "method": method, "path": path,
                "status": resp.status_code, "created_id": created_id,
            }

        self.log.append(entry)
        return {"status_code": resp.status_code, "body": body}


# ============================================================
# LLM CLIENT
# ============================================================

SYSTEM_PROMPT = """You are an AI accounting assistant that executes tasks in Tripletex (Norwegian accounting software).
You receive a task prompt (in Norwegian, English, Spanish, Portuguese, Nynorsk, German, or French) and must return the exact Tripletex API calls needed.

## IMPORTANT API REFERENCE

### POST /employee
Create an employee. Key fields:
- firstName (string, REQUIRED in practice)
- lastName (string, REQUIRED in practice)
- email (string)
- dateOfBirth (string, YYYY-MM-DD)
- phoneNumberMobile (string)
- nationalIdentityNumber (string, 11 digits for Norwegian)
- bankAccountNumber (string)
- address: {"addressLine1": "...", "postalCode": "...", "city": "..."}
- startDate (string, YYYY-MM-DD) — NOTE: this field goes on Employment, not Employee
- isContact (boolean, set false for employees)

After creating employee, you MUST create an employment record:

### POST /employee/employment
- employee: {"id": $employee_id}
- startDate (string, YYYY-MM-DD, REQUIRED) — use the start date from the prompt, or "2026-01-01" as default
- employmentType: "ORDINARY" (or "MARITIME", "FREELANCE")
- percentageOfFullTimeEquivalent: 100.0
- workingHoursScheme: "STANDARD"

Then create employment details:

### POST /employee/employment/details
- employment: {"id": $employment_id}
- date: same as startDate (YYYY-MM-DD, REQUIRED)
- employmentType: "ORDINARY"
- maritimeEmployment: {"shipRegister": "NIS", "shipType": "OTHER", "tradeArea": "OTHER"}
- remunerationType: "MONTHLY_WAGE"
- workingHoursScheme: "STANDARD"
- percentageOfFullTimeEquivalent: 100.0
- occupationCode: {"id": 7} — default office worker

### POST /customer
- name (string, REQUIRED in practice)
- email (string)
- phoneNumber (string)
- phoneNumberMobile (string)
- organizationNumber (string)
- isPrivateIndividual (boolean)
- postalAddress: {"addressLine1": "...", "postalCode": "...", "city": "..."}
- language: "NO" or "EN"
- invoiceEmail (string)
- isSupplier: false (unless they are also a supplier)

### POST /supplier
- name (string, REQUIRED)
- email, phoneNumber, organizationNumber, postalAddress (same as customer)

### POST /product
- name (string, REQUIRED)
- number (string) — product number/code
- priceExcludingVatCurrency (number)
- priceIncludingVatCurrency (number)
- vatType: {"id": 3} for 25% MVA, {"id": 6} for 0%, {"id": 5} for 15% food
- productUnit: {"id": 1} for stk/pieces, {"id": 5} for timer/hours
- account: {"id": X} — revenue account, default 3000
- isInactive: false

### POST /department
- name (string, REQUIRED)
- departmentNumber (string, REQUIRED)

### POST /project
- name (string, REQUIRED)
- number (string)
- projectManager: {"id": $employee_id}
- department: {"id": $dept_id}
- startDate, endDate (YYYY-MM-DD)

### Creating an Invoice (multi-step):
1. First ensure customer exists (POST /customer or GET /customer?name=...)
2. Create order: POST /order
   - customer: {"id": $customer_id}
   - orderDate: "YYYY-MM-DD" (REQUIRED)
   - deliveryDate: "YYYY-MM-DD" (REQUIRED)
   - orderLines: [{"product": {"id": $product_id}, "count": N, "unitPriceExcludingVatCurrency": X.XX, "vatType": {"id": 3}}]
3. Invoice the order: PUT /order/$order_id/:invoice
   - invoiceDate: "YYYY-MM-DD" (REQUIRED)
   - sendToCustomer: false

### POST /ledger/voucher
For journal entries / manual bookkeeping:
- date: "YYYY-MM-DD"
- description: "..."
- postings: [{"account": {"id": X}, "amount": X.XX, "description": "..."}]

### POST /travelExpense
- employee: {"id": $employee_id}
- title: "..."
- costs: [{"date": "YYYY-MM-DD", "description": "...", "amount": X.XX, "vatType": {"id": 3}, "currency": {"id": 1}}]

## DATE FORMAT
ALWAYS convert dates to YYYY-MM-DD:
- "15.03.1990" → "1990-03-15"
- "15. mars 1990" → "1990-03-15"
- "March 15, 1990" → "1990-03-15"
- "15/03/1990" → "1990-03-15"

## RESPONSE FORMAT
Return ONLY valid JSON:
```json
{
  "task_type": "create_employee|create_customer|create_product|create_invoice|create_supplier|create_department|create_project|other",
  "api_calls": [
    {
      "method": "POST|PUT|GET",
      "path": "/employee",
      "data": { ... },
      "description": "Short description",
      "capture_id_as": "employee_id"
    }
  ]
}
```

Rules:
- capture_id_as: saves the created entity's ID for use in later calls
- Reference saved IDs with "$variable_name" in data fields
- Extract ALL information from the prompt — names, emails, dates, numbers
- For employees: ALWAYS create both the employee AND the employment record
- NEVER include readOnly fields like "id" or "version" in POST data
- Keep descriptions short but clear"""

ERROR_RECOVERY_PROMPT = """The previous API calls had errors. Here is what happened:

{error_log}

Original task prompt:
{original_prompt}

Please analyze the errors and provide corrected API calls. Common issues:
- Missing required fields (check the error message for which field)
- Wrong date format (must be YYYY-MM-DD)
- Wrong field names or types
- Need to create prerequisite entities first (e.g., customer before invoice)
- startDate belongs on Employment, not Employee

Return the CORRECTED api_calls as JSON in the same format as before.
Only include the calls that still need to be made (skip already successful ones).
If an entity was already created successfully, use its captured ID."""


def call_llm(messages: list) -> dict:
    """Call OpenRouter LLM."""
    logger.info(f"  LLM call: {len(messages)} messages, model={LLM_MODEL}")

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 4096,
        },
        timeout=60,
    )

    if resp.status_code != 200:
        logger.error(f"  LLM ERROR {resp.status_code}: {resp.text[:300]}")
        return None

    result = resp.json()
    content = result["choices"][0]["message"]["content"]
    logger.info(f"  LLM response: {len(content)} chars")
    logger.info(f"  LLM raw: {content[:1000]}")

    # Parse JSON from response - handle markdown and surrounding text
    content = content.strip()

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(content[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    logger.error(f"  Could not parse JSON from LLM response")
    logger.error(f"  Content: {content[:500]}")
    return None


def get_initial_plan(prompt: str, files: list) -> dict:
    """Get initial plan from LLM."""
    user_content = f"Task prompt:\n{prompt}"
    if files:
        user_content += "\n\nAttached files:"
        for f in files:
            user_content += f"\n- {f.get('filename', '?')} ({f.get('mime_type', '?')})"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    return call_llm(messages)


def get_recovery_plan(prompt: str, error_log: str, previous_messages: list) -> dict:
    """Ask LLM to fix errors based on API responses."""
    recovery_content = ERROR_RECOVERY_PROMPT.format(
        error_log=error_log,
        original_prompt=prompt,
    )
    messages = previous_messages + [
        {"role": "user", "content": recovery_content},
    ]
    return call_llm(messages)


# ============================================================
# EXECUTE API CALLS
# ============================================================

def resolve_references(data: Any, captured_ids: dict) -> Any:
    """Recursively resolve $variable_name references."""
    if isinstance(data, str):
        if data.startswith("$") and data[1:] in captured_ids:
            return captured_ids[data[1:]]
        for var, val in captured_ids.items():
            data = data.replace(f"${var}", str(val))
        return data
    elif isinstance(data, dict):
        return {k: resolve_references(v, captured_ids) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_references(item, captured_ids) for item in data]
    return data


def execute_plan(client: TripletexClient, plan: dict, captured_ids: dict = None) -> tuple:
    """Execute planned API calls. Returns (success, captured_ids, error_details)."""
    if captured_ids is None:
        captured_ids = {}

    api_calls = plan.get("api_calls", [])
    errors = []

    for i, call in enumerate(api_calls):
        method = call.get("method", "POST").upper()
        path = call.get("path", "")
        data = call.get("data", {})
        desc = call.get("description", f"Call {i+1}")
        capture_as = call.get("capture_id_as")

        logger.info(f"  [{i+1}/{len(api_calls)}] {desc}")

        # Resolve captured ID references
        data = resolve_references(data, captured_ids)
        path = resolve_references(path, captured_ids)

        # Skip calls with unresolved references
        data_str = json.dumps(data)
        if "$" in data_str:
            unresolved = re.findall(r'\$(\w+)', data_str)
            logger.warning(f"  Skipping - unresolved refs: {unresolved}")
            errors.append(f"Call {i+1} ({desc}): unresolved references {unresolved}")
            continue

        # Execute
        if method == "POST":
            result = client.post(path, data)
        elif method == "PUT":
            result = client.put(path, data)
        elif method == "GET":
            result = client.get(path, data)
        else:
            logger.warning(f"  Unknown method: {method}")
            continue

        # Capture ID if needed
        if capture_as and result["status_code"] < 400:
            body = result["body"]
            new_id = None
            if isinstance(body, dict):
                value = body.get("value", body)
                if isinstance(value, dict):
                    new_id = value.get("id")
            if new_id:
                captured_ids[capture_as] = new_id
                logger.info(f"  ✓ Captured {capture_as} = {new_id}")

        if result["status_code"] >= 400:
            error_body = result["body"]
            error_msg = ""
            if isinstance(error_body, dict):
                error_msg = error_body.get("message", "")
                vals = error_body.get("validationMessages", [])
                if vals:
                    error_msg += f" | Validations: {json.dumps(vals, ensure_ascii=False)}"
            errors.append(
                f"Call {i+1} ({method} {path}): {result['status_code']} - {error_msg}\n"
                f"  Sent data: {json.dumps(data, ensure_ascii=False)[:500]}"
            )

    return len(errors) == 0, captured_ids, errors


# ============================================================
# ENDPOINTS — Accept POST on BOTH / and /solve
# ============================================================

@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "tripletex-ai-agent",
        "version": "0.3.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


async def handle_solve(body: dict) -> JSONResponse:
    """Core solve logic shared by both endpoints."""
    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})
    base_url = creds.get("base_url", "")
    session_token = creds.get("session_token", "")

    logger.info("=" * 70)
    logger.info("NEW TASK RECEIVED")
    logger.info("=" * 70)
    logger.info(f"Prompt: {prompt}")
    logger.info(f"Files: {len(files)} {[f.get('filename','?') for f in files]}")
    logger.info(f"Base URL: {base_url}")
    logger.info(f"Token: {session_token[:15]}..." if len(session_token) > 15 else f"Token: {session_token}")

    if not base_url or not session_token:
        logger.error("Missing credentials!")
        return JSONResponse({"status": "completed"})

    client = TripletexClient(base_url, session_token)

    # --- STEP 1: Get initial plan from LLM ---
    logger.info("\n[STEP 1] Getting plan from LLM...")
    plan = get_initial_plan(prompt, files)

    if plan is None:
        logger.error("LLM failed to produce a plan")
        return JSONResponse({"status": "completed"})

    task_type = plan.get("task_type", "unknown")
    logger.info(f"  Task type: {task_type}")
    logger.info(f"  Planned calls: {len(plan.get('api_calls', []))}")
    for c in plan.get("api_calls", []):
        logger.info(f"    {c.get('method','?')} {c.get('path','?')} — {c.get('description','?')}")

    # --- STEP 2: Execute the plan ---
    logger.info("\n[STEP 2] Executing plan...")
    success, captured_ids, errors = execute_plan(client, plan)

    # --- STEP 3: Error recovery (one retry) ---
    if not success and errors:
        logger.info(f"\n[STEP 3] Errors detected ({len(errors)}), asking LLM for recovery...")
        error_log = "\n\n".join(errors)
        logger.info(f"  Errors:\n{error_log}")

        # Build conversation for recovery
        user_msg = f"Task prompt:\n{prompt}"
        prev_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": json.dumps(plan)},
        ]

        recovery_plan = get_recovery_plan(prompt, error_log, prev_messages)
        if recovery_plan and recovery_plan.get("api_calls"):
            logger.info(f"  Recovery plan: {len(recovery_plan['api_calls'])} calls")
            for c in recovery_plan.get("api_calls", []):
                logger.info(f"    {c.get('method','?')} {c.get('path','?')} — {c.get('description','?')}")

            success2, captured_ids, errors2 = execute_plan(client, recovery_plan, captured_ids)
            if success2:
                logger.info("  Recovery SUCCESSFUL!")
            else:
                logger.warning(f"  Recovery had {len(errors2)} errors")
        else:
            logger.warning("  LLM could not produce recovery plan")

    logger.info("\n" + "=" * 70)
    logger.info(f"TASK COMPLETE — API calls: {client.call_count}, Errors: {client.errors}")
    logger.info(f"Captured IDs: {captured_ids}")
    logger.info("=" * 70)

    return JSONResponse({"status": "completed"})


@app.post("/solve")
async def solve(request: Request):
    body = await request.json()
    return await handle_solve(body)


@app.post("/")
async def solve_root(request: Request):
    """Handle POST to / — platform may call this instead of /solve."""
    body = await request.json()
    return await handle_solve(body)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
