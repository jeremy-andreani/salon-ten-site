# Anne's website knowledge refresh

This kit belongs to the website repository so edits from Kellie or anyone else can refresh
Anne without Jarvis running. GitHub Actions runs it on changes pushed to main and on manual
dispatch. It exits with a notice while the ELEVENLABS_API_KEY repository secret is absent.

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

Auto-refresh requires only ELEVENLABS_API_KEY under Settings > Secrets and variables > Actions,
once these files are published. The local credential is in
~/.config/salon-receptionist/keys.env. Never copy its value into a repository file.
Do not enable a second copy of this automation in conductor against the same agent.
The site is not deployed by this workflow; the separate Deploy to Vodien workflow owns that.

These files are prepared locally only. Publishing this automation-only change must use a
commit message containing [skip ci], since the existing Vodien workflow triggers on every
push. That prevents publishing the website during this setup. Future site edits run normally.

The implementation source for maintenance is tools/salon-receptionist/refresh_kb.py in
conductor. Keep this installed copy in sync when that implementation changes. Staff facts in
this repository's knowledge-base.md are its own maintained source, not overwritten by code updates.
