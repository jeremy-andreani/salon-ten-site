# Salon Ten website

The live website is **https://salonten.com.au/**, hosted on Vodien.
This repository's `main` branch is the master copy for every content change.

Kellie can ask her Claude to edit the website, check the change, and push it to `main`.
After the one-time connection setup, **Deploy to Vodien** publishes the changes, normally
within a couple of minutes. Check the [Actions tab](https://github.com/jeremy-andreani/salon-ten-site/actions)
if an update does not appear, then refresh the live page.

- [CLAUDE.md](CLAUDE.md) explains how to make and check edits.
- [.github/VODIEN-SETUP.md](.github/VODIEN-SETUP.md) has Jeremy's one-time setup steps.
- [.github/workflows/deploy-vodien.yml](.github/workflows/deploy-vodien.yml) runs publishing.

The connection is ready only after the workflow is on GitHub, its three secrets are set,
and its first deployment succeeds. A push alone is not proof of a live update.

The previous GitHub Pages address is a preview only. Its settings have been left unchanged;
use `salonten.com.au` for all owner checks and customer links. The preview should be retired
separately after publishing to Vodien is working, to avoid two apparent live sites.

Publishing protects `old-wordpress/`, `cgi-bin/`, `.well-known/`, and `new-site-test/`.
Only public website files are staged; working notes, screenshots, the landing-page template
and repository configuration are not uploaded. No framework or package installation is needed.
