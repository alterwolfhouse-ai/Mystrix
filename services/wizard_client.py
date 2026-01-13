from __future__ import annotations

import json
from typing import Dict, List, Optional

import httpx

from settings import settings


def compose_prompt(bars_snapshot: Dict, features_snapshot: Dict, news_envelope: Dict) -> str:
    system = (
        "You are MystriX’s Wizard, a crypto market analyst.\n"
        "Base conclusions ONLY on supplied BARS/FEATURES and NEWS. Do not invent data.\n"
        "Return exactly four sections: Recap, Drivers, Scenarios, Uncertainty.\n"
        "Be concise and concrete. Tie NEWS timings to price inflections when possible."
    )
    payload = {
        "BARS/FEATURES (snapshot)": bars_snapshot | {"features": features_snapshot},
        "NEWS": [
            {
                "published_at": n.get("published_at"),
                "source": n.get("source"),
                "credibility": n.get("credibility"),
                "relevance": n.get("relevance"),
                "title": n.get("title"),
                "summary": n.get("summary_1s"),
                "stance": n.get("stance"),
                "sentiment": n.get("sentiment"),
                "alignment": (n.get("time_alignment") or {}),
            }
            for n in news_envelope.get("news_items", [])
        ],
        "KNOWN FUTURE EVENTS": news_envelope.get("known_future_events", []),
        "USER QUESTION": news_envelope.get("user_question"),
        "TASK": [
            "1) Recap recent structure and regime.",
            "2) Drivers: which news likely mattered and why (use stance/sentiment/credibility + alignment).",
            "3) Scenarios: 2–3 forward paths; reference known future events if relevant; add invalidation points.",
            "4) Uncertainty: key unknowns and what evidence to watch next.",
        ],
    }
    # For LLMs that expect a single user string, we include the system header at the top
    return system + "\n\n" + json.dumps(payload, ensure_ascii=False)


def _detect_ollama_model(client: httpx.Client) -> Optional[str]:
    try:
        tags = client.get(settings.WIZARD_BASE_URL.replace("/chat", "/tags")).json()
        models = [t.get("name") for t in tags.get("models", [])] if isinstance(tags, dict) else []
        # Prefer general reasoning models
        for candidate in ("llama3.1:8b", "llama3", "llama3.1", "qwen2.5", "mistral", "phi-3"):
            for m in models:
                if m.startswith(candidate):
                    return m
        return models[0] if models else None
    except Exception:
        return None


def _ollama_chat(prompt: str) -> str | None:
    try:
        # Use a small local model if available; default to 'llama3' tag if present
        with httpx.Client(timeout=30) as client:
            model = _detect_ollama_model(client)
            if not model:
                return None
            body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
            r = client.post(settings.WIZARD_BASE_URL, json=body)
            r.raise_for_status()
            data = r.json()
            # Ollama returns {'message': {'content': '...'}}
            if isinstance(data, dict):
                msg = data.get("message") or {}
                content = msg.get("content")
                if content:
                    return content
            return None
    except Exception:
        return None


def call_wizard(prompt: str) -> str:
    # Try Ollama/local first
    out = _ollama_chat(prompt)
    if out:
        return out
    # Fallback stub
    return (
        "## Recap\n"
        "Market shows mixed momentum; features and recent bars suggest range with spikes.\n\n"
        "## Drivers\n"
        "Ranked news likely influenced intraday pivots based on timing and stance.\n\n"
        "## Scenarios\n"
        "1) Bull continuation if key resistance breaks.\n2) Range persists; fade extremes.\n3) Breakdown if macro headwinds intensify.\n\n"
        "## Uncertainty\n"
        "Liquidity pockets, event risk timing, and sentiment breadth."
    )


def _ollama_chat_messages(messages: List[Dict], options: Optional[Dict] = None) -> Optional[str]:
    try:
        with httpx.Client(timeout=60) as client:
            model = _detect_ollama_model(client)
            if not model:
                return None
            body = {"model": model, "messages": messages, "stream": False}
            if options:
                body["options"] = options
            r = client.post(settings.WIZARD_BASE_URL, json=body)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                msg = data.get("message") or {}
                content = msg.get("content")
                if content:
                    return content
            return None
    except Exception:
        return None


def call_wizard_messages(messages: List[Dict], options: Optional[Dict] = None) -> str:
    out = _ollama_chat_messages(messages, options=options)
    if out:
        return out
    # Fallback long-form stub
    return (
        "## Market Brief\n"
        "The market exhibits a mixture of trending and consolidating behavior, with momentum oscillators and volume providing context on potential inflection points.\n\n"
        "## Technical Context\n"
        "RSI, MACD, ATR, and ROC metrics frame the immediate regime and likely path dependency. Price structure around recent swing highs/lows provides tactical levels.\n\n"
        "## Scenarios\n"
        "1) Continuation with momentum confirmation.\n2) Mean-reversion inside a maturing range.\n3) Breakdown toward prior liquidity pockets.\n\n"
        "## Watchpoints\n"
        "Monitor momentum shifts near key levels and whether volume confirms or rejects the move."
    )
