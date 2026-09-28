// POST /send-booking-link — texts the caller Salon Ten's Kitomba booking link, deep-linked to a
// specific treatment when the caller's requested service confidently matches the site's
// generated service-to-link map (see refresh_kb.py service_links). Two or more treatments that
// all confidently match send one SMS with every service pre-selected in the Kitomba link. If any
// requested treatment can't be matched, or the caller is just browsing, that falls back to the
// generic booking page. Only the fixed generic URL or URLs built from that generated map are ever
// sent, never model text. Replaces the engine endpoint in
// src/Gateway.Api/EndpointMapper.SalonReceptionist.cs.
const fs = require('fs');
const common = require(Runtime.getAssets()['/common.js'].path);

// Twilio's Messaging Policy requires an opt-out instruction in the initial message.
const GENERIC_URL_TEXT = 'kitomba.com/bookings/salonten';
const BOOKING_TEXT = `Hi, it's Salon Ten. Book online here: ${GENERIC_URL_TEXT}\nReply STOP to opt out`;
const MULTIPLE_BOOKING_TEXT = `Hi, it's Salon Ten. Book online here: ${GENERIC_URL_TEXT}\nYou can add all your services there.\nReply STOP to opt out`;
const COOLDOWN_SECONDS = 600;

function loadServiceLinks() {
  try {
    const asset = Runtime.getAssets()['/service-links.json'];
    const parsed = JSON.parse(fs.readFileSync(asset.path, 'utf8'));
    return (parsed && typeof parsed.services === 'object' && parsed.services) || {};
  } catch (err) {
    // Missing or malformed map: every caller safely falls back to the generic link below.
    return {};
  }
}

const SERVICE_LINKS = loadServiceLinks();

// Salon Ten's full public Kitomba catalogue (refresh_catalogue.py): every bookable service id and
// label, including combined services such as "Brow Wax, Brow Tint, Lash Tint".
function loadCatalogue() {
  try {
    const asset = Runtime.getAssets()['/kitomba-services.json'];
    const parsed = JSON.parse(fs.readFileSync(asset.path, 'utf8'));
    const services = Array.isArray(parsed && parsed.services)
      ? parsed.services.filter((s) => s && /^\d+$/.test(String(s.id)) && typeof s.label === 'string')
      : [];
    return { base: BOOKING_BASE, services };
  } catch (err) {
    // Missing or malformed catalogue: only the website map above is used.
    return { base: BOOKING_BASE, services: [] };
  }
}

const BOOKING_BASE = 'https://apps.kitomba.com/bookings/salonten';
const CATALOGUE = loadCatalogue();

