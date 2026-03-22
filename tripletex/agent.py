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

# Memory: learn from errors across runs
MEMORY_FILE = Path(__file__).parent / "memory.json"
def load_memory():
    if MEMORY_FILE.exists():
        try: return json.loads(MEMORY_FILE.read_text())
        except: pass
    return {"lessons": []}

def save_lesson(error_msg, fix):
    mem = load_memory()
    # Don't duplicate
    for l in mem["lessons"]:
        if l["error"] == error_msg:
            return
    mem["lessons"].append({"error": error_msg, "fix": fix, "ts": datetime.utcnow().isoformat()})
    # Keep last 50 lessons
    mem["lessons"] = mem["lessons"][-50:]
    MEMORY_FILE.write_text(json.dumps(mem, indent=2, ensure_ascii=False))

def get_lessons_text():
    mem = load_memory()
    if not mem["lessons"]:
        return ""
    lines = ["LESSONS FROM PREVIOUS RUNS (avoid these mistakes):"]
    for l in mem["lessons"][-20:]:
        lines.append(f"- {l['fix']}")
    return "\n".join(lines)

ENV = {}
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

LLM_KEY = ENV.get("OPENROUTER_API_KEY", "")
LLM_MODEL = "anthropic/claude-sonnet-4"

# Task type detection — ONLY match when 100% certain. Everything else → generic.
def detect_task_type(prompt):
    p = prompt.lower()
    words = p.split()
    prompt_len = len(words)

    # Only match SHORT, simple prompts (< 40 words) for Tier 1 recipes
    # Long/complex prompts → generic (let LLM figure it out)
    if prompt_len > 50:
        return "generic"

    # Payroll — very distinct keyword, safe to match
    if any(w in p for w in ["lønn for", "payroll for", "paie de", "nómina"]):
        return "payroll"

    # Only match pure "create X" tasks — no multi-step tasks
    # Must NOT contain invoice/payment/voucher/project lifecycle keywords
    has_complex = any(w in p for w in ["faktura", "invoice", "betaling", "payment", "voucher", "bilag",
        "reconcil", "årsoppgj", "year-end", "month-end", "prosjektsyklus", "lifecycle",
        "kreditnota", "credit note", "reverser", "reverse", "purregebyr", "reminder",
        "timer", "hours", "horas", "heures", "reiseregning", "travel expense"])

    if not has_complex:
        # Pure create department (very safe — "trois départements", "three departments")
        if any(w in p for w in ["avdeling", "department", "départe", "abteilung", "departamento"]):
            return "create_department"
        # Pure create supplier
        if any(w in p for w in ["registrer leverandør", "register.*supplier", "enregistrez.*fournisseur"]):
            return "create_supplier"
        # Pure create product (with price/VAT)
        if any(w in p for w in ["opprett produkt", "create.*product", "créez.*produit", "crea.*producto"]):
            return "create_product"

    return "generic"

