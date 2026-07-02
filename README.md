# Anime/Manga Trivia Bot

Posts one random anime or manga fact to a Telegram channel every day, powered by
the free [Jikan API](https://docs.api.jikan.moe/) (MyAnimeList data) and
optionally polished by Gemini 2.0 Flash. Runs entirely on GitHub Actions —
zero hosting cost.

## How it works

1. Picks `anime` or `manga` at random each run.
2. Calls Jikan's `/random/{kind}` endpoint until it finds a title not in
   `seen_ids.json` that has a synopsis or background text.
3. If `GEMINI_API_KEY` is set, sends that text to Gemini to rewrite as a short,
   punchy post. Otherwise falls back to a plain template.
4. Posts to your Telegram channel via the Bot API.
5. Appends the title's MAL id to `seen_ids.json` and the workflow commits that
   file back to the repo, so you won't get true repeats until ~500 posts in.

## Setup

1. **Create/reuse a Telegram bot** via [@BotFather](https://t.me/BotFather) —
   grab the bot token.
2. **Add the bot as admin** to your target channel (e.g. `@autoanime464`) so it
   can post.
3. In your GitHub repo, go to **Settings → Secrets and variables → Actions**
   and add:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID` — e.g. `@autoanime464` or the numeric chat id
   - `GEMINI_API_KEY` — optional, omit to use the plain template instead
4. Push this repo to GitHub. The workflow runs daily at 14:00 UTC
   (7:30 PM IST) — edit the cron line in
   `.github/workflows/daily-trivia.yml` to change the time.
5. To test immediately without waiting for the cron: go to the **Actions**
   tab → **Daily Anime/Manga Trivia Post** → **Run workflow**.

## Local test

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=xxx
export TELEGRAM_CHAT_ID=@your_channel
export GEMINI_API_KEY=xxx   # optional
python main.py
```

## Notes

- Jikan has no auth but does rate-limit (~3 req/sec, ~60/min) — the script
  already paces retries with small sleeps.
- If Jikan is temporarily down, the run just skips posting that day rather
  than failing loudly — check the Actions log if a day looks quiet.
