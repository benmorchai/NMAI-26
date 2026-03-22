# Tripletex Agent Knowledge Base

## CRITICAL: Scoring System
- Field-by-field verification AFTER agent returns
- Scoring QUERIES the Tripletex API to check what was created
- Each check has point values (e.g. "Employee found: 2pts, first name: 1pt")
- correctness = points_earned / max_points (0-1)
- Tier multiplier: T1=x1, T2=x2, T3=x3
- Efficiency bonus only for perfect (1.0) correctness
- Max score: T1=2.0, T2=4.0, T3=6.0
- Best score per task kept forever

## CRITICAL: Common Task Patterns (from docs)
| Pattern | Example | API Flow |
|---------|---------|----------|
| Create single entity | "Create employee" | POST /employee |
| Create with linking | "Create invoice for customer" | GET /customer → POST /order → POST /invoice |
| Modify existing | "Add phone to contact" | GET /customer → PUT /customer/{id} |
| Delete/reverse | "Delete travel expense" | GET /travelExpense → DELETE /travelExpense/{id} |
| Multi-step setup | "Register payment" | POST /customer → POST /invoice → POST /payment |

## CRITICAL: What scoring checks (learned from runs)
- Employee: found?, firstName, lastName, email, department, dateOfBirth, employment, role
- Customer: found?, name, organizationNumber, email, address
- Supplier: found?, name, organizationNumber, email
- Product: found?, name, number, price, vatType
- Department: found?, name
- Project: found?, name, customer link, projectManager
- Invoice: found?, customer, amount, date, orderLines
- Voucher: postings checked for account numbers, amounts, descriptions

## CRITICAL: Voucher Requirements (verified in sandbox)
- Row numbers MUST start from 1 (row 0 = system generated, causes 422)
- MUST include amountGross and amountGrossCurrency (without them amounts = 0.00!)
- Sum of all postings MUST equal 0 (debit=positive, credit=negative)
- For account 1500 (Kundefordringer): add customer:{id:X}
- For account 2400 (Leverandørgjeld): add supplier:{id:X}
- Use account 2710 for input VAT (not 2700)

## Account Numbers (verified in sandbox)
- 1500: Kundefordringer (id varies per environment)
- 1920: Bankinnskudd
- 2400: Leverandørgjeld
- 2700: Utgående MVA (for sales)
- 2710: Inngående MVA (for purchases)
- 2930: Skyldig lønn (NOT 2920!)
- 3000: Salgsinntekt, avgiftspliktig
- 5000: Lønn til ansatte
- 6300: Leie lokale
- 7300: Salgskostnad

## Employment Details (verified in sandbox)
- employmentType: "ORDINARY" (not "FULL_TIME")
- remunerationType: "MONTHLY_WAGE" (not "MONTHLY")
- workingHoursScheme: "NOT_SHIFT"
- percentageOfFullTimeEquivalent: 100.0
- Must create employment FIRST, then details in separate call

## Invoice Creation
- POST /invoice {invoiceDate, invoiceDueDate, customer:{id}, orders:[{id}]}
- Requires order to be created first
- Fails with 422 if company has no bank account number
- Fallback: PUT /order/{id}/:invoice?invoiceDate=X&sendToCustomer=false

## Endpoints That NEVER Work
- POST /ledger/account (cannot create accounts)
- PUT /ledger/posting (cannot modify postings)
- POST /salary/transaction (requires salary module, always 403/422)
- POST /payment (does not exist)

## Dimensions
- POST /ledger/accountingDimensionName {dimensionName, active:true}
- POST /ledger/accountingDimensionValue {displayName, number, active:true, showInVoucherRegistration:true}

## Task Types We've Seen (with scores)
### Always works (7-10 pts):
- Create customer/supplier/employee/department/product/project

### Sometimes works (2-8 pts):
- Create invoice (depends on bank account)
- Register payment on invoice
- Project lifecycle (many steps)
- Employee from PDF

### Never works (0 pts):
- Supplier invoice via voucher → 0 (even with correct amounts!)
- Receipt expense via voucher → 0
- Year-end closing via voucher → 0
- Month-end closing via voucher → low score

