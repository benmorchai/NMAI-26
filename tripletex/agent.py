#!/usr/bin/env python3
"""
Tripletex AI Accounting Agent - NM i AI 2026

Uses OpenRouter (Claude Sonnet) to interpret accounting prompts
and execute Tripletex API calls.
"""

import base64
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
    """Load vars from .env file."""
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

# --- FastAPI ---
app = FastAPI(title="Tripletex AI Agent", version="0.2.0")


# ============================================================
# TRIPLETEX API CLIENT
# ============================================================

class TripletexClient:
    """Thin wrapper around Tripletex REST API v2."""

    def __init__(self, base_url: str, session_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = ("0", session_token)
        self.session.headers["Content-Type"] = "application/json"
        self.call_count = 0
        self.errors = 0

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get(self, path: str, params: dict = None) -> dict:
        self.call_count += 1
        url = self._url(path)
        logger.info(f"  API GET {path} params={params}")
        resp = self.session.get(url, params=params)
        if resp.status_code >= 400:
            self.errors += 1
            logger.error(f"  API ERROR {resp.status_code}: {resp.text[:300]}")
        else:
            logger.info(f"  API OK {resp.status_code}")
        return {"status_code": resp.status_code, "body": resp.json() if resp.text else {}}

    def post(self, path: str, data: dict) -> dict:
        self.call_count += 1
        url = self._url(path)
        logger.info(f"  API POST {path} data={json.dumps(data, ensure_ascii=False)[:500]}")
        resp = self.session.post(url, json=data)
        if resp.status_code >= 400:
            self.errors += 1
            logger.error(f"  API ERROR {resp.status_code}: {resp.text[:500]}")
        else:
            logger.info(f"  API OK {resp.status_code}")
        return {"status_code": resp.status_code, "body": resp.json() if resp.text else {}}

    def put(self, path: str, data: dict) -> dict:
        self.call_count += 1
        url = self._url(path)
        logger.info(f"  API PUT {path}")
        resp = self.session.put(url, json=data)
        if resp.status_code >= 400:
            self.errors += 1
            logger.error(f"  API ERROR {resp.status_code}: {resp.text[:500]}")
        else:
            logger.info(f"  API OK {resp.status_code}")
        return {"status_code": resp.status_code, "body": resp.json() if resp.text else {}}

    def delete(self, path: str) -> dict:
        self.call_count += 1
        url = self._url(path)
        logger.info(f"  API DELETE {path}")
        resp = self.session.delete(url)
        if resp.status_code >= 400:
            self.errors += 1
            logger.error(f"  API ERROR {resp.status_code}: {resp.text[:500]}")
        else:
            logger.info(f"  API OK {resp.status_code}")
        return {"status_code": resp.status_code, "body": resp.json() if resp.text else {}}


# ============================================================
# LLM CLIENT (OpenRouter)
# ============================================================

SYSTEM_PROMPT = """You are an AI accounting assistant for Tripletex (Norwegian accounting software).
You receive accounting task prompts (possibly in Norwegian, English, Spanish, Portuguese, Nynorsk, German, or French) and must determine which Tripletex API calls to make.

You have access to these Tripletex API endpoints:

## Employee (POST /employee)
Fields: firstName, lastName, email, dateOfBirth (YYYY-MM-DD), phoneNumberMobile, employeeNumber, nationalIdentityNumber, bankAccountNumber, address ({addressLine1, postalCode, city, country: {id: 161} for Norway}), isContact (false for employee, true for contact), startDate (YYYY-MM-DD)
NOTE: After creating an employee, you must also create an employment via POST /employee/employment with: {employee: {id: <employee_id>}, startDate: "YYYY-MM-DD", employmentType: "ORDINARY", percentageOfFullTimeEquivalent: 100.0, workingHoursScheme: "STANDARD"}

## Customer (POST /customer)
Fields: name, email, phoneNumber, phoneNumberMobile, organizationNumber, isPrivateIndividual (true/false), postalAddress ({addressLine1, postalCode, city, country: {id: 161}}), invoiceEmail, language ("NO"/"EN"), isSupplier (false)

## Product (POST /product)
Fields: name, number, description, priceExcludingVatCurrency, priceIncludingVatCurrency, vatType ({id: X}), isInactive (false), productUnit ({id: X}), account ({id: X})
Common VAT types: {id: 3} = 25% MVA, {id: 6} = 0% MVA (exempt), {id: 5} = 15% food MVA, {id: 1} = exempt
Common product units: {id: 1} = stk (pieces), {id: 2} = kg, {id: 3} = liter, {id: 5} = timer (hours)
Revenue account: {id: 260} for 3000 (Salgsinntekt)

## Invoice (POST /invoice)
First create an Order (POST /order), then invoice it (PUT /order/:invoiceIds/invoice).
Order fields: customer ({id: X}), deliveryDate (YYYY-MM-DD), orderDate (YYYY-MM-DD), orderLines: [{product: {id: X}, count: N, unitPriceExcludingVatCurrency: X.XX}]

## Contact (POST /customer with isContact: true or via employees with isContact: true)

## Department (POST /department)
Fields: name, departmentNumber

## Project (POST /project)
Fields: name, number, projectManager ({id: X}), department ({id: X}), startDate, endDate

## Account (POST /ledger/account)
Fields: number, name

## Supplier (POST /supplier)
Fields: name, email, phoneNumber, organizationNumber, postalAddress (same as customer)

## Payment (POST /payment)
Fields: paymentDate, amount, amountCurrency, invoice ({id: X})

## Travel Expense (POST /travelExpense)
Fields: employee ({id: X}), departureDate, returnDate, title, description

IMPORTANT RULES:
1. Extract ALL required information from the prompt
2. Use the EXACT data from the prompt (names, numbers, dates, etc.)
3. For dates, convert to YYYY-MM-DD format
4. For Norwegian phone numbers, keep as-is
5. If creating an employee, always also create the employment record
6. Return your response as a JSON array of API calls to make

Respond ONLY with valid JSON in this exact format:
```json
{
  "task_type": "create_employee|create_customer|create_product|create_invoice|other",
  "api_calls": [
    {
      "method": "POST",
      "path": "/employee",
      "data": { ... },
      "description": "Create employee Ola Nordmann",
      "capture_id_as": "employee_id"
    },
    {
      "method": "POST",
      "path": "/employee/employment",
      "data": {
        "employee": {"id": "$employee_id"},
        "startDate": "2026-01-01",
        "employmentType": "ORDINARY",
        "percentageOfFullTimeEquivalent": 100.0,
        "workingHoursScheme": "STANDARD"
      },
      "description": "Create employment for the employee"
    }
  ]
}
```

The "capture_id_as" field is optional - use it when a subsequent call needs the ID from a previous call. Reference captured IDs with "$variable_name" in subsequent call data.

IMPORTANT: Only output the JSON object, nothing else. No markdown, no explanation."""


def call_llm(prompt: str, files: list = None) -> dict:
    """Call OpenRouter LLM to interpret the accounting task."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Build user message with prompt and file info
    user_content = f"Task prompt:\n{prompt}"

    if files:
        user_content += "\n\nAttached files:"
        for f in files:
            fname = f.get("filename", "unknown")
            ftype = f.get("mime_type", "unknown")
            user_content += f"\n- {fname} ({ftype})"
            # For images, we could pass them as vision content
            # For now, just note their existence

    messages.append({"role": "user", "content": user_content})

    logger.info(f"  LLM request: {len(prompt)} chars prompt, model={LLM_MODEL}")

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

    # Parse JSON from response (handle markdown code blocks)
    content = content.strip()
    if content.startswith("```"):
        # Remove markdown code block
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"  LLM JSON parse error: {e}")
        logger.error(f"  Raw content: {content[:500]}")
        return None


# ============================================================
# EXECUTE API CALLS
# ============================================================

def execute_plan(client: TripletexClient, plan: dict) -> bool:
    """Execute the planned API calls against Tripletex."""
    api_calls = plan.get("api_calls", [])
    captured_ids = {}
    success = True

    for i, call in enumerate(api_calls):
        method = call.get("method", "POST").upper()
        path = call.get("path", "")
        data = call.get("data", {})
        desc = call.get("description", f"Call {i+1}")
        capture_as = call.get("capture_id_as", None)

        logger.info(f"  [{i+1}/{len(api_calls)}] {desc}")

        # Resolve captured ID references ($variable_name)
        data = resolve_references(data, captured_ids)

        # Execute the call
        if method == "POST":
            result = client.post(path, data)
        elif method == "PUT":
            # Resolve path references too
            for var, val in captured_ids.items():
                path = path.replace(f"${var}", str(val))
            result = client.put(path, data)
        elif method == "GET":
            result = client.get(path, data)
        elif method == "DELETE":
            result = client.delete(path)
        else:
            logger.warning(f"  Unknown method: {method}")
            continue

        # Capture ID if needed
        if capture_as and result["status_code"] < 400:
            body = result["body"]
            # Tripletex returns {value: {id: X, ...}}
            new_id = None
            if isinstance(body, dict):
                value = body.get("value", body)
                if isinstance(value, dict):
                    new_id = value.get("id")
            if new_id:
                captured_ids[capture_as] = new_id
                logger.info(f"  Captured {capture_as} = {new_id}")
            else:
                logger.warning(f"  Could not capture ID from response")

        if result["status_code"] >= 400:
            success = False
            # Don't abort - try remaining calls

    logger.info(f"  Plan executed: {len(api_calls)} calls, {client.call_count} total API calls, {client.errors} errors")
    return success


def resolve_references(data: Any, captured_ids: dict) -> Any:
    """Recursively resolve $variable_name references in data."""
    if isinstance(data, str):
        if data.startswith("$") and data[1:] in captured_ids:
            return captured_ids[data[1:]]
        # Also handle inside strings
        for var, val in captured_ids.items():
            data = data.replace(f"${var}", str(val))
        return data
    elif isinstance(data, dict):
        return {k: resolve_references(v, captured_ids) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_references(item, captured_ids) for item in data]
    return data


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "tripletex-ai-agent",
        "version": "0.2.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/solve")
async def solve(request: Request):
    """
    Main endpoint called by the NM i AI platform.

    1. Receives prompt + files + credentials
    2. Sends prompt to LLM to get API call plan
    3. Executes the plan against Tripletex
    4. Returns {"status": "completed"}
    """
    body = await request.json()

    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})
    base_url = creds.get("base_url", "")
    session_token = creds.get("session_token", "")

    logger.info("=" * 60)
    logger.info("NEW TASK RECEIVED")
    logger.info("=" * 60)
    logger.info(f"Prompt: {prompt[:500]}")
    logger.info(f"Files: {len(files)} {'(' + ', '.join(f.get('filename','?') for f in files) + ')' if files else ''}")
    logger.info(f"Base URL: {base_url}")

    # Step 1: Call LLM to interpret the task
    logger.info("[STEP 1] Calling LLM to interpret task...")
    plan = call_llm(prompt, files)

    if plan is None:
        logger.error("LLM failed to produce a plan. Returning completed anyway.")
        return JSONResponse({"status": "completed"})

    task_type = plan.get("task_type", "unknown")
    api_calls = plan.get("api_calls", [])
    logger.info(f"  Task type: {task_type}")
    logger.info(f"  Planned calls: {len(api_calls)}")
    for call in api_calls:
        logger.info(f"    {call.get('method', '?')} {call.get('path', '?')} - {call.get('description', '?')}")

    # Step 2: Execute the plan
    logger.info("[STEP 2] Executing API calls...")
    client = TripletexClient(base_url, session_token)
    success = execute_plan(client, plan)

    logger.info("=" * 60)
    logger.info(f"TASK COMPLETE - {'SUCCESS' if success else 'WITH ERRORS'}")
    logger.info(f"  API calls: {client.call_count}, Errors: {client.errors}")
    logger.info("=" * 60)

    return JSONResponse({"status": "completed"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
