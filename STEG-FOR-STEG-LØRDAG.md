# LØRDAG MORGEN – Steg for steg

## FØRST: Oppsett (30 min)

### 1. Klon GitHub-repoet
```bash
git clone https://github.com/DITT-BRUKERNAVN/nm-ai-2026.git
cd nm-ai-2026
```

### 2. Installer det du trenger
```bash
pip install fastapi uvicorn requests numpy anthropic
npm install -g cloudflared
```

### 3. Legg inn MCP docs-server i Claude Code (valgfritt)
```bash
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```

### 4. Hent JWT-token
- Gå til app.ainm.no i Chrome
- Logg inn med Google
- Åpne DevTools (F12) → Application → Cookies → access_token
- Kopier verdien – du trenger denne for Astar Island API

---

## OPPGAVE-REKKEFØLGE

### STEG A: Astar Island Baseline (30 min) → Unngå 0-score
**Hvorfor først:** Det tar 15 min å submitte en uniform baseline. Gir deg score > 0 umiddelbart. Du trenger INGEN simulator for dette.

**Hva du gjør:**
1. Be Claude Code: "Lag et Python-script som kobler til Astar Island API og submitter en uniform baseline prediction."
2. Kjør scriptet
3. Sjekk score på leaderboard

**Steg-for-steg prompt til Claude Code:**
```
Lag et enkelt Python-script (astar_baseline.py) som:

1. Bruker requests med Bearer token auth mot https://api.ainm.no
2. Henter aktive runder fra GET /astar-island/rounds
3. Henter runde-detaljer fra GET /astar-island/rounds/{round_id}
4. For HVER av 5 seeds:
   - Lager en 40×40×6 prediction tensor
   - For statiske celler fra initial_state:
     - Ocean (10) / Plains (11) / Empty (0) → [0.90, 0.02, 0.02, 0.02, 0.02, 0.02]
     - Mountain (5) → [0.02, 0.02, 0.02, 0.02, 0.02, 0.90]
     - Forest (4) → [0.10, 0.02, 0.02, 0.02, 0.82, 0.02]
   - For settlements (1): [0.05, 0.50, 0.15, 0.25, 0.03, 0.02]
   - For ports (2): [0.05, 0.15, 0.50, 0.25, 0.03, 0.02]
   - Enforcer minimum 0.01 floor og renormaliserer
5. Submitter via POST /astar-island/submit
6. Printer respons for hver seed

Min JWT token er: [LIM INN HER]
```

**Etter dette:** Du har score på Astar. Gå videre.

---

### STEG B: Tripletex MVP (2-3 timer)

**Steg B1: Bare skjelettet (20 min)**
```
Lag en minimal FastAPI-app (tripletex/agent.py) med POST /solve endpoint.

Den skal:
1. Ta imot JSON body med prompt, files, tripletex_credentials
2. Logge promptet til konsollen
3. Returnere {"status": "completed"}

Legg til en health check GET / som returnerer {"status": "ok"}.

Ikke gjør noe annet ennå – bare ta imot requesten og returner completed.
```

Test: `uvicorn tripletex.agent:app --port 8000`
Test lokalt: `curl -X POST http://localhost:8000/solve -H "Content-Type: application/json" -d '{"prompt":"test","files":[],"tripletex_credentials":{"base_url":"http://test","session_token":"abc"}}'`

**Steg B2: Eksponere via HTTPS (10 min)**
```bash
cloudflared tunnel --url http://localhost:8000
```
Kopier HTTPS-URL-en som dukker opp, og lim den inn på app.ainm.no submission-siden.
Submit! Du vil nå se oppgaver komme inn (men agenten gjør ingenting ennå – den bare returnerer completed).

**Steg B3: Se hva som kommer inn (20 min)**
Nå ser du i konsoll-loggen hva slags prompts som sendes. Les noen.
Git commit: `git add . && git commit -m "Tripletex: minimal endpoint" && git push`

