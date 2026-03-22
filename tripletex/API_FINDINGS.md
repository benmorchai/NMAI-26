# Tripletex API Findings - Testet mot sandbox 2026-03-22

## KRITISKE BUGS I AGENT.PY

### Bug 1: Voucher row starter fra 0 - MÅ være 1+
```
FEIL (gir 422): postings: [{row: 0, ...}, {row: 1, ...}]
RIKTIG:         postings: [{row: 1, ...}, {row: 2, ...}]
```
Feilmelding: "Posteringene på rad 0 (guiRow 0) er systemgenererte"

### Bug 2: userType mangler i system-prompt for employee
- `NO_ACCESS` - fungerer, krever IKKE email
- `STANDARD` - fungerer, krever email
- `EXTENDED` - fungerer, krever email
- `ADMINISTRATOR` - FUNGERER IKKE (ugyldig verdi)
- Agenten sier "userType: NO_ACCESS" i prompt, men noen tasks krever admin-rolle

### Bug 3: Payment registrering - feil API-format
```
FEIL:   PUT /invoice/{id}/:payment med JSON body {paymentDate, amount}
RIKTIG: PUT /invoice/{id}/:payment?paymentDate=YYYY-MM-DD&paymentTypeId=ID&paidAmount=BELØP
```
Payment bruker QUERY PARAMS, ikke body! Og feltet heter `paidAmount` ikke `amount`.

### Bug 4: Payment krever paymentTypeId
Tilgjengelige betalingstyper (GET /invoice/paymentType):
- 36329010: Kontant
- 36329011: Betalt til bank
NB: IDene er UNIKE per sandbox-konto! Agenten må GET /invoice/paymentType først.

## RIKTIGE API-KALL (verifisert)

### Customer (1 write)
```
POST /customer
{name: "Navn AS", isCustomer: true, email: "epost@firma.no"}
```

### Supplier (1 write)
```
POST /supplier
{name: "Leverandør AS", email: "lev@firma.no"}
```

### Employee (1 write, GET department først)
```
GET /department?fields=id,name&count=20  (gratis)
POST /employee
{firstName: "Ola", lastName: "Nordmann", department: {id: DEPT_ID}, userType: "NO_ACCESS"}
```
- userType PÅKREVD! Gyldige: NO_ACCESS, STANDARD, EXTENDED
- STANDARD/EXTENDED krever email-felt
- For admin-rolle: bruk STANDARD + sett rolle separat

### Order + Invoice (2 writes)
```
POST /order
{customer: {id: CUST_ID}, orderDate: "YYYY-MM-DD", deliveryDate: "YYYY-MM-DD",
 orderLines: [{description: "Tjeneste", count: 1, unitPriceExcludingVatCurrency: 10000}]}

PUT /order/{ORDER_ID}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=false
```

### Invoice Payment (1 write, GET paymentType først)
```
GET /invoice/paymentType  (gratis - hent tilgjengelige betalingstyper)
PUT /invoice/{INVOICE_ID}/:payment?paymentDate=YYYY-MM-DD&paymentTypeId=PT_ID&paidAmount=BELØP
```
NB: Query params, IKKE JSON body!

### Voucher (1 write, GET /ledger/account først)
```
GET /ledger/account?fields=id,number,name&count=500  (gratis)
POST /ledger/voucher
{date: "YYYY-MM-DD", description: "Beskrivelse",
 postings: [
   {row: 1, account: {id: ACCT_ID}, amount: 5000, amountCurrency: 5000,
    amountGross: 5000, amountGrossCurrency: 5000, description: "Debit"},
   {row: 2, account: {id: ACCT_ID}, amount: -5000, amountCurrency: -5000,
    amountGross: -5000, amountGrossCurrency: -5000, description: "Credit"}
 ]}
```
VIKTIG: row starter fra 1! Positive=debit, negative=credit. Sum MÅ = 0.

### Travel Expense (1 write)
```
POST /travelExpense
{employee: {id: EMP_ID}, title: "Reisebeskrivelse"}
```
NB: Feltnavnene er IKKE departureDate/returnDate!

### Delete (1 write, GET for å finne ID først)
```
GET /{entity}?fields=id,name  (gratis)
DELETE /{entity}/{ID}
```

## VANLIGE KONTONUMMER (for vouchers)
- 1500 Kundefordringer
- 1920 Bankinnskudd
- 2400 Leverandørgjeld
- 2710 Inngående merverdiavgift, høy sats
- 3000 Salgsinntekt, avgiftspliktig
- 5000 Lønn til ansatte
- 6300 Leie lokale
- 7300 Salgskostnad

## DUPLIKATER I SANDBOX (agenten lager nye i stedet for å sjekke)
- 13 departments (4x Økonomi, 4x Lager, 4x IT)
- 5x "Geir Neset" employee
- 3x "Vestfjord AS" customer
- 17 ordrer uten faktura

## OPPDATERING TIL SYSTEM PROMPT

Legg til i SYSTEM-strengen i agent.py (etter linje 54):

```
CRITICAL API RULES:
- Voucher postings: row starts at 1, NOT 0! Row 0 is system-reserved.
- Employee: userType is REQUIRED. Valid: "NO_ACCESS" (no email needed), "STANDARD" (email required), "EXTENDED" (email required).
- Payment: PUT /invoice/{id}/:payment?paymentDate=YYYY-MM-DD&paymentTypeId=ID&paidAmount=AMOUNT (query params, NOT body!)
- Payment: GET /invoice/paymentType first to find valid paymentTypeId values.
- Order lines: include in POST /order body, not separate call.
- Travel expense: POST /travelExpense {employee:{id:X}, title:"desc"} - minimal fields needed.
- DELETE: always GET first to find the ID, then DELETE /{entity}/{id}.
- Before creating ANY entity, GET first to check if it already exists!

EFFICIENCY RULES:
- ONLY POST/PUT/DELETE/PATCH count as "write calls". GET is FREE.
- Every EXTRA write call beyond minimum REDUCES your score.
- Every 4xx error response REDUCES your score.
- PLAN first: determine the MINIMUM writes needed before making any calls.
- GET all needed data in your first turn (GETs are free).
```
