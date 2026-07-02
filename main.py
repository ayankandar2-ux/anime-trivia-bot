"""
Daily Anime/Manga Trivia Bot
Fetches a random anime or manga from Jikan (MyAnimeList API), turns it into a
short trivia post (optionally polished by Gemini), and sends it to a Telegram
channel. Keeps a seen_ids.json to avoid repeating the same title too often.

Env vars required:
    TELEGRAM_BOT_TOKEN   - from @BotFather
    TELEGRAM_CHAT_ID     - e.g. @autoanime464 or a numeric chat id

Env vars optional:
    GEMINI_API_KEY       - if set, Gemini rewrites the fact into a punchier post
                            if not set, falls back to a plain template
"""

import json
import os
import random
import time
from pathlib import Path

import requests

JIKAN_BASE = "https://api.jikan.moe/v4"
SEEN_FILE = Path("seen_ids.json")
MAX_SEEN = 500  # keep the seen list from growing forever

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def load_seen():
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except json.JSONDecodeError:
            return {"anime": [], "manga": []}
    return {"anime": [], "manga": []}


def save_seen(seen):
    # trim to keep file small
    seen["anime"] = seen["anime"][-MAX_SEEN:]
    seen["manga"] = seen["manga"][-MAX_SEEN:]
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def fetch_random_entry(kind, seen_ids, max_attempts=8):
    """kind is 'anime' or 'manga'. Retries until it finds an unseen entry
    with usable text (synopsis or background), or gives up and returns
    whatever it last got."""
    last_data = None
    for _ in range(max_attempts):
        try:
            resp = requests.get(f"{JIKAN_BASE}/random/{kind}", timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data")
        except requests.RequestException:
            time.sleep(2)
            continue

        if not data:
            continue

        last_data = data
        entry_id = data.get("mal_id")
        has_text = bool(data.get("synopsis") or data.get("background"))

        if entry_id not in seen_ids and has_text:
            return data

        # Jikan has a soft rate limit (~3 req/sec, ~60/min)
        time.sleep(1.5)

    return last_data


def build_fact_text(kind, data):
    title = data.get("title") or data.get("title_english") or "Unknown Title"
    synopsis = (data.get("synopsis") or "").strip()
    background = (data.get("background") or "").strip()
    score = data.get("score")
    genres = ", ".join(g["name"] for g in data.get("genres", [])[:4])
    url = data.get("url", "")

    # Prefer background (trivia-flavored) text, fall back to synopsis
    body = background if background else synopsis
    if not body:
        body = "No extra details available for this one — just an interesting pick!"

    if GEMINI_API_KEY:
        polished = polish_with_gemini(kind, title, body, genres, score)
        if polished:
            return polished

    # Fallback template if no Gemini key or Gemini call failed
    snippet = body[:500].rsplit(".", 1)[0] + "." if len(body) > 500 else body
    lines = [
        f"📚 Today's {kind.capitalize()} Fact: {title}",
        "",
        snippet,
    ]
    if genres:
        lines += ["", f"🏷️ Genres: {genres}"]
    if score:
        lines += [f"⭐ MAL Score: {score}"]
    if url:
        lines += ["", url]
    return "\n".join(lines)


def polish_with_gemini(kind, title, body, genres, score):
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = (
        f"Write a short, engaging Telegram post (max 500 characters, no markdown "
        f"headers, can use a couple of emojis) sharing an interesting fact about "
        f"the {kind} '{title}'. Genres: {genres or 'N/A'}. MAL score: {score or 'N/A'}. "
        f"Base it on this info, but rewrite it in your own words, don't just copy it:\n\n{body[:1500]}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        resp = requests.post(endpoint, json=payload, timeout=30)
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if candidates:
            text = candidates[0]["content"]["parts"][0]["text"].strip()
            return text
    except (requests.RequestException, KeyError, IndexError):
        pass
    return None


def send_to_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": False},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    seen = load_seen()
    kind = random.choice(["anime", "manga"])
    seen_ids = set(seen[kind])

    data = fetch_random_entry(kind, seen_ids)
    if not data:
        print("Could not fetch a usable entry from Jikan after retries. Exiting.")
        return

    text = build_fact_text(kind, data)
    print("--- Post preview ---")
    print(text)
    print("--------------------")

    send_to_telegram(text)

    seen[kind].append(data.get("mal_id"))
    save_seen(seen)
    print(f"Posted {kind} #{data.get('mal_id')} ({data.get('title')}) and updated seen_ids.json")


if __name__ == "__main__":
    main()