**Steg B4: Legg til LLM-tolkning (1-2 timer)**
```
Utvid /solve til å bruke Claude API (anthropic) for å tolke promptet.

1. Send promptet til Claude med system-prompt som forklarer at den skal
   tolke regnskapsoppgaver og bestemme API-kall
2. Bruk structured output / tool use for å få Claude til å returnere
   en liste med API-kall den vil gjøre
3. Utfør API-kallene mot Tripletex proxy (base_url) med Basic Auth
4. Returnere {"status": "completed"}

Start med kun: opprett ansatt (POST /employee) og opprett kunde (POST /customer).
Legg til flere oppgavetyper gradvis.
```

**Etter hvert submit:** Sjekk score. Legg til flere oppgavetyper. Iterer.

---

### STEG C: NorgesGruppen – Start trening i bakgrunnen (1 time setup, resten kjører selv)

**Steg C1: Last ned data**
Gå til app.ainm.no submit-siden for NorgesGruppen. Last ned:
- NM_NGD_coco_dataset.zip (~864 MB)
- NM_NGD_product_images.zip (~60 MB)

**Steg C2: Konverter og tren**
```
Sett opp YOLOv8 trening for NorgesGruppen object detection.

1. Pakk ut COCO-datasettet
2. Konverter COCO-format til YOLO-format (lag conversion script)
3. Splitt i train/val (90/10)
4. Start trening med ultralytics==8.1.0:
   - Model: yolov8m.pt
   - Epochs: 50 (kan økes senere)
   - Image size: 640
   - Batch size: auto
   - nc: 357 (356 kategorier + unknown_product)

La treningen kjøre i bakgrunnen mens du jobber med Tripletex.
```

**Steg C3: Lag submission (når trening er ferdig)**
```
Lag run.py for NorgesGruppen submission.

Krav:
- Kjøres som: python run.py --input /data/images --output /output/predictions.json
- Bruk pathlib (IKKE os) for filhåndtering
- Bruk json (IKKE yaml) for config
- Last YOLOv8 modell fra best.pt
- Kjør inference på alle bilder i input-mappen
- Skriv predictions.json i COCO-format:
  [{"image_id": int, "category_id": int, "bbox": [x,y,w,h], "score": float}]
- Image_id hentes fra filnavn (img_00042.jpg → 42)

Blokkerte imports: os, sys, subprocess, socket, pickle, yaml, shutil, builtins
```

---

## SIMULATOR / DASHBOARD

Bygg denne ETTER du har scores på alle 3 oppgaver, ikke før.
Den er nyttig, men poeng er viktigere enn visualisering.

Alternativt: Start med en enkel terminal-basert oversikt (print statements)
som viser hva som skjer, og bygg dashboard senere.

---

## HVORDAN SJEKKE RESULTATER

### Tripletex
- Leaderboard: app.ainm.no → Tripletex → Leaderboard
- Submission history: app.ainm.no → Tripletex → dine submissions med detaljert scoring

### Astar Island
- Leaderboard: app.ainm.no → Astar Island → Leaderboard
- Egne scores: GET /astar-island/my-rounds (viser score per runde/seed)
- Analyse etter runde: GET /astar-island/analysis/{round_id}/{seed_index}

### NorgesGruppen
- Leaderboard: app.ainm.no → NorgesGruppen → Leaderboard
- Submission history på submit-siden
- Offentlig leaderboard = public test set
- Finalen bruker privat test set (du kan velge hvilken submission som evalueres)

---

## GIT-WORKFLOW

Når noe funker:
```bash
git add .
git commit -m "Tripletex: kan opprette ansatte"
git push
```

Når du eksperimenterer:
```bash
git checkout -b eksperiment-astar-ml
# ... jobb ...
# Funker det? Merge:
git checkout main
git merge eksperiment-astar-ml
git push
# Funker det ikke? Gå tilbake:
git checkout main
```

Enkelt tips: Bare jobb på main og commit ofte. Du kan alltid `git log` og
`git checkout <commit-hash>` for å gå tilbake.