function normalize(text) {
  return String(text).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

// Words of 3+ characters only, so a stray "to"/"an" can't force or block a match.
function words(text) {
  return normalize(text).split(' ').filter((w) => w.length >= 3);
}

// Common caller phrasings that word-overlap matching alone would miss or misfire on (e.g. "CIT"
// shares no substring with "microneedling"; "dermaplane" isn't a substring of "dermaplaning").
// Keep in sync with the TREATMENT ALIASES section of agent-prompt.md. Maps to a service-links
// slug; only the caller-facing label/URL already in SERVICE_LINKS is ever sent.
const ALIASES = {
  'skin needling': 'microneedling',
  needling: 'microneedling',
  'collagen induction therapy': 'microneedling',
  cit: 'microneedling',
  microneedling: 'microneedling',
  'chemical peel': 'clinical-skin-peels',
  'skin peel': 'clinical-skin-peels',
  peel: 'clinical-skin-peels',
  'medi peel': 'clinical-skin-peels',
  hydrafacial: 'aquaglow-hydra-facial',
  'hydra facial': 'aquaglow-hydra-facial',
  'laser hair removal': 'ipl-hair-removal',
  photofacial: 'bbl-ipl-skin-rejuvenation',
  'photo facial': 'bbl-ipl-skin-rejuvenation',
  bbl: 'bbl-ipl-skin-rejuvenation',
  'spray tan': 'tanning',
  tan: 'tanning',
  tanning: 'tanning',
  dermaplane: 'dermaplaning',
  piercing: 'ear-piercing',
  'ear piercing': 'ear-piercing',
  'led facial': 'led-skin-treatments',
  'led treatment': 'led-skin-treatments',
  'led light therapy': 'led-skin-treatments',
  'medi facial': 'cosmeceutical-facials',
  'hyperformance facial': 'cosmeceutical-facials',
  'nano infusion': 'skin-tight-nano-facial',
  'nano facial': 'skin-tight-nano-facial',
};

// Word-boundary substring match (padded with spaces) so "tan" can't fire inside an unrelated
// longer word. When several alias phrases match, the longest (most specific) one wins.
function aliasMatch(requested) {
  const text = ` ${normalize(requested || '')} `;
  let best = null;
  for (const [phrase, slug] of Object.entries(ALIASES)) {
    if (text.includes(` ${phrase} `) && (!best || phrase.length > best.phrase.length)) best = { phrase, slug };
  }
  return best ? SERVICE_LINKS[best.slug] || null : null;
}

// Matches only against the pre-approved map (slug + label); the caller's free text never
// reaches a URL directly, only selects which pre-approved URL is confident enough to send.
// Every significant word of the caller's phrase must appear in (or be contained by) the
// treatment's label/slug, so word order and minor phrasing ("skin needling" for "Skin
// Microneedling") don't block a match, while a vague single word that fits several
// treatments ("facial", "skin") stays ambiguous and falls back to the generic link.
function wordOverlapMatch(requested) {
  const queryWords = words(requested || '');
  if (!queryWords.length) return null;
  const matches = Object.entries(SERVICE_LINKS).filter(([slug, entry]) => {
    const haystack = [...words(entry.label), ...words(slug)];
    return queryWords.every((w) => haystack.some((h) => h.includes(w) || w.includes(h)));
  });
  return matches.length === 1 ? matches[0][1] : null;
}

function matchService(requested) {
  return aliasMatch(requested) || wordOverlapMatch(requested);
}

// Every generated link encodes its own service as index 0; pull the raw Kitomba service id back
// out so several can be re-indexed together into one link.
function serviceIdFromUrl(url) {
  const match = /services\[0\]\[0\]=(\d+)/.exec(url || '');
  return match ? match[1] : null;
}

function bookingUrl(ids) {
  const params = ids.map((id, i) => `services[${i}][0]=${id}&services[${i}][1]=service&services[${i}][2]=`).join('&');
  return `${CATALOGUE.base}#services/all?${params}`;
}

// --- Brows, lashes and waxing: combined-service matching against the full catalogue ---------
// Each request (and each catalogue label) is parsed into "atoms" such as brow_wax, brow_tint,
// lash_tint, brazilian or lip. The union of every requested atom is then covered by catalogue
// services, largest first, so "lash tint" + "brow tint" + "brow wax" becomes the one combined
// "Brow Wax, Brow Tint, Lash Tint" service rather than three separate ones.
const WAX_AREAS = [
  ['brazillian', 'brazilian'], ['brazilian', 'brazilian'], ['g string', 'g_string'], ['bikini', 'bikini'],
  ['underarms', 'underarm'], ['underarm', 'underarm'], ['armpits', 'underarm'], ['armpit', 'underarm'],
  ['lip', 'lip'], ['chin', 'chin'], ['sides of face', 'face_sides'], ['side of face', 'face_sides'],
  ['full face', 'full_face'], ['back', 'back'], ['chest', 'chest'],
  ['full arms', 'full_arms'], ['full arm', 'full_arms'], ['half arms', 'half_arms'], ['half arm', 'half_arms'],
  ['full legs', 'full_leg'], ['full leg', 'full_leg'], ['half legs', 'half_leg'], ['half leg', 'half_leg'],
  ['three quarter legs', 'three_quarter_leg'], ['three quarter leg', 'three_quarter_leg'],
  ['top legs', 'top_leg'], ['top leg', 'top_leg'], ['upper legs', 'top_leg'], ['upper leg', 'top_leg'],
];
// Words that put a request outside the brow/lash/waxing family (a back massage is not a back
// wax, IPL bikini is not a bikini wax); those go through name matching instead.
const NOT_WAXING = /\b(massages?|facials?|ipl|laser|electrolysis|peels?|needling|microneedling|tan|tanning|pedicures?|manicures?|dermaplan\w*|lift\w*|perm\w*|piercing|hydra\w*|led|bbr|bbl|reiki|assessment|consult\w*|mens?|trim)\b/;
const FILLER = new Set(['a', 'an', 'the', 'please', 'also', 'some', 'my', 'get', 'like', 'want', 'would', 'just', 'treatment', 'service', 'appointment', 'booking', 'includes', 'include', 'including', 'only', 'if', 'needed', 'nose', 'tidy', 'too', 'as', 'well', 'one', 'both', 'normal', 'regular', 'standard']);

function segments(text) {
  return String(text).toLowerCase()
    .replace(/\b3\s*\/\s*4\b/g, ' three quarter ').replace(/\bno (eye)?brows?\b/g, ' ')
    .replace(/[,&+\/;()]/g, ' , ')
    .split(/\s*,\s*|\s+(?:and|plus|with)\s+/)
    .map(normalize).filter(Boolean);
}

// Returns the atom set, or null when any part of the text isn't understood (so it is never
// treated as covered by a waxing/tinting service it may not mean).
function atoms(text) {
  if (NOT_WAXING.test(normalize(text))) return null;
  const segs = segments(text).map((seg) => {
    const padded = ` ${seg} `;
    const part = /\b(eye)?brows?\b/.test(seg) ? 'brow' : /\b(eye)?lash(es)?\b/.test(seg) ? 'lash' : null;
    const action = /\btint(s|ing|ed)?\b/.test(seg) ? 'tint' : /\b(wax(es|ing|ed)?|shap(e|es|ed|ing))\b/.test(seg) ? 'wax' : null;
    const areas = [];
    let rest = padded;
    for (const [phrase, atom] of WAX_AREAS) {
      if (rest.includes(` ${phrase} `)) { areas.push(atom); rest = rest.replace(` ${phrase} `, ' '); }
    }
    const filler = seg.split(' ').every((w) => FILLER.has(w) || /^(wax|waxes|waxing|waxed|tint|tints|tinting|tinted|shape|shapes|shaped|shaping)$/.test(w));
    return { part, action, areas, filler };
  });
  const out = new Set();
  for (let i = 0; i < segs.length; i++) {
    const seg = segs[i];
    let { part, action } = seg;
    if (part && !action) {
      const next = segs.slice(i + 1).find((s) => s.action && s.part);
      const prev = segs.slice(0, i).reverse().find((s) => s.action && s.part);
      action = (next || prev || {}).action || (part === 'brow' ? 'wax' : null); // bare "brows" = a brow wax
      if (!action) return null;
    }
    if (!part && action && !seg.areas.length) {
      const prev = segs.slice(0, i).reverse().find((s) => s.part);
      const next = segs.slice(i + 1).find((s) => s.part);
      part = (prev || next || {}).part || null; // "brow wax and tint" = a brow tint too
      if (!part && action === 'tint') return null; // a bare "waxing" is just filler
    }
    if (part) {
      if (part === 'lash' && action !== 'tint') return null;
      out.add(`${part}_${action}`);
    }
    seg.areas.forEach((a) => out.add(a));
    if (!part && !seg.areas.length && !seg.filler) return null;
  }
  return out.size ? out : null;
}

const ATOM_SERVICES = CATALOGUE.services
  .map((s) => ({ entry: s, atoms: atoms(s.label) }))
  .filter((s) => s.atoms);

// Greedy cover: the service that satisfies the most still-wanted atoms (and nothing unwanted)
// first. Returns null if anything wanted can't be covered.
function coverAtoms(wanted) {
  const remaining = new Set(wanted);
  const chosen = [];
  while (remaining.size) {
    const fits = ATOM_SERVICES
      .filter((s) => [...s.atoms].every((a) => remaining.has(a)))
      .sort((a, b) => b.atoms.size - a.atoms.size || a.entry.label.length - b.entry.label.length);
    if (!fits.length) return null;
    chosen.push(fits[0].entry);
    fits[0].atoms.forEach((a) => remaining.delete(a));
  }
  return chosen;
}

// Anything else: the website map (aliases, then word overlap), then a unique word-overlap match
// against the full catalogue ("organic spa facial", "gel pedicure"). Ambiguous stays unmatched.
function catalogueOverlap(requested) {
  const queryWords = words(requested || '');
  if (!queryWords.length) return null;
  const exact = CATALOGUE.services.filter((s) => normalize(s.label) === normalize(requested));
  if (exact.length === 1) return exact[0];
  const matches = CATALOGUE.services.filter((s) => {
    const haystack = words(s.label);
    return queryWords.every((w) => haystack.some((h) => h.includes(w) || w.includes(h)));
  });
  return matches.length === 1 ? matches[0] : null;
}

function nameMatch(requested) {
  const site = matchService(requested);
  if (site) {
    const id = serviceIdFromUrl(site.url);
    return id ? { id, label: site.label } : null;
  }
  const entry = catalogueOverlap(requested);
  return entry ? { id: String(entry.id), label: entry.label } : null;
}

// Resolves every requested treatment to pre-approved Kitomba service ids (with labels), merging
// brow/lash/waxing items into combined services where one exists. Null if any can't be matched.
function resolveServices(requested) {
  const named = [];
  const wanted = new Set();
  let atomSlot = -1;
  for (const text of requested) {
    const set = atoms(text);
    if (set) {
      set.forEach((a) => wanted.add(a));
      if (atomSlot < 0) atomSlot = named.length;
      continue;
    }
    const match = nameMatch(text);
    if (!match) return null;
    named.push(match);
  }
  let combined = [];
  if (wanted.size) {
    const cover = coverAtoms(wanted);
    if (!cover) return null;
    combined = cover.map((e) => ({ id: String(e.id), label: e.label }));
  }
  const all = atomSlot < 0 ? named : [...named.slice(0, atomSlot), ...combined, ...named.slice(atomSlot)];
  const seen = new Set();
  return all.filter((m) => !seen.has(m.id) && seen.add(m.id));
}

function joinLabels(labels) {
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`;
}

exports.handler = async function (context, event, callback) {
  const { reply } = common;
  const authError = common.authenticate(context, event);
  if (authError) return reply(callback, authError.status, { error: authError.error });
  const { body, error } = common.readBody(event);
  if (error) return reply(callback, error.status, { error: error.error });

  const number = common.trimmed(body.caller_number);
  if (!common.isAuMobileOrLocal(number))
    return reply(callback, 400, { error: 'caller_number must be an Australian E.164 number: +61 followed by nine digits, without the domestic leading zero.' });
  // Anne has called this with an invented example number before the caller gave theirs; never
  // text a placeholder.
  if (/^\+614(?:12345678|(\d)\1{7})$/.test(number))
    return reply(callback, 400, { error: 'caller_number looks like a placeholder. Ask the caller for their real mobile number and call again once they have said it.' });
  if (body.multiple_services !== undefined && typeof body.multiple_services !== 'boolean')
    return reply(callback, 400, { error: 'multiple_services must be true or false.' });
  if (body.services !== undefined && !(Array.isArray(body.services) && body.services.every((s) => typeof s === 'string')))
    return reply(callback, 400, { error: 'services must be an array of treatment name strings.' });
  if (!common.isE164(context.SALON_FROM_NUMBER) || !context.SYNC_SERVICE_SID)
    return reply(callback, 503, { error: 'SALON_FROM_NUMBER or SYNC_SERVICE_SID is not configured on the Twilio Functions environment.' });

  const dryRun = common.isDryRun(event);
  const client = context.getTwilioClient();
  const map = client.sync.v1.services(context.SYNC_SERVICE_SID).syncMaps(dryRun ? 'booking-cooldown-dryrun' : 'booking-cooldown');
  const key = number.slice(1);

  // Reserve the cooldown before sending. Sync create is atomic, so concurrent calls for the
  // same number cannot both send. The reservation is kept on failure: Twilio may have accepted
  // a request whose response we did not receive. Never auto-retry.
  const now = Date.now();
  const expiresAt = new Date(now + COOLDOWN_SECONDS * 1000).toISOString();
  try {
    await map.syncMapItems.create({ key, data: { expires_at: expiresAt }, itemTtl: COOLDOWN_SECONDS });
  } catch (err) {
    if (!err || err.code !== 54208) {
      console.warn('Salon booking cooldown store is unavailable; no SMS was sent.');
      return reply(callback, 503, { error: 'The booking SMS could not be sent right now. Read out the booking link instead.' });
    }
    // An item exists. Sync TTL removal can lag, so honour the stored expiry, and take over a
    // stale item only with a revision-checked update.
    let item;
    try { item = await map.syncMapItems(key).fetch(); } catch (e) { item = null; }
    const until = item && item.data && Date.parse(item.data.expires_at);
    if (!item || (until && until > now)) {
      const seconds = until ? Math.max(1, Math.ceil((until - now) / 1000)) : COOLDOWN_SECONDS;
      return reply(callback, 429, { error: 'A booking SMS was already attempted for this number. Wait before trying again.', retry_after_seconds: seconds }, { 'Retry-After': String(seconds) });
    }
    try {
      await map.syncMapItems(key).update({ data: { expires_at: expiresAt }, itemTtl: COOLDOWN_SECONDS, ifMatch: item.revision });
    } catch (e) {
      return reply(callback, 429, { error: 'A booking SMS was already attempted for this number. Wait before trying again.', retry_after_seconds: COOLDOWN_SECONDS }, { 'Retry-After': String(COOLDOWN_SECONDS) });
    }
  }

  // The agent counts treatments before mapping them. Never let an alias for one treatment
  // override a request for several, even if a service was accidentally supplied as well.
  const multipleServices = body.multiple_services === true;
  const requestedServices = multipleServices && Array.isArray(body.services) ? body.services : null;
  let chosen = requestedServices && requestedServices.length >= 2 ? resolveServices(requestedServices) : null;
  let single = null;
  if (!multipleServices && body.service !== undefined) {
    const site = matchService(body.service);
    if (site) single = site;
    else {
      // e.g. "lash tint", or "brow wax and tint" -> the combined Brow Wax & Brow Tint service.
      const resolved = resolveServices([body.service]);
      if (resolved && resolved.length === 1) single = { label: resolved[0].label, url: bookingUrl([resolved[0].id]) };
      else if (resolved && resolved.length > 1) chosen = resolved;
    }
  }
  const multiUrl = chosen && chosen.length ? bookingUrl(chosen.map((m) => m.id)) : null;
  const linkType = multiUrl ? (chosen.length > 1 ? 'treatments' : 'treatment') : single ? 'treatment' : 'general';
  const smsText = multiUrl && chosen.length > 1
    ? `Hi, it's Salon Ten. Book your ${joinLabels(chosen.map((m) => m.label))} online here: ${multiUrl}\nThey're already selected, just pick a time.\nReply STOP to opt out`
    : multiUrl
    ? `Hi, it's Salon Ten. Book your ${chosen[0].label} online here: ${multiUrl}\nReply STOP to opt out`
    : single
    ? `Hi, it's Salon Ten. Book your ${single.label} online here: ${single.url}\nReply STOP to opt out`
    : multipleServices ? MULTIPLE_BOOKING_TEXT : BOOKING_TEXT;

  if (dryRun)
    return reply(callback, 200, { status: 'dry_run', message: 'Validated and cooldown reserved in the dry-run map. No SMS was sent.', sms_preview: smsText, link_type: linkType });

  const outcome = await common.sendSms(client, context.SALON_FROM_NUMBER, number, smsText);
  return outcome === 'accepted'
    ? reply(callback, 200, { status: 'accepted', message: 'The booking SMS was accepted by Twilio for delivery.', link_type: linkType })
    : reply(callback, 502, { error: 'Twilio did not confirm the booking SMS. Delivery is unconfirmed; do not retry for ten minutes.' });
};
