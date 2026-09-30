# Deploy checklist: GA4 analytics (branch `ga4-analytics`)

Status: prepared locally, NOT pushed, NOT deployed. Pushing `main` auto-deploys to Vodien via
`.github/workflows/deploy-vodien.yml`; this branch does not trigger it (the workflow runs on `main` only).

## What the branch does
- All 36 pages: GA4 `config` wired into the existing single gtag.js load (AW-976595232 stays the loader;
  Meta Pixel untouched). It stays inert until the placeholder is replaced with a real `G-` ID.
- `conversion.js`, on every `kitomba.com` link (booking, apps.kitomba.com and voucher): GA4 event
  `book_now_click` (params `link_url`, `page_path`), the existing Google Ads conversion, and the Meta
  `Schedule` event (previously apps.kitomba.com only).

## Steps
1. Create the GA4 property and web data stream for https://salonten.com.au (Australia/Sydney, AUD),
   link it to Google Ads AW-976595232, and note the `G-` measurement ID
   (see `tenants/conductor/salon-ten-ga4-setup-chrome-prompt.md` in the conductor repo).
2. On branch `ga4-analytics`, substitute the ID in one command:
   `grep -rl "'GA4_MEASUREMENT_ID'" --include='*.html' . | xargs sed -i '' "s/'GA4_MEASUREMENT_ID'/'G-XXXXXXXXXX'/"`
   (macOS sed; use your real ID). Check: `grep -rl "'GA4_MEASUREMENT_ID'" --include='*.html' .` returns nothing
   and `grep -rl "'G-XXXXXXXXXX'" --include='*.html' . | wc -l` returns 36.
3. Commit, merge to `main`, push. Wait for the **Deploy to Vodien** workflow to go green.
4. Verify on https://salonten.com.au (not the GitHub Pages preview): view source shows the `G-` ID, and
   GA4 Admin > DebugView / Realtime shows `page_view`; click a Book Now link and confirm `book_now_click`.
5. In GA4 Admin > Events, mark `book_now_click` as a key event. Optionally import the GA4 key event into Google Ads.
6. Confirm the existing Google Ads conversion and Meta Pixel (Events Manager test) still fire.

## Rollback
Revert the merge commit on `main` and push; the workflow redeploys the previous pages.
