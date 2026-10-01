# Staging test site

| | Address | Branch | Updates when |
|---|---|---|---|
| **Test site (staging)** | https://jeremy-andreani.github.io/salon-ten-site/ | `staging` | you push to `staging` |
| **Live website** | https://salonten.com.au/ | `main` | you push or merge to `main` |

The test site is hidden from Google (noindex plus a robots.txt block) and has the Google Ads,
Google Analytics and Meta Pixel tracking switched off, so testing never touches live data or
ad reporting. It is built on GitHub, so it does not depend on anyone's computer being on.

## The workflow

1. **Work on `staging`.** `git checkout staging && git pull`. If `main` has moved on, run
   `git merge origin/main` so `staging` includes it.
2. **Make the change and push to `staging`.** The **Deploy staging preview** workflow runs
   (Actions tab) and takes about a minute.
3. **Check the preview URL** above once the workflow shows a green tick. Hard-refresh
   (Cmd+Shift+R) and check on a phone.
4. **Go live only when it looks right:** open a pull request from `staging` into `main` and
   merge it, or merge `staging` into `main` and push. **Deploy to Vodien** then publishes it.
5. **Check the live page** at salonten.com.au.

**Never push straight to `main` for untested changes.** `main` goes live within minutes.

## How it is wired (for reference, do not change in a content edit)

- `.github/workflows/staging-preview.yml` builds the same files as production
  (`build_site.py`), runs `.github/scripts/stage_site.py` on the copy, and publishes it to GitHub
  Pages. It only runs for pushes to `staging`.
- `stage_site.py` adds `<meta name="robots" content="noindex, nofollow">` to every page, writes a
  `robots.txt` that disallows everything, and removes the ad/analytics tags. It changes only the
  build copy, never the files in git, so what is merged to `main` is exactly what was written.
- **Deploy to Vodien** runs only for `main`. It never runs for `staging`.
- Pages deployments are limited to the `staging` branch in the repository's `github-pages`
  environment settings.
