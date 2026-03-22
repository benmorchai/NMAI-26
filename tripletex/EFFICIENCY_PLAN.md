# Tripletex Agent — Efficiency Forbedring

## Problem
Agenten klarer alle oppgaver (correctness = 1.0) men scoren er lav fordi **efficiency bonus mangler**.

## Scoring
```
score = correctness x tier x (1 + efficiency_bonus)

Uten bonus: maks 1x tier (det vi har na)
Med bonus:  maks 2x tier (dobbel score!)
```

Efficiency bonus basert pa:
1. **Write-calls** vs best-in-class (POST/PUT/DELETE/PATCH). GETs er GRATIS.
2. **4xx errors** - hver feil reduserer bonus

## Endring: Oppdater SYSTEM-prompten i agent.py

Legg til dette ETTER eksisterende system-prompt (linje 54 i agent.py):

```
EFFICIENCY RULES (critical for scoring):
- ONLY POST/PUT/DELETE/PATCH count as "write calls". GET is FREE.
- Your score is compared to the BEST solution's write count.
- Every EXTRA write call beyond minimum REDUCES your score.
- Every 4xx error response REDUCES your score.

STRATEGY:
1. PLAN first: determine the MINIMUM writes needed before making any calls
2. GET all needed data in your first turn (GETs are free)
3. Validate all required fields before POSTing
4. Execute writes precisely - no trial and error
5. Never retry a failed call with same data - analyze the error first

MINIMUM WRITES per common task:
- Create employee: 1 write (POST /employee, after GET /department)
- Create customer: 1 write (POST /customer)
- Create product: 1 write (POST /product)
- Create order: 1 write (POST /order, after GET /customer)
- Create invoice: 1 write (PUT /order/{id}/:invoice)
- Create project: 1 write (POST /project, after GET /employee for manager)
- Create voucher: 1 write (POST /ledger/voucher, after GET /ledger/account)
- Delete entity: 1 write (DELETE /entity/{id}, after GET to find ID)

REQUIRED FIELDS (prevents 422 errors):
- employee: firstName, lastName, department:{id:X} - GET /department first!
- customer: name, isCustomer:true
- order: customer:{id:X}, orderDate:"YYYY-MM-DD", deliveryDate:"YYYY-MM-DD"
- voucher: date, description, postings must sum to 0 (debit positive, credit negative)
```

## Estimert effekt
- Score per task: fra ~1.0x tier til ~1.5-1.8x tier
- **Total score-okning: 50-80%**
