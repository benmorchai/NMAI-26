# NM i AI 2026 – Komplett Strategi & Plan

**Deadline: Søndag 22. mars kl 15:00 CET**
**Gjenværende tid: ~41 timer (fra fredag kveld)**

---

## DE TRE OPPGAVENE – SAMMENDRAG

### Oppgave 1: Tripletex – AI Accounting Agent (33%)
**Hva:** Bygg en AI-agent som utfører regnskapsoppgaver i Tripletex.
**Hvordan:** Du eksponerer et HTTPS-endepunkt (`/solve`). De sender en POST med et regnskapsprompt (på 7 språk), vedlegg (PDF/bilder), og Tripletex API-credentials. Agenten din tolker promptet, gjør API-kall til Tripletex, og returnerer `{"status": "completed"}`.
**Scoring:**
- 30 ulike oppgavetyper, 56 varianter per oppgave (7 språk × 8 datasett)
- Felt-for-felt verifisering → correctness score (0-1)
- Multiplisert med tier (×1, ×2, ×3)
- Perfekt score + effektiv kode = bonus (opptil 2× tier)
- Max score per oppgave: 6.0 (Tier 3 perfekt + max effektivitet)
- Beste score per oppgave beholdes alltid
**Rate limits:** Verified: 3 samtidige, 10 per oppgave/dag. Unverified: 1 samtidig, 3 per oppgave/dag.
**Timeout:** 5 min (300 sek)
**Infrastruktur:** Du trenger en server som eksponerer HTTPS endpoint (kan bruke cloudflared tunnel lokalt)
**Tier 3 åpner:** Tidlig lørdag

### Oppgave 2: Astar Island – Norse World Prediction (33%)
**Hva:** Observer en norrøn sivilisasjonssimulator gjennom begrenset viewport og prediker sluttilstanden.
**Hvordan:** 40×40 grid, 50 års simulering. Du har 50 queries per runde (delt over 5 seeds). Hver query viser maks 15×15 celler. Submit en H×W×6 sannsynlighets-tensor per seed.
**Scoring:**
- Entropy-vektet KL-divergens mellom prediksjon og ground truth
- score = max(0, min(100, 100 × exp(-3 × weighted_kl)))
- 100 = perfekt, 0 = elendig
- VIKTIG: Aldri sett 0.0 sannsynlighet – bruk minimum 0.01 floor!
- Beste runde-score × runde-vekt = leaderboard-score
**6 terrain-klasser:** Empty(0), Settlement(1), Port(2), Ruin(3), Forest(4), Mountain(5)
**Stochastisk:** Samme kart gir ulike utfall hver gang
**Strategi:** Observer strategisk, forstå skjulte regler, bygg prediksjonsmodell

### Oppgave 3: NorgesGruppen Data – Object Detection (33%)
**Hva:** Detekter og klassifiser dagligvareprodukter på butikkhyller.
**Hvordan:** Last ned treningsdata (248 bilder, ~22700 COCO-annotasjoner, 356 kategorier). Tren en modell. Zip kode + weights. Last opp.
**Scoring:**
- 70% detection mAP@0.5 (fant du produktene?)
- 30% classification mAP@0.5 (riktig produkt?)
- Detection-only (category_id: 0 for alt) = maks 70% score
**Sandbox:** NVIDIA L4 GPU (24GB VRAM), Python 3.11, PyTorch 2.6, ultralytics 8.1.0
**Rate limits:** 3 submissions/dag, 2 samtidige
**Viktig:** run.py må ligge i rot av zip. Mange imports er blokkert (os, sys, subprocess osv.)
**Treningsdata:** ~864 MB COCO dataset + ~60 MB produktbilder

---

## VANSKELIGHETSRANGERING

| Oppgave | Vanskelighet | Tid til MVP | Poeng-potensial | Prioritet |
|---------|-------------|-------------|-----------------|-----------|
| Tripletex | ★★☆ Medium | 3-4 timer | Høyt (mange oppgaver å score på) | 🥇 #1 |
| Astar Island | ★★★ Vanskelig | 2-3 timer | Medium (krever god modell) | 🥈 #2 |
| NorgesGruppen | ★★☆ Medium | 4-6 timer (trening) | Medium-Høyt | 🥉 #3 |

**Hvorfor denne rekkefølgen:**
- **Tripletex først:** Mest iterativ – du kan submitte ofte og forbedre gradvis. Tier 1+2 er allerede åpne. Krever "bare" en LLM-agent + API-kall. Du kan bruke Claude som LLM-backend.
- **Astar Island #2:** Fascinerende ML-problem. 50 queries er begrenset, men du kan submitte uniform baseline umiddelbart for å unngå 0. Deretter forbedre.
- **NorgesGruppen #3:** Krever GPU-trening som tar tid. MEN: en enkel YOLOv8-modell med default settings kan gi ok score. Det tar bare lang tid å laste ned data + trene.