# Recipes: short, specific instructions per task type
RECIPES = {
"create_customer": """Create customer. Extract name, organizationNumber, email, phone, address from prompt.
POST /customer {name, isCustomer:true, organizationNumber?, email?, phoneNumber?, postalAddress?:{addressLine1,postalCode,city}}
One call, then done:true.""",

"create_supplier": """Create supplier. Extract name, organizationNumber, email from prompt.
POST /supplier {name, organizationNumber?, email?}
One call, then done:true.""",

"create_employee": """Create employee:
1. GET /department?count=50 to find department ID
2. POST /employee {firstName, lastName, userType:"NO_ACCESS", department:{id:DEPT_ID}, email, dateOfBirth:"YYYY-MM-DD"}
3. POST /employee/employment {employee:{id:EMP_ID}, startDate:"YYYY-MM-DD"}
4. POST /employee/employment/details {employment:{id:EMPL_ID}, date:"YYYY-MM-DD", employmentType:"ORDINARY", remunerationType:"MONTHLY_WAGE", workingHoursScheme:"NOT_SHIFT", percentageOfFullTimeEquivalent:100, annualSalary:N}
If occupation code mentioned: GET /employee/employment/occupationCode?count=50 first, add occupationCode:{id} to details.""",

"create_department": """Create department(s). Extract name(s) from prompt.
POST /department {name} for each. Batch in one turn. Then done:true.""",

"create_product": """Create product. Extract name, number, price, VAT rate from prompt.
If VAT mentioned: GET /ledger/vatType first. Common: 25%→id=3, 15%→id=31, 12%→id=32, 0%→id=5
POST /product {name, number, priceExcludingVatCurrency, vatType:{id:X}}
One call, then done:true.""",

"create_project": """Create project linked to customer:
1. GET /customer?organizationNumber=X — if not found, POST /customer
2. GET /employee?email=X or POST /employee for project manager
3. POST /project {name, number:"PROJ-001", isInternal:false, projectManager:{id:EMP_ID}, customer:{id:CUST_ID}, startDate:"TODAY"}
Then done:true.""",

"create_invoice": """Create and send invoice:
1. GET /customer?organizationNumber=X — if not found, POST /customer
2. POST /order {customer:{id}, orderDate:"TODAY", deliveryDate:"TODAY", orderLines:[{description, count:1, unitPriceExcludingVatCurrency:AMOUNT}]}
3. PUT /order/{id}/:invoice?invoiceDate=TODAY&sendToCustomer=true (use query params, NO body)
If step 3 fails, try POST /invoice {invoiceDate, invoiceDueDate, customer:{id}, orders:[{id}]}""",

"supplier_invoice": """Register supplier invoice as voucher:
1. GET /supplier?organizationNumber=X — if not found, POST /supplier {name, organizationNumber}
2. GET /ledger/account?number=EXPENSE (account from prompt, e.g. 6300, 7300)
3. GET /ledger/account?number=2710 (input VAT)
4. GET /ledger/account?number=2400 (accounts payable)
5. Calculate: if amount includes VAT → netto=amount/1.25, mva=amount-netto. If excludes VAT → netto=amount, mva=amount*0.25
6. POST /ledger/voucher {date:"TODAY", description:"Invoice [number] from [supplier]", postings:[
   {row:1, account:{id:EXPENSE_ID}, amount:netto, amountCurrency:netto, amountGross:netto, amountGrossCurrency:netto, description:"[expense description]"},
   {row:2, account:{id:2710_ID}, amount:mva, amountCurrency:mva, amountGross:mva, amountGrossCurrency:mva, description:"Input VAT 25%"},
   {row:3, account:{id:2400_ID}, supplier:{id:SUPP_ID}, amount:-total, amountCurrency:-total, amountGross:-total, amountGrossCurrency:-total, description:"Accounts payable"}
]} Sum MUST be 0. Row starts at 1.""",

"payroll": """Payroll — use voucher (salary API requires module):
1. GET /employee?email=X
2. GET /ledger/account?number=5000 (salary expense)
3. GET /ledger/account?number=2930 (salary payable — NOT 2920!)
4. POST /ledger/voucher {date:"TODAY", description:"Payroll [name]", postings:[
   {row:1, account:{id:5000_ID}, amount:BASE_SALARY, amountCurrency:BASE_SALARY, amountGross:BASE_SALARY, amountGrossCurrency:BASE_SALARY, description:"Base salary"},
   {row:2, account:{id:5000_ID}, amount:BONUS, amountCurrency:BONUS, amountGross:BONUS, amountGrossCurrency:BONUS, description:"Bonus"},
   {row:3, account:{id:2930_ID}, amount:-(BASE+BONUS), amountCurrency:-(BASE+BONUS), amountGross:-(BASE+BONUS), amountGrossCurrency:-(BASE+BONUS), description:"Salary payable"}
]} Sum MUST be 0.""",

"credit_note": """Credit note for customer invoice:
1. GET /customer?organizationNumber=X
2. GET /invoice?customerId=ID&invoiceDateFrom=2020-01-01&invoiceDateTo=TODAY (BOTH dates required!)
3. PUT /invoice/{id}/:createCreditNote?date=TODAY (date as QUERY PARAM, not body!)
Then done:true.""",

"dimension": """Create accounting dimension:
1. POST /ledger/accountingDimensionName {dimensionName:"NAME", active:true}
2. POST /ledger/accountingDimensionValue {displayName:"VALUE1", number:"VALUE1", active:true, showInVoucherRegistration:true}
3. Repeat step 2 for each value
4. If voucher needed: GET /ledger/account?number=X, then POST /ledger/voucher with correct postings""",
}

