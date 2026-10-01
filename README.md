# Salon Ten website

The live website is **https://salonten.com.au/**, hosted on Vodien.
This repository's `main` branch is the live copy; every content change is made on the
`staging` branch first and checked on the test site at
**https://jeremy-andreani.github.io/salon-ten-site/** before it is merged to `main`
(see [STAGING.md](STAGING.md)).

Kellie can ask her Claude to edit the website on `staging`, check the preview, and then merge
`staging` into `main` to go live. After the one-time connection setup, **Deploy to Vodien**
publishes `main`, normally within a couple of minutes. Check the [Actions tab](https://github.com/jeremy-andreani/salon-ten-site/actions)
if an update does not appear, then refresh the live page.

- [STAGING.md](STAGING.md) explains the test-site workflow.
- [CLAUDE.md](CLAUDE.md) explains how to make and check edits.
- [.github/VODIEN-SETUP.md](.github/VODIEN-SETUP.md) has Jeremy's one-time setup steps.
- [.github/workflows/deploy-vodien.yml](.github/workflows/deploy-vodien.yml) runs publishing.

The connection is ready only after the workflow is on GitHub, its three secrets are set,
and its first deployment succeeds. A push alone is not proof of a live update.

The GitHub Pages address is the staging test site and shows the `staging` branch only; it is
hidden from search engines. Use `salonten.com.au` for customer links.

Publishing protects `old-wordpress/`, `cgi-bin/`, `.well-known/`, and `new-site-test/`.
Only public website files are staged; working notes, screenshots, the landing-page template
and repository configuration are not uploaded. No framework or package installation is needed.