---

## TIDSPLAN

### FREDAG KVELD (nå → seng)
- [ ] Les gjennom dette dokumentet
- [ ] Sett opp GitHub repo (public, nm-ai-2026 eller lignende)
- [ ] Vipps-verifisering (KRITISK for rate limits)
- [ ] Valgfritt: Start på Tripletex-agent boilerplate

### LØRDAG (hoved-arbeidsdag)
**07:00-09:00 — Tripletex MVP**
- Sett opp FastAPI /solve endpoint
- Koble til Claude API som LLM-backend for prompt-tolkning
- Implementer grunnleggende Tripletex API-kall (employees, customers)
- Test med cloudflared tunnel
- SUBMIT første gang → få poeng på tavlen

**09:00-10:00 — Astar Island Baseline**
- Hent aktiv runde + initial states
- Submit uniform prediction (1/6 for alle klasser) for alle 5 seeds → unngå 0
- Bruk noen queries for å observere og forstå mekanikken

**10:00-12:00 — NorgesGruppen Starter**
- Last ned treningsdata (~864 MB)
- Start YOLOv8 trening (dette kan kjøre i bakgrunnen)
- Sett opp run.py boilerplate

**12:00-14:00 — Tilbake til Tripletex**
- Forbedre agenten: håndter flere oppgavetyper
- Legg til filhåndtering (PDF/bilde-vedlegg)
- Legg til flerspråklig støtte
- Submit og iterer

**14:00-16:00 — Astar Island Forbedring**
- Analyser observasjoner, forstå mechanics
- Bygg enkel prediksjonsmodell basert på initial state + observasjoner
- Submit forbedrede prediksjoner

**16:00-18:00 — NorgesGruppen Submit**
- YOLOv8-trening bør være ferdig
- Pakk modell + run.py
- Submit første versjon

**18:00-22:00 — Iterasjon på svakeste oppgave**
- Sjekk leaderboard, fokuser på laveste score
- Tripletex Tier 3 bør være åpen nå – prøv de vanskelige oppgavene

### SØNDAG (optimalisering)
**07:00-12:00 — Forbedring**
- Iterer på alle tre oppgaver
- Fokus på den med lavest normalisert score
- Finjuster Tripletex-agenten for efficiency bonus
- Forbedre Astar-modellen med bedre query-strategi
- Eventuelt retrain NorgesGruppen med bedre hyperparametre

**12:00-14:30 — Siste submits**
- Sørg for at alt er submittet
- Sjekk at GitHub repo er public med all kode
- Siste optimaliseringer

**14:30-15:00 — Buffer**
- Siste submits hvis noe gikk galt
- Verifiser leaderboard

---

## CLAUDE CODE PROMPTS

### Prompt 1: Prosjekt-oppsett
```
Jeg deltar i NM i AI 2026. Sett opp et Python-prosjekt med denne strukturen:

nm-ai-2026/
├── tripletex/
│   ├── agent.py          # FastAPI /solve endpoint
│   ├── tripletex_api.py  # Wrapper for Tripletex API calls
│   └── llm.py            # LLM integration for prompt parsing
├── astar/
│   ├── client.py         # API client for Astar Island
│   ├── predictor.py      # Prediction model
│   └── strategy.py       # Query strategy (which viewports to observe)
├── norgesgruppen/
│   ├── train.py          # YOLOv8 training script
│   ├── run.py            # Submission entry point
│   └── utils.py          # Helper functions
├── simulator/
│   └── dashboard.html    # Enkel visualiserings-hub
├── requirements.txt
├── .gitignore
└── README.md

Bruk Python 3.11. Legg til dependencies: fastapi, uvicorn, requests, numpy, anthropic (for Claude API), ultralytics.
```

### Prompt 2: Tripletex Agent MVP
```
Bygg en Tripletex AI accounting agent. Den skal:

1. Eksponere POST /solve endpoint via FastAPI
2. Ta imot JSON med: prompt (tekst), files (base64-vedlegg), tripletex_credentials (base_url, session_token)
3. Bruke Claude API (anthropic) til å tolke promptet og bestemme hvilke API-kall som trengs
4. Kalle Tripletex API via proxy (base_url) med Basic Auth (username: "0", password: session_token)
5. Returnere {"status": "completed"}

Oppgavetyper inkluderer: Opprett ansatt, opprett kunde, opprett faktura, registrer betaling, reiseregning, prosjekter, avdelinger, kreditnotaer.

Promptene kan komme på 7 språk: norsk, engelsk, spansk, portugisisk, nynorsk, tysk, fransk.

VIKTIG: Minimér API-kall og unngå 4xx-feil for efficiency bonus. Parse promptet grundig FØR du gjør kall.
```

