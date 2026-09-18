# Atlas Syria News Automation

Free news-monitoring workflow for **Atlas Syria**.

## Current v1
- Checks the official Syrian Ministry of Higher Education Telegram mirror.
- Baseline post ID: **13130**.
- Detects posts newer than the last processed ID.
- Stores candidate posts as JSON artifacts for editorial review.
- Does **not** publish automatically.
- Video production remains manual.

## Source
Official Telegram mirror: https://t.me/s/symoheasr

## Run
GitHub Actions → **Atlas Syria News Monitor** → **Run workflow**.

The scheduled workflow also runs every hour.

## Next stages
1. Relevance filtering for Atlas Syria.
2. Neutral Arabic editorial package + SEO.
3. 9:16 image generation using Atlas branding.
4. WordPress draft creation after credentials are configured securely.
