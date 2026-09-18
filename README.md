# Atlas Syria News Automation

Free monitoring and WordPress-draft workflow for **Atlas Syria**.

## v2 pipeline

Official Telegram mirror → hourly GitHub Actions check → duplicate detection → Arabic higher-education relevance filter → WordPress **Draft**.

Baseline Telegram post ID is **13130**. Posts at or below the baseline are ignored. The workflow never publishes a WordPress post: created posts use `status=draft`.

## Source

Official Telegram mirror: https://t.me/s/symoheasr

## Required GitHub Actions secrets

Add these in repository **Settings → Secrets and variables → Actions**:

- `WP_SITE_URL` = `https://atlas-sy.com`
- `WP_USERNAME` = the WordPress user dedicated to automation
- `WP_APP_PASSWORD` = a WordPress Application Password for that user

Do not put passwords in repository files.

If the secrets are absent, monitoring still runs and WordPress creation is skipped safely.

## State and duplicate prevention

`data/state.json` stores the last seen Telegram ID, processed Telegram IDs, and normalized-text hashes. State is committed back by GitHub Actions only when it changes.

## Editorial safety

v2 copies only source-provided Telegram text into the WordPress draft and adds the official source link. It does not invent facts or automatically publish. Rich rewriting, SEO metadata beyond the excerpt, branded 9:16 image generation, and social scheduling remain review-stage enhancements.

## Manual run

GitHub → Actions → **Atlas Syria News Monitor** → **Run workflow**.

The schedule also runs hourly at minute 17 UTC.