# Base system prompt (used for generic fallback and as header for recipes)
SYSTEM_HEADER = """You are an AI accounting agent for Tripletex. Respond with ONLY this JSON:
{"calls": [{"method":"GET|POST|PUT|DELETE","path":"/endpoint","params":{},"body":{}}], "done": false}
Set done:true when complete. RULES:
- Every 4xx error hurts score. Never retry same call more than once.
- Never call: POST /ledger/account, PUT /ledger/posting, POST /salary/transaction, POST /payment
- After creating something (201), NEVER modify/delete it. Move on.
- Voucher: row starts at 1 (NEVER 0), include amountGross, sum must be 0.
- Prompts come in 7 languages (nb,en,es,pt,nn,de,fr)."""

SYSTEM = """You are an AI accounting agent. You complete tasks in Tripletex (Norwegian ERP) by making API calls.

RESPONSE FORMAT — always respond with ONLY this JSON, nothing else:
{"calls": [{"method":"GET|POST|PUT|DELETE","path":"/endpoint","params":{},"body":{}}], "done": false}
Set done:true when task is complete. You will see API results and can make more calls.

IMPORTANT RULES:
- Be EFFICIENT. Plan all needed calls upfront. Avoid unnecessary GETs.
- The environment starts EMPTY but may have some pre-populated data. ALWAYS GET first to check if entities exist before creating. Use GET /product?number=X, GET /customer?organizationNumber=X, GET /supplier?organizationNumber=X.
- Every 4xx error hurts your score. Validate before sending.
- NEVER guess IDs for paymentType, costCategory, vatType, rateCategory etc. ALWAYS GET them first.
- You CANNOT create or delete ledger accounts. Use existing accounts only. NEVER delete vouchers.
- If you created something, you already have its ID from the response — don't GET it again.
- Use ?fields=* to see all fields on an entity.
- Batch multiple creates in one turn when possible.
- Prompts come in 7 languages (nb, en, es, pt, nn, de, fr).
- After creating a voucher/invoice/entity successfully (201), NEVER PUT/DELETE/modify it. Move on.
- CRITICAL: If a write call (POST/PUT) fails, NEVER retry the same endpoint more than once. Move on or try a different approach.
- NEVER call: POST /ledger/account, PUT /ledger/posting, POST /salary/transaction — these always fail.
- For vouchers: GET /ledger/account?number=XXXX for EVERY account you need BEFORE creating the voucher.
- Voucher postings MUST include: row (starting from 1, NEVER 0), account:{id}, amount, amountCurrency, amountGross, amountGrossCurrency, description. Debit=positive, credit=negative. Sum MUST equal 0.

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
10. Salary/Payroll → The salary API requires a salary module. Try POST /salary/transaction {date, year, month} ONCE.
  If it fails (403/422), IMMEDIATELY fall back to POST /ledger/voucher:
  Debit account 5000 (Lønn) for base salary, debit 5000 again for bonus, credit account 2930 (Skyldig lønn) for negative total.
  Do NOT retry /salary/transaction more than once.
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
- POST /employee/employment/details {employment:{id:EMPLOYMENT_ID}, date:"YYYY-MM-DD", employmentType:"ORDINARY", remunerationType:"MONTHLY_WAGE", workingHoursScheme:"NOT_SHIFT", percentageOfFullTimeEquivalent:100, annualSalary:N}
  * Use occupationCode:{id:X} if task specifies one — GET /employee/employment/occupationCode to find ID
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
  * Create order FIRST in one turn, then POST /invoice in the NEXT turn (not same turn).
  * If POST /invoice fails, IMMEDIATELY fall back to PUT /order/{id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=false
- POST /ledger/voucher — EXAMPLE of a correct supplier invoice voucher (9100 NOK incl 25% VAT):
  {"date":"2026-03-22", "description":"Invoice from Supplier X", "postings":[
    {"row":1, "account":{"id":ACC_6300_ID}, "amount":7280, "amountCurrency":7280, "amountGross":7280, "amountGrossCurrency":7280, "description":"Office services"},
    {"row":2, "account":{"id":ACC_2710_ID}, "amount":1820, "amountCurrency":1820, "amountGross":1820, "amountGrossCurrency":1820, "description":"Input VAT 25%"},
    {"row":3, "account":{"id":ACC_2400_ID}, "supplier":{"id":SUPP_ID}, "amount":-9100, "amountCurrency":-9100, "amountGross":-9100, "amountGrossCurrency":-9100, "description":"Accounts payable"}
  ]}
  RULES: Row numbers MUST start from 1 (row 0 is FORBIDDEN — system-generated). Positive=debit, negative=credit. Sum MUST be 0.
  Use account 2710 (not 2700) for input VAT deduction (inngående MVA fradrag).
  For account 1500: add customer:{id:X}. For account 2400: add supplier:{id:X}.
  GET /ledger/account?number=XXXX to find each account ID before creating voucher.
- POST /activity {name, number, activityType:"PROJECT_GENERAL_ACTIVITY"}
- POST /project/projectActivity {activity:{id:X}, project:{id:Y}} — ALWAYS link activities to projects
- POST /ledger/accountingDimensionName {dimensionName, active:true} — create custom dimension
- POST /ledger/accountingDimensionValue {displayName, number, active:true, showInVoucherRegistration:true} — add values to dimension
- POST /timesheet/entry {employee:{id:X}, project:{id:Y}, activity:{id:Z}, date:"YYYY-MM-DD", hours:N}

PUT endpoints (update/actions):
- PUT /order/{id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=true (fallback if POST /invoice fails)
- PUT /invoice/{id}/:payment — use QUERY PARAMS not body: ?paymentDate=YYYY-MM-DD&paymentTypeId=N&paidAmount=N&paidAmountCurrency=N
  * GET /invoice/paymentType FIRST to find valid paymentTypeId (IDs vary per environment)
  * Send ALL payment fields as params:{}, NOT body:{}
- PUT /invoice/{id}/:createCreditNote — use QUERY PARAMS: ?date=YYYY-MM-DD (NOT body! body gives 422)
- PUT /invoice/{id}/:createReminder
- PUT /invoice/{id}/:send?sendType=EMAIL (sendType as QUERY PARAM, not body)
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
            json={"model": LLM_MODEL, "messages": messages, "temperature": 0, "max_tokens": 4000,
                  "response_format": {"type": "json_object"}}, timeout=45)
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"]
        log.info(f"  LLM ({len(txt)}c): {txt[:500]}")
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
        # Fix voucher postings: ensure amountGross is always set
        if method == "POST" and "voucher" in path:
            body = call.get("body", {})
            for p in body.get("postings", []):
                if "amountGross" not in p and "amount" in p:
                    p["amountGross"] = p["amount"]
                if "amountGrossCurrency" not in p and "amountCurrency" in p:
                    p["amountGrossCurrency"] = p["amountCurrency"]
        if method == "GET":
            r = session.get(url, params=call.get("params"), timeout=15)
        else:
            r = getattr(session, method.lower())(url, params=call.get("params"), json=call.get("body"), timeout=15)
        log.info(f"  {method} {path}: {r.status_code}")
        if r.status_code >= 400:
            log.error(f"    ERROR: {r.text[:300]}")
            # Learn from errors
            try:
                err_data = r.json()
                for vm in err_data.get("validationMessages", []):
                    emsg = vm.get("message", "")
                    if emsg:
                        fix = f"When calling {method} {path}: {emsg}"
                        save_lesson(emsg, fix)
            except:
                pass
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

    # Pre-calculate numbers from prompt so LLM doesn't have to do arithmetic
    def calc_helper(prompt_text):
        calcs = []
        import re as _re
        # Currency: amount × rate
        for m in _re.finditer(r'(\d[\d\s]*(?:[.,]\d+)?)\s*EUR.*?(\d+[.,]\d+)\s*NOK/EUR', prompt_text):
            eur = float(m.group(1).replace(" ", "").replace(",", "."))
            rate = float(m.group(2).replace(",", "."))
            nok = round(eur * rate, 2)
            calcs.append(f"{eur} EUR × {rate} NOK/EUR = {nok} NOK")
        # Two rates → calculate difference
        rates = _re.findall(r'(\d+[.,]\d+)\s*NOK/EUR', prompt_text)
        eur_amounts = _re.findall(r'(\d[\d\s]*(?:[.,]\d+)?)\s*EUR', prompt_text)
        if len(rates) >= 2 and eur_amounts:
            eur = float(eur_amounts[0].replace(" ", "").replace(",", "."))
            r1 = float(rates[0].replace(",", "."))
            r2 = float(rates[1].replace(",", "."))
            nok1 = round(eur * r1, 2)
            nok2 = round(eur * r2, 2)
            diff = round(nok2 - nok1, 2)
            calcs.append(f"Original: {eur} × {r1} = {nok1} NOK")
            calcs.append(f"Payment: {eur} × {r2} = {nok2} NOK")
            calcs.append(f"Exchange difference: {nok2} - {nok1} = {diff} NOK")
        # VAT: amount inkl MVA → netto + MVA
        for m in _re.finditer(r'(\d[\d\s]*(?:[.,]\d+)?)\s*(?:kr|NOK)?\s*(?:inklusiv|inkl|including|incl|inklusive|einschließlich|incluant|incluindo|incluyendo)\s*(?:MVA|mva|VAT|MwSt|TVA|IVA)', prompt_text, _re.I):
            brutto = float(m.group(1).replace(" ", "").replace(",", "."))
            netto = round(brutto / 1.25, 2)
            mva = round(brutto - netto, 2)
            calcs.append(f"{brutto} incl 25% VAT: netto={netto}, VAT={mva}")
        # Salary + bonus
        base_m = _re.search(r'(?:base|grunn|salaire|sueldo|salário).*?(\d[\d\s]*(?:[.,]\d+)?)\s*(?:kr|NOK)', prompt_text, _re.I)
        bonus_m = _re.search(r'(?:bonus|prime|prima).*?(\d[\d\s]*(?:[.,]\d+)?)\s*(?:kr|NOK)', prompt_text, _re.I)
        if base_m and bonus_m:
            base = float(base_m.group(1).replace(" ", "").replace(",", "."))
            bonus = float(bonus_m.group(1).replace(" ", "").replace(",", "."))
            calcs.append(f"Base salary: {base}, Bonus: {bonus}, Total: {base + bonus}")
        # Depreciation: cost / years
        for m in _re.finditer(r'(\d[\d\s]*(?:[.,]\d+)?)\s*(?:kr|NOK).*?(\d+)\s*(?:år|year|an|año|ano|jahr)', prompt_text, _re.I):
            cost = float(m.group(1).replace(" ", "").replace(",", "."))
            years = int(m.group(2))
            annual = round(cost / years, 2)
            monthly = round(annual / 12, 2)
            calcs.append(f"Depreciation: {cost} / {years} years = {annual}/year = {monthly}/month")
        return calcs

    calcs = calc_helper(prompt)

    # Build user message with prompt + decoded files
    today = datetime.utcnow().strftime("%Y-%m-%d")
    lessons = get_lessons_text()
    user_msg = f"Today's date: {today}\n\nTask:\n{prompt}"
    if calcs:
        user_msg += "\n\nPRE-CALCULATED VALUES (use these exact numbers):\n" + "\n".join(f"  {c}" for c in calcs)
    if lessons:
        user_msg += f"\n\n{lessons}"
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

    # Always use full system prompt — recipe detection caused misclassification issues
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
