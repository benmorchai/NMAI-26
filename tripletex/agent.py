#!/usr/bin/env python3
"""
Tripletex AI Accounting Agent - NM i AI 2026
FastAPI endpoint that receives accounting tasks and executes them via Tripletex API.

Steg 1: Skeleton - bare mottar og logger requests.
"""

import logging
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("tripletex-agent")

# --- FastAPI app ---
app = FastAPI(title="Tripletex AI Agent", version="0.1.0")


@app.get("/")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "tripletex-ai-agent",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/solve")
async def solve(request: Request):
    """
    Main endpoint called by the NM i AI platform.

    Request body:
    {
        "prompt": "Create an employee named ...",
        "files": [
            {"filename": "invoice.pdf", "mime_type": "application/pdf", "data": "base64..."}
        ],
        "tripletex_credentials": {
            "base_url": "https://<proxy>/v2",
            "session_token": "abc123..."
        }
    }

    Response:
    {"status": "completed"}
    """
    body = await request.json()

    # Extract fields
    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})
    base_url = creds.get("base_url", "N/A")
    session_token = creds.get("session_token", "N/A")

    # Log what we received
    logger.info("=" * 60)
    logger.info("NEW TASK RECEIVED")
    logger.info("=" * 60)
    logger.info(f"Prompt: {prompt[:500]}")
    logger.info(f"Files: {len(files)}")
    for f in files:
        fname = f.get("filename", "unknown")
        ftype = f.get("mime_type", "unknown")
        fsize = len(f.get("data", ""))
        logger.info(f"  - {fname} ({ftype}, {fsize} chars base64)")
    logger.info(f"Base URL: {base_url}")
    logger.info(f"Session token: {session_token[:10]}..." if len(session_token) > 10 else f"Session token: {session_token}")
    logger.info("=" * 60)

    # TODO: Steg 2 - Parse prompt med LLM og utfør Tripletex API-kall
    # For nå: bare returner completed
    logger.info("Returning status: completed (skeleton - no action taken)")

    return JSONResponse({"status": "completed"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