## AINM Endpoint Spec
- POST /solve — accepts {prompt, files[], tripletex_credentials{base_url, session_token}}
- files[].content_base64 — base64-encoded PDF/image
- Auth: Basic Auth username="0", password=session_token
- Timeout: 300 seconds (5 minutes)
- Response: {"status": "completed"} with HTTP 200
- Each submission gets FRESH Tripletex account (starts empty each time)
- API via authenticated proxy (base_url from request)

## AINM Sandbox vs Competition
| | Sandbox | Competition |
|---|---|---|
| Account | Persistent | Fresh per submission |
| API access | Direct to Tripletex | Via proxy |
| Data | Accumulates | Starts empty |
| Scoring | None | Automated field-by-field |

## Efficiency Tips (from docs)
- Plan before calling — parse prompt fully first
- Avoid trial-and-error — every 4xx error reduces bonus
- Minimize GET calls — don't fetch what you don't need
- Batch where possible
- Read error messages — fix in one retry, not several
- GET requests don't count against efficiency

## VatType IDs (from sandbox)
- id=3: Utgående avgift, høy sats (25%) — for SALES
- id=5: Ingen utgående avgift, innenfor loven (0%)
- id=6: Ingen utgående avgift, utenfor loven (0%)
- id=31: Utgående avgift, middels sats (15%)
- id=32: Utgående avgift, lav sats (12%)
- id=1: Fradrag inngående avgift, høy sats (25%) — for PURCHASES

## Invoice Payment (verified from OpenAPI)
- PUT /invoice/{id}/:payment — QUERY PARAMS (not body):
  paymentDate, paymentTypeId, paidAmount, paidAmountCurrency
- GET /invoice/paymentType first to find valid paymentTypeId
- POST /payment does NOT exist in Tripletex API

## Credit Note
- PUT /invoice/{id}/:createCreditNote {date, comment?}

## Travel Expense
- GET /travelExpense/costCategory — IDs vary per environment
- GET /travelExpense/paymentType — IDs vary per environment
- POST /travelExpense {employee:{id}, project:{id}, title, ...}
- POST /travelExpense/cost {travelExpense:{id}, ...}
- POST /travelExpense/perDiemCompensation {travelExpense:{id}, ...}

## Incoming Invoice (supplier invoice — from OpenAPI)
- POST /incomingInvoice — complex format:
  {invoiceHeader: {vendorId, invoiceDate, dueDate, currencyId, invoiceAmount, description, invoiceNumber},
   orderLines: [{description, accountId, amountInclVat, vatTypeId}]}
- Sandbox gives 403 (permission denied), production proxy may allow it
- This might be what scoring checks for supplier invoice tasks

## KEY UNSOLVED PROBLEM
Vouchers with correct amounts, correct accounts, 0 errors → still 0 score.
Scoring may be checking something OTHER than /ledger/voucher for certain task types.

Hypotheses:
1. Scoring checks /incomingInvoice for supplier invoices (not /ledger/voucher)
2. Scoring checks specific voucher fields we're not setting (vendorInvoiceNumber?)
3. Production proxy behaves differently from sandbox
4. amountGross code-fix may not be triggering in production (need to verify)

## UI Testing Results (2026-03-22)

### Bank Account
- bankAccountNumber CANNOT be set via API (readOnly)
- Must be set via UI: Selskap → Selskapsinformasjon → Fakturakonto
- Requires: 11-digit valid Norwegian bank account + SWIFT code
- Production proxy MAY pre-set this for invoice tasks

### Invoice Flow (verified working in sandbox)
1. POST /customer → 201
2. POST /order with orderLines → 201
3. POST /invoice {invoiceDate, invoiceDueDate, customer:{id}, orders:[{id}]} → 201
4. PUT /invoice/{id}/:payment?paymentDate=X&paymentTypeId=Y&paidAmount=Z&paidAmountCurrency=Z → 200
5. PUT /invoice/{id}/:createCreditNote?date=YYYY-MM-DD → 200 (date as QUERY PARAM, not body!)

### Credit Note
- PUT /invoice/{id}/:createCreditNote?date=YYYY-MM-DD (QUERY PARAM!)
- NOT body: {"date": "..."} — that gives 422 "date cannot be null"

### Key Finding
- Production environments for invoice tasks have bankAccountNumber pre-set
- For non-invoice tasks (project lifecycle etc), bank account is NOT set
- Agent should NOT try to set bank account via API (will fail)
