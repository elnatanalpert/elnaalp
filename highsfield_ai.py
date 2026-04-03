"""
Highsfield AI — Claude API wrapper
Exposes utility functions for cold outreach: compose emails, find leads, chat.
"""

from __future__ import annotations

import os
from typing import Iterator

import anthropic

_client: anthropic.Anthropic | None = None

MODEL = "claude-opus-4-6"

SYSTEM_OUTREACH = (
    "אתה מומחה שיווק B2B של Highsfield AI. "
    "אתה כותב מיילים קרים (cold emails) קצרים, אישיים ומשכנעים בעברית ובאנגלית. "
    "תמיד מתייחס לנישה ולשם החברה של הליד."
)

SYSTEM_LEADS = (
    "אתה מומחה מחקר עסקי. "
    "אתה מוצא לקוחות פוטנציאליים לפי נישה ומחזיר JSON תקין בלבד. "
    "כל ליד: {name, website, email_guess, niche, reason}."
)


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_email(
    company: str,
    contact_name: str = "",
    niche: str = "",
    language: str = "he",
    extra_context: str = "",
) -> str:
    """
    Compose a personalised cold email for a lead.

    Parameters
    ----------
    company:       Company / organisation name.
    contact_name:  First name of the contact (optional).
    niche:         Business niche (e.g. 'ארגונים', 'עמותות').
    language:      'he' for Hebrew, 'en' for English.
    extra_context: Any additional information about the lead.

    Returns
    -------
    The generated email text as a string.
    """
    lang_instruction = "כתוב בעברית." if language == "he" else "Write in English."
    greeting = f"לכבוד {contact_name} מ-{company}" if contact_name else f"לכבוד צוות {company}"

    prompt = (
        f"{lang_instruction}\n"
        f"כתוב cold email קצר (עד 120 מילה) בשביל:\n"
        f"חברה/ארגון: {company}\n"
        f"נישה: {niche or 'לא צוין'}\n"
        f"פנייה: {greeting}\n"
        f"הקשר נוסף: {extra_context or 'אין'}\n\n"
        "המייל צריך להכיל: שורת נושא, גוף קצר ופנייה לפגישה."
    )

    client = _get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_OUTREACH,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_message().content[0].text


def find_leads(niche: str, count: int = 10) -> list[dict]:
    """
    Ask Claude to generate a list of potential leads for a given niche.

    Parameters
    ----------
    niche:  Business niche to target (e.g. 'עמותות', 'רשתות קמעונאות').
    count:  How many leads to generate (default 10).

    Returns
    -------
    List of lead dicts with keys: name, website, email_guess, niche, reason.
    Raises ValueError if the response cannot be parsed as JSON.
    """
    import json

    prompt = (
        f"מצא {count} לקוחות פוטנציאליים בנישת: {niche}.\n"
        "החזר JSON בלבד — רשימת אובייקטים עם שדות: "
        "name, website, email_guess, niche, reason.\n"
        "אל תוסיף שום טקסט מחוץ ל-JSON."
    )

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_LEADS,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        leads = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned invalid JSON: {exc}\n\nRaw response:\n{raw}") from exc

    return leads


def chat(prompt: str, system: str = "", stream: bool = False) -> str | Iterator[str]:
    """
    General-purpose chat with Claude.

    Parameters
    ----------
    prompt:  User message.
    system:  Optional system prompt override.
    stream:  If True, returns a generator that yields text chunks.

    Returns
    -------
    Full response string, or a generator of text chunks when stream=True.
    """
    client = _get_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = dict(
        model=MODEL,
        max_tokens=4096,
        messages=messages,
    )
    if system:
        kwargs["system"] = system

    if stream:
        def _stream_gen() -> Iterator[str]:
            with client.messages.stream(**kwargs) as s:
                for text in s.text_stream:
                    yield text
        return _stream_gen()

    response = client.messages.create(**kwargs)
    return response.content[0].text


def analyze(text: str, task: str = "סכם את הטקסט הבא בקצרה") -> str:
    """
    Analyse or summarise arbitrary text.

    Parameters
    ----------
    text:  Input text to analyse.
    task:  Instruction for Claude (default: summarise).

    Returns
    -------
    Analysis/summary as a string.
    """
    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": f"{task}:\n\n{text}"}],
    )
    return response.content[0].text