### Prompt 3: Astar Island Baseline
```
Bygg en klient for Astar Island API (NM i AI 2026).

Base URL: https://api.ainm.no/astar-island
Auth: Bearer token (JWT fra cookie)

Oppgaven:
1. Hent aktiv runde via GET /rounds
2. Hent runde-detaljer med initial_states via GET /rounds/{round_id}
3. For hver av 5 seeds: submit en baseline prediction (uniform 1/6 for alle 6 klasser)
4. Bruk POST /submit med H×W×6 tensor

VIKTIG: Aldri sett probability til 0.0 – bruk minimum 0.01 floor og renormaliser.
Kartet er 40×40, 6 klasser: Empty(0), Settlement(1), Port(2), Ruin(3), Forest(4), Mountain(5).

Enkel forbedring: Bruk initial_state grid til å sette høyere sannsynlighet for statiske celler:
- Ocean (10) → Empty med høy sannsynlighet
- Mountain (5) → Mountain med høy sannsynlighet
- Forest (4) → Forest med høy sannsynlighet (men kan endres litt)
- Settlement (1) → fordel mellom Settlement, Ruin, Port
- Bruk observasjoner (50 queries) til å kalibrere sannsynlighetene
```

### Prompt 4: NorgesGruppen YOLOv8
```
Sett opp YOLOv8 object detection for NorgesGruppen dagligvare-oppgaven.

Treningsdata er COCO-format:
- 248 bilder av butikkhyller
- ~22700 annotasjoner
- 356 produktkategorier (+ unknown_product = 357 klasser totalt)
- bbox format: [x, y, width, height] i piksler

Oppgaver:
1. Konverter COCO-annotasjoner til YOLO-format
2. Tren YOLOv8m (medium) med ultralytics==8.1.0
3. Lag run.py som tar --input og --output argumenter
4. run.py skal laste modell, kjøre inference på alle bilder i input-mappen, og skrive predictions.json

VIKTIG sandbox-begrensninger:
- Pin ultralytics==8.1.0
- GPU: NVIDIA L4, 24GB VRAM
- Blokkerte imports: os, sys, subprocess, socket, pickle, yaml, osv
- Bruk pathlib istedenfor os
- Bruk json istedenfor yaml
- Max zip: 420 MB, max weights: 420 MB
```

### Prompt 5: Simulator/Dashboard
```
Lag en enkel web-basert dashboard (single HTML file) som visualiserer:

1. Tripletex status: Siste submits, score per oppgave, total score
2. Astar Island: Visualisering av 40×40 grid med fargekoder for terrengtyper, query-budget brukt
3. NorgesGruppen: Treningsprogress, siste submission score

Bruk HTML + vanilla JS + CSS. Dashboard skal kunne oppdateres manuelt (refresh).
Legg til en enkel logg-visning som viser siste handlinger.

Fargekoder for Astar:
- Ocean/Empty: blå/grå
- Settlement: rød
- Port: oransje
- Ruin: brun
- Forest: grønn
- Mountain: mørkegrå

Hold det enkelt men funksjonelt.
```

---

## KRITISKE HUSKEREGLER

1. **Aldri 0 på noen oppgave** – submit NOEN form for svar på alle 3
2. **Vipps-verifisering** – gir 3× rate limits og er påkrevd for premie
3. **GitHub repo MUST be public** – krav for premie-eligibilitet
4. **Astar: minimum 0.01 probability floor** – ellers KL-divergens = uendelig
5. **NorgesGruppen: run.py i ROOT av zip** – vanligste feil
6. **NorgesGruppen: blokkerte imports** – ikke bruk os, sys, subprocess, pickle, yaml
7. **Tripletex: Basic Auth med username "0"** – ikke glem dette
8. **Tripletex: Alle API-kall via proxy (base_url)** – ikke direkte til Tripletex
9. **Commit ofte** – du kan alltid rulle tilbake
10. **MCP docs-server:** `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`

---

## OVERGANG TIL STASJONÆR PC

For å fortsette på stasjonær PC i morgen:
1. Push alt til GitHub (eller bare åpne denne mappen hvis den er på samme maskin/cloud)
2. Installer Python 3.11, Node.js, Git
3. `pip install fastapi uvicorn requests numpy anthropic ultralytics`
4. `npm install -g cloudflared` (for Tripletex HTTPS tunnel)
5. Sett opp Claude Code med MCP: `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`
6. Kopier JWT token fra app.ainm.no (for Astar Island API)
7. Last ned NorgesGruppen treningsdata fra submit-siden

Alt i denne filen + promptene kan brukes direkte i Claude Code på stasjonær.
