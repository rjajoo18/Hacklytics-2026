"""
Chatbot API router — Snowflake Cortex integration.

Endpoint
--------
POST /api/chatbot/chat
    Body:     { "message": str, "history": [{"role": str, "content": str}, ...] }
    Response: { "response": str }

Required env vars (add to project-root .env or .env.local):
    SNOWFLAKE_ACCOUNT   e.g.  "xy12345.us-east-1"
    SNOWFLAKE_USER      e.g.  "JDOE"
    SNOWFLAKE_PASSWORD  your Snowflake password or key-pair private key passphrase
    SNOWFLAKE_HOST      e.g.  "xy12345.snowflakecomputing.com"
    SNOWFLAKE_ROLE      e.g.  "SYSADMIN"
    SNOWFLAKE_MODEL     (optional) defaults to "llama3.1-8b"
                        Other options: mistral-large2 | llama3.1-70b | claude-3-5-sonnet
"""

from __future__ import annotations

import os

import snowflake.connector
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

_ACCOUNT  = os.getenv("SNOWFLAKE_ACCOUNT",  "")
_USER     = os.getenv("SNOWFLAKE_USER",     "")
_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD", "")
_HOST     = os.getenv("SNOWFLAKE_HOST",     "")
_ROLE     = os.getenv("SNOWFLAKE_ROLE",     "")
_MODEL    = os.getenv("SNOWFLAKE_MODEL",    "llama3.1-8b")

_SYSTEM_PROMPT = (
    "You are Quantara, a supply chain risk analyst specializing in U.S. tariff policy. "
    "Answer the user's question using the tariff data context provided. "
    "If the answer is not in the data, say you don't know. "
    "Be concise and analytical."
)


# ── Request / Response models ──────────────────────────────────────────────────

class Message(BaseModel):
    role: str      # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    response: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _connect() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        user=_USER,
        password=_PASSWORD,
        account=_ACCOUNT,
        host=_HOST,
        port=443,
        role=_ROLE,
    )


def _get_tariff_context(cursor) -> str:
    try:
        cursor.execute(
            "SELECT * FROM HACKLYTICS_DB.PUBLIC.COUNTRY_TARIFF_RISK LIMIT 500;"
        )
        rows = cursor.fetchall()
        context = "Tariff Risk Data Context:\n"
        for row in rows:
            context += f"{row}\n"
        return context
    except Exception:
        return "No tariff data available."


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Send a message to the Snowflake Cortex LLM with tariff data context injected.
    """
    if not all([_ACCOUNT, _USER, _PASSWORD, _HOST]):
        raise HTTPException(
            status_code=503,
            detail=(
                "Snowflake credentials not configured. "
                "Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, "
                "and SNOWFLAKE_HOST in the project .env or .env.local file."
            ),
        )

    try:
        conn   = _connect()
        cursor = conn.cursor()

        tariff_data = _get_tariff_context(cursor)

        augmented_prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"{tariff_data}\n\n"
            f"User Question: {req.message}"
        )

        # Escape single quotes so they don't break the SQL string literal
        escaped = augmented_prompt.replace("'", "\\'")
        cursor.execute(
            f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{_MODEL}', '{escaped}')"
        )
        result = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return ChatResponse(response=result)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snowflake Cortex error: {exc}")


@router.get("/health")
async def chatbot_health() -> dict:
    """Check whether Snowflake credentials are present (does not actually connect)."""
    configured = all([_ACCOUNT, _USER, _PASSWORD, _HOST])
    return {"configured": configured, "model": _MODEL}
