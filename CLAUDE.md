# Salon Ten website — working notes for Claude Code

This file is read automatically by Claude Code at the start of a session in this repo. It's here
so you (Kellie's Claude) know how the site is built and what conventions to follow before making
any change.

## What this is

A plain static HTML/CSS website for Salon Ten (Mount Hutton, NSW) — no build tools, no framework,
no server-side code. Every page is a hand-written `.html` file that links to one shared
`style.css` and one shared `nav.js`.

- **Live site:** https://jeremy-andreani.github.io/salon-ten-site/
- **Hosting:** GitHub Pages, served straight from this repo's `main` branch. There is no separate
  build or deploy step — GitHub republishes automatically about a minute after anything is pushed
  to `main`.
- **Domain:** the live URL above is a `github.io` address, not `salonten.com.au` yet. Pointing the
  real domain at this site is a later, separate step that belongs to Jeremy — see "What not to do"
  below.

## Repo layout

- `index.html` — the home page (hero, treatments-by-category grid, about preview, testimonials,
  gift certificates banner, closing CTA).
- `treatments.html` — the "every treatment, in one place" overview page, listing every treatment
  by category with a link to its own page.
- One HTML file per treatment, e.g. `clinical-skin-peels.html`, `cosmeceutical-facials.html`,
  `microdermabrasion.html`, `massage.html`, `hair-removal.html`, `eyes.html`, `pedicures.html`,
  `tanning.html`, `ear-piercing.html`, `dermaplaning.html`, `aquaglow-hydra-facial.html`,
  `bbl-ipl-skin-rejuvenation.html`, `skin-tight-nano-facial.html`, `led-skin-treatments.html`,
  `packages.html`, `promotions.html`, `relaxing-facials.html`. Each is a single, mostly
  self-contained page (heading, intro, treatment card(s) with price, a Book Now band).
- `about.html`, `team.html`, `faq.html`, `policies.html`, `contact.html` — the structural pages
  (About, Our Team, FAQ, Salon Policies & Etiquette, Contact & map).
- `style.css` — the **one** shared stylesheet every page links to. Palette, type, buttons, header,
  hero, cards, footer — all of it lives here. Changing this file changes every page at once.
- `nav.js` — the small script that makes the mobile hamburger menu open/close. Shared by every
  page; do not duplicate its logic inline.
- `conversion.js` — fires the Google Ads conversion tag when a Book Now / Gift Vouchers link is
  clicked. Every page loads it. Leave it alone unless specifically asked to touch ad tracking.
- `img/` — every image used on the site, named after the treatment/page it belongs to (e.g.
  `img/clinical-skin-peels.jpg`, `img/kellie.jpg`, `img/logo.png`).
- `lp/template.html` — the shared template for Google Ads landing pages (placeholders like
  `{{TREATMENT_NAME}}`). It is not itself a live page.
- `relaxing-facials/`, `comprehensive-skin-assessment/`, `skin-microneedling/`,
  `specialised-facial-treatments/` — four real Google Ads landing pages, one folder each with its
  own `index.html` (so the ad's URL resolves with a trailing slash). Each is a single-CTA page
  with no site navigation, built from the `lp/template.html` pattern. See "What not to do" — these
  are deliberately different from the rest of the site.
- `redirects.txt` — old-site to new-site URL mappings, used only at domain cut-over. Not something
  a content change ever needs to touch.

## Page template — copy this pattern exactly for any new or edited treatment page

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

**Header/nav (identical on every page, only the current page's link styling differs — copy verbatim):**
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

**Footer (identical on every page — copy verbatim):**
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

## House style (all lives in `style.css` — do not restate it inline on a page)

- Colours: navy ink `#0A1B36` (headings, header text), navy accent `#2E56A0` (buttons, links),
  gold `#C9A66B` (prices, gift-voucher accents), paper background `#F6F7FA`.
- Fonts: `Libre Baskerville` (serif) for every heading, `Montserrat` (sans) for body text, nav and
  buttons. Both load via the Google Fonts `@import` at the top of `style.css` — don't add a third
  font without asking.
- On the **home page's** treatments-by-category grid (`index.html`, `.treat-cats`/`.treat-list`),
  each treatment is a **name-only link** — no description text sits under the name there. If you
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
  though they're not on the current printed price list — they were an intentional call, not an
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
- `relaxing-facials.html`
- `ear-piercing.html`
- `cosmeceutical-facials.html`
- `eyes.html`
- `microdermabrasion.html`

**To swap a placeholder for a real photo:**
1. Drop the new image file into `img/` (reuse the existing filename referenced in that page's
   `src=` if you can, so you only need to change the file, not the HTML — otherwise update the
   `src=` to point at the new filename).
2. Remove the `<p class="img-caption">Placeholder image</p>` line.
3. Remove the `<!-- PLACEHOLDER -->` comment line.
4. Update the image's `alt="..."` text so it no longer says "(placeholder image)".

## Safe workflow for any change

1. `git pull` before you start, so you're not editing an out-of-date copy.
2. Make the change.
3. Commit in small, separate commits with plain, specific messages (e.g. "Update dermaplaning
   price to $95", not "changes" or "updates"). One logical change per commit.
4. `git push` to `main`.
5. Wait about a minute, then hard-refresh the live page
   (https://jeremy-andreani.github.io/salon-ten-site/...) — a normal refresh can show a cached
   copy of the old page.
6. Check the changed page on a phone too, not just a laptop — the site is mobile-first and some
   layout issues (menu wrapping, image cropping) only show up at a phone width.

## What NOT to do

- **Do not delete any page.** If a page seems wrong or redundant, flag it rather than removing it.
- **Do not change `style.css` in a way that affects every page** (colours, fonts, header, footer,
  button styles) without asking first — one page's fix can quietly change the whole site.
- **Do not touch the four ad landing pages** (`relaxing-facials/`, `comprehensive-skin-assessment/`,
  `skin-microneedling/`, `specialised-facial-treatments/`) or `lp/template.html` unless
  specifically asked. They're deliberately built differently (no nav, single CTA) to match live
  Google Ads campaigns — a well-meaning "consistency" fix here would break running ads.
- **Do not add a `CNAME` file.** That's what points the real `salonten.com.au` domain at this
  site, and doing the domain cut-over is Jeremy's own step, done separately and deliberately, not
  something to trigger from a content edit.
