# Salon Ten website - working notes for Claude Code

This file is read automatically by Claude Code at the start of a session in this repo. It's here
so you (Kellie's Claude) know how the site is built and what conventions to follow before making
any change.

## What this is

A plain static HTML/CSS website for Salon Ten (Mount Hutton, NSW) - no build tools, no framework,
no server-side code. Every page is a hand-written `.html` file that links to one shared
`style.css` and one shared `nav.js`.

- **Live site:** https://salonten.com.au/
- **Master copy:** https://github.com/jeremy-andreani/salon-ten-site, on the `main` branch.
  Make every content change here. Do not maintain a second master copy or upload edits by hand.
- **Hosting:** Vodien. The workflow `.github/workflows/deploy-vodien.yml` publishes changes from
  `main` to the live site using an encrypted FTP connection. Once Jeremy completes the one-time
  connection setup, updates should normally appear within a couple of minutes of a push.
- **First activation:** follow [.github/VODIEN-SETUP.md](.github/VODIEN-SETUP.md). Publishing is
  not connected until the workflow has been pushed to GitHub, the three secrets have been added,
  and **Deploy to Vodien** has completed successfully. Do not call a change live before that.
- **Old preview:** https://jeremy-andreani.github.io/salon-ten-site/ is only the previous preview.
  Its settings have been left alone. Always give Kellie the `salonten.com.au` link and verify
  changes there. A successful GitHub Pages build does not mean Vodien has been updated.
- **Domain:** already hosted at Vodien. Content edits do not require any DNS or domain changes.

## Repo layout

- `index.html` - the home page (hero, treatments-by-category grid, about preview, testimonials,
  gift certificates banner, closing CTA).
- `treatments.html` - the "every treatment, in one place" overview page, listing every treatment
  by category with a link to its own page.
- One HTML file per treatment, e.g. `clinical-skin-peels.html`, `cosmeceutical-facials.html`,
  `microdermabrasion.html`, `massage.html`, `hair-removal.html`, `eyes.html`, `pedicures.html`,
  `tanning.html`, `ear-piercing.html`, `dermaplaning.html`, `aquaglow-hydra-facial.html`,
  `bbl-ipl-skin-rejuvenation.html`, `skin-tight-nano-facial.html`, `led-skin-treatments.html`,
  `packages.html`, `promotions.html`, `relaxing-facials.html`. Each is a single, mostly
  self-contained page (heading, intro, treatment card(s) with price, a Book Now band).
- `about.html`, `team.html`, `faq.html`, `policies.html`, `contact.html` - the structural pages
  (About, Our Team, FAQ, Salon Policies & Etiquette, Contact & map).
- `style.css` - the **one** shared stylesheet every page links to. Palette, type, buttons, header,
  hero, cards, footer - all of it lives here. Changing this file changes every page at once.
- `nav.js` - the small script that makes the mobile hamburger menu open/close. Shared by every
  page; do not duplicate its logic inline.
- `conversion.js` - fires the Google Ads conversion tag when a Book Now / Gift Vouchers link is
  clicked. Every page loads it. Leave it alone unless specifically asked to touch ad tracking.
- `img/` - every image used on the site, named after the treatment/page it belongs to (e.g.
  `img/clinical-skin-peels.jpg`, `img/kellie.jpg`, `img/logo.png`).
- `lp/template.html` - the shared template for Google Ads landing pages (placeholders like
  `{{TREATMENT_NAME}}`). It is not itself a live page.
- `relaxing-facials/`, `comprehensive-skin-assessment/`, `skin-microneedling/`,
  `specialised-facial-treatments/` - four real Google Ads landing pages, one folder each with its
  own `index.html` (so the ad's URL resolves with a trailing slash). Each is a single-CTA page
  with no site navigation, built from the `lp/template.html` pattern. See "What not to do" - these
  are deliberately different from the rest of the site.
- `.htaccess` - the active redirects from old WordPress addresses to the new pages. This file
  is published with the website. Keep the four ad landing-page addresses working as they are.
- `redirects.txt` - historical notes about the old addresses. It is not uploaded.
- `.github/scripts/build_site.py` - prepares the upload and checks local links. It includes public
  HTML, CSS, JavaScript and image files at the root, `img/`, and the four ad folders above. If a
  new public folder is needed, add it to `SITE_DIRECTORIES` and check the build first.
- `.github/workflows/deploy-vodien.yml` - the publishing workflow. It uploads only the prepared
  website files. `.github/`, `.claude/`, Markdown, screenshots, `lp/template.html`, and other
  working files stay out of the upload.

## Page template - copy this pattern exactly for any new or edited treatment page

Every structural/treatment page (everything except the four `lp/`-style landing pages) shares
this shell. Copy an existing page like `clinical-skin-peels.html` as your starting point rather
than typing this from scratch, but the pattern is:

**`<head>`:**
```html
<title>{Treatment Name} &ndash; Salon Ten</title>
<meta name="description" content="{One sentence, plain, matching what the page is about}.">
<link rel="stylesheet" href="style.css">
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-976595232"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){ dataLayer.push(arguments); }
  gtag('js', new Date());
  gtag('config', 'AW-976595232');
</script>
```
Keep the Google Ads tag block on every page, unchanged.

**Header/nav (identical on every page, only the current page's link styling differs - copy verbatim):**
```html
<header class="site-header">
  <div class="nav-inner">
    <a class="brand" href="index.html"><img src="img/logo.png" alt="Salon Ten" width="130" height="41"></a>
    <button class="nav-toggle" id="navToggle" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="navLinks">
      <span></span><span></span><span></span>
    </button>
    <ul class="nav-links" id="navLinks">
      <li><a href="index.html">Home</a></li>
      <li><a href="treatments.html">Treatments</a></li>
      <li><a href="about.html">About</a></li>
      <li><a href="team.html">Our Team</a></li>
      <li><a href="faq.html">FAQ</a></li>
      <li><a href="policies.html">Policies</a></li>
      <li><a href="contact.html">Contact</a></li>
    </ul>
    <div class="header-actions">
      <a class="phone" href="tel:+61249530626">(02) 4953 0626</a>
      <a class="btn btn-primary" href="https://apps.kitomba.com/bookings/salonten#services/all" target="_blank" rel="noopener">Book Now</a>
    </div>
  </div>
</header>
```

**Footer (identical on every page - copy verbatim):**
```html
<footer class="site-footer">
  <div class="wrap foot-grid">
    <div>
      <div class="foot-brand">Salon Ten</div>
      <p>A boutique skin, beauty and body salon in Mount Hutton, servicing Lake Macquarie and Newcastle since 2010.</p>
    </div>
    <div>
      <h4>EXPLORE</h4>
      <ul>
        <li><a href="about.html">About</a></li>
        <li><a href="team.html">Our Team</a></li>
        <li><a href="faq.html">FAQ</a></li>
        <li><a href="policies.html">Policies</a></li>
        <li><a href="contact.html">Contact &amp; map</a></li>
      </ul>
    </div>
    <div>
      <h4>CONTACT</h4>
      <ul>
        <li><a href="tel:+61249530626">(02) 4953 0626</a></li>
        <li><a href="mailto:info@salonten.com.au">info@salonten.com.au</a></li>
        <li>5/7 Wilsons Road, Mount Hutton, NSW 2290</li>
        <li><a href="https://www.facebook.com/salontenbodyandbeauty/" target="_blank" rel="noopener">Facebook</a></li>
      </ul>
    </div>
  </div>
  <div class="wrap foot-bottom">
    <span>Mon 9-5 &middot; Tue 9-5 &middot; Wed 9-2 &middot; Thu 9-5 &middot; Fri 9-5 &middot; Sat 9-2 &middot; Sun closed</span>
    <span><a class="btn btn-small" href="https://www.kitomba.com/bookings/salonten#voucher" target="_blank" rel="noopener">Gift Vouchers</a></span>
  </div>
</footer>
<script src="nav.js"></script>
<script src="conversion.js"></script>
```

**Booking link pattern:** every "Book Now" style button links to
`https://apps.kitomba.com/bookings/salonten#services/all` (Kitomba is the salon's booking system,
a separate third-party site). Gift voucher links go to
`https://www.kitomba.com/bookings/salonten#voucher`. Both always open in a new tab
(`target="_blank" rel="noopener"`). Never change these URLs or point them anywhere else.

**Page body pattern (see `clinical-skin-peels.html` for a full worked example):** a
`page-intro` section with a kicker label + `<h1>` + lede paragraph, then one `section.section`
containing one or more `article.treatment` blocks (image, heading with inline price, description
paragraph, optional sub-prices line), then a closing `cta-band` section with a Book Now button and
an "All Treatments" link back to `index.html`.

## House style (all lives in `style.css` - do not restate it inline on a page)

- Colours: navy ink `#0A1B36` (headings, header text), navy accent `#2E56A0` (buttons, links),
  gold `#C9A66B` (prices, gift-voucher accents), paper background `#F6F7FA`.
- Fonts: `Libre Baskerville` (serif) for every heading, `Montserrat` (sans) for body text, nav and
  buttons. Both load via the Google Fonts `@import` at the top of `style.css` - don't add a third
  font without asking.
- On the **home page's** treatments-by-category grid (`index.html`, `.treat-cats`/`.treat-list`),
  each treatment is a **name-only link** - no description text sits under the name there. If you
  add a new treatment to that grid, keep it to a name and a link; the description belongs on the
  treatment's own page, not the home page list.

## Content rules

- **Kellie's own wording is the source of truth.** If Kellie says a description is wrong or not
  how she'd put it, replace it with her wording, not a rewrite of the existing text. Never leave a
  paraphrase in place of what she actually said.
- **Prices follow the printed price list** (the physical trifold menu she hands out in-salon), not
  what's currently on the site, if the two disagree. If you're not sure which is current, ask
  rather than guess.
- **Never invent a claim, result, qualification or review.** Don't add "clinically proven",
  specific result percentages, staff qualifications, or testimonials that weren't actually given to
  you. If a description needs a fact you don't have, leave a note rather than making one up.
- **Keep BBL packages and Microdermabrasion on the site.** These two are deliberately kept even
  though they're not on the current printed price list - they were an intentional call, not an
  oversight. Don't remove them because they're "not on the price list."

## Pages currently carrying a placeholder image

These pages have a stock/placeholder photo (not a real photo of the treatment or salon), marked
in the HTML with a `<!-- PLACEHOLDER -->` comment right above the image and an "Placeholder image"
caption underneath it:

- `clinical-skin-peels.html`
- `facials.html`
- `aquaglow-hydra-facial.html`
- `tanning.html`
- `dermaplaning.html`
- `hair-removal.html`
- `ear-piercing.html`
- `cosmeceutical-facials.html`
- `eyes.html`
- `microdermabrasion.html`

**To swap a placeholder for a real photo:**
1. Drop the new image file into `img/` (reuse the existing filename referenced in that page's
   `src=` if you can, so you only need to change the file, not the HTML - otherwise update the
   `src=` to point at the new filename).
2. Remove the `<p class="img-caption">Placeholder image</p>` line.
3. Remove the `<!-- PLACEHOLDER -->` comment line.
4. Update the image's `alt="..."` text so it no longer says "(placeholder image)".

## Safe workflow for any change

1. Work in `jeremy-andreani/salon-ten-site` and read this file. Pull the latest `main` before
   editing. If there are existing local changes or a conflict, preserve them and resolve it;
   never force-push or discard someone else's work.
2. Make the change Kellie requested, using her wording. Check the page and its links locally.
3. Run `python3 .github/scripts/build_site.py /path/to/a/new/output-folder` to check the upload.
   Choose a new empty destination each time. Add new website files to git before running it.
4. Commit with a plain, specific message, then push to `main`. This publishes the change to the
   real website once the one-time connection is active.
5. Open https://github.com/jeremy-andreani/salon-ten-site/actions and check **Deploy to Vodien**
   for the latest change. Wait for a green tick. If it fails, read the failed step. Missing
   `VODIEN_FTP_SERVER`, `VODIEN_FTP_USERNAME` or `VODIEN_FTP_PASSWORD` means the one-time setup
   is incomplete. A queued run or first upload can take longer than a couple of minutes.
6. Open the changed page at https://salonten.com.au/ and refresh it. If it looks old after a
   successful upload, hard-refresh (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows), then check it
   on a phone too. Confirm the actual changed wording or image before reporting it live.
7. Tell Kellie what changed and give the live `salonten.com.au` page link. If publishing failed,
   say that clearly; a saved GitHub change alone does not mean the live website changed.

If a published edit needs undoing, revert that edit in git and push the reversal to `main`.
Do not try to fix it by editing a second copy in cPanel.

## What NOT to do

- **Do not delete any page.** If a page seems wrong or redundant, flag it rather than removing it.
- **Do not change `style.css` in a way that affects every page** (colours, fonts, header, footer,
  button styles) without asking first - one page's fix can quietly change the whole site.
- **Do not touch the four ad landing pages** (`relaxing-facials/`, `comprehensive-skin-assessment/`,
  `skin-microneedling/`, `specialised-facial-treatments/`) or `lp/template.html` unless
  specifically asked. They're deliberately built differently (no nav, single CTA) to match live
  Google Ads campaigns - a well-meaning "consistency" fix here would break running ads.
- **Do not add a `CNAME` file or change hosting/DNS.** The domain already runs on Vodien.
- **Do not change deployment credentials or safety settings as part of a content edit.** The FTP
  account is restricted to `public_html`, so `server-dir: ./` already means that directory.
  Never change it to `public_html/`, enable `dangerous-clean-slate`, or remove the exclusions for
  `old-wordpress/`, `cgi-bin/`, `.well-known/`, or `new-site-test/`.
- **Never put passwords in repository files or messages.** The publishing workflow reads the
  three repository secrets. Kel does not need the cPanel password to make ordinary edits.
