# Anne's website knowledge and booking refresh

This kit belongs to the website repository so edits from Kellie or anyone else can refresh
Anne without Jarvis running. The Deploy to Vodien workflow calls this reusable workflow only
after a successful website upload, on pushes to main or manual dispatch of Deploy to Vodien.
The refresh checks out the exact revision uploaded, not a newer revision that arrives mid-run.
The deploy workflow's concurrency covers both the website upload and Anne's refresh.
Missing credentials fail the run visibly.

Each run regenerates the website treatment links, downloads Kitomba's public service catalogue,
replaces and verifies Anne's ElevenLabs knowledge document, and builds and deploys the Twilio
Functions with both lookup assets. Public catalogue requests do not read clients or bookings.
The Functions deploy reuses the production Sync service even on an empty runner, so existing
message records and booking cooldowns stay in place. It never writes or deletes
SALON_OWNER_NOTIFY_NUMBER and verifies that the live setting is unchanged.

Staff-only facts belong in the Staff clarifications (hand-maintained, keep on refresh) section
of knowledge-base.md. The complete section is preserved verbatim. Existing Unknown entries
are retained; the old IPL unknown-price entry deliberately withholds the website price until
staff resolve it. The women-only Brazilian waxing restriction is also retained beside the price.

The script uses only Python's standard library. It reads pages from the root of this repository
and prints a diff, then creates a replacement ElevenLabs text document, attaches it to Anne,
verifies by GET, updates its local state and deletes the old document. Failed or uncertain
attachment never triggers deletion. Unrelated knowledge documents and agent settings are kept.

Local preview, with no API calls or writes:

```sh
python3 .github/receptionist/refresh_kb.py --site-dir . --dry-run
```

Auto-refresh requires these repository secrets: ELEVENLABS_API_KEY, TWILIO_ACCOUNT_SID,
TWILIO_AUTH_TOKEN and SALON_WEBHOOK_SECRET. The sender number is reused from the existing
production Twilio environment. The local credentials are in
~/.config/salon-receptionist/keys.env. Never copy their values into a repository file or log.
SALON_OWNER_NOTIFY_NUMBER is intentionally not a workflow input or repository secret.
Do not enable a second copy of this automation in conductor against the same agent.

verify-deployment.py fetches the new document's actual content and compares it with the
generated file, confirms the production build includes the uploaded Function and asset
versions, and exercises both lookup assets through authenticated dry-run requests. The
catalogue check selects combined brow/lash service 15822; the website check compares a current
treatment's generated URL. Both use the isolated dry-run cooldown map and send no SMS.
The run summary records the live document ID, content hash, build ID and lookup counts.

Twilio lookup assets remain private. If Kitomba retires verification service 15822, review
the verification treatment before changing the check. A provider or verification failure
fails the workflow; an earlier successful provider update is not automatically rolled back.

Offline regression checks against the current website:

```sh
SALON_SITE_DIR=. python3 -m unittest discover -s .github/receptionist -p 'test_*.py'
node --test .github/receptionist/test_send_booking_link.js
```

CI runs deployment safety tests and Function syntax checks. Website extraction tests with
fixed price/hour fixtures are maintenance checks, not a gate on Kellie's valid content edits.

The implementation source for maintenance is tools/salon-receptionist/ in conductor.
Keep the installed scripts, Functions and tests in sync when that implementation changes. Staff facts in
this repository's knowledge-base.md are its own maintained source, not overwritten by code updates.
