// Run with: node --test tools/salon-receptionist/test_send_booking_link.js
// Execute the real handler and shared helpers with an in-memory Twilio client. No network/SMS.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const FUNCTIONS = path.join(__dirname, 'functions');
const SERVICES = JSON.parse(fs.readFileSync(path.join(FUNCTIONS, 'service-links.generated.json'), 'utf8')).services;
const GENERIC_URL = 'kitomba.com/bookings/salonten';

function harness() {
  class Response {
    constructor() { this.headers = {}; }
    setStatusCode(status) { this.status = status; }
    appendHeader(key, value) { this.headers[key] = value; }
    setBody(body) { this.body = body; }
  }
  const shared = { module: { exports: {} }, require, Buffer, console, Twilio: { Response } };
  vm.runInNewContext(fs.readFileSync(path.join(FUNCTIONS, 'common.private.js'), 'utf8'), shared);
  const sandbox = {
    exports: {}, console,
    Runtime: { getAssets: () => ({
      '/common.js': { path: 'test-common' },
      '/service-links.json': { path: path.join(FUNCTIONS, 'service-links.generated.json') },
      '/kitomba-services.json': { path: path.join(FUNCTIONS, 'kitomba-services.generated.json') },
    }) },
    require: (name) => name === 'test-common' ? shared.module.exports : require(name),
  };
  vm.runInNewContext(fs.readFileSync(path.join(FUNCTIONS, 'send-booking-link.js'), 'utf8'), sandbox);

  const sent = [];
  const maps = new Map();
  const client = {
    messages: { create: async (message) => { sent.push(message); } },
    sync: { v1: { services: () => ({ syncMaps: (name) => {
      if (!maps.has(name)) maps.set(name, new Map());
      const items = maps.get(name);
      const syncMapItems = (key) => ({ fetch: async () => items.get(key) });
      syncMapItems.create = async (item) => {
        if (items.has(item.key)) throw { code: 54208 };
        items.set(item.key, item);
      };
      return { syncMapItems };
    } }) } },
  };
  const context = {
    SALON_WEBHOOK_SECRET: 'test-secret',
    SALON_FROM_NUMBER: '+61400000000',
    SYNC_SERVICE_SID: 'test-sync-service',
    getTwilioClient: () => client,
  };
  const invoke = (body, dryRun = false) => new Promise((resolve, reject) => {
    const event = {
      caller_number: '+61400000001', ...body,
      request: { headers: {
        'content-type': 'application/json',
        'x-salon-webhook-secret': context.SALON_WEBHOOK_SECRET,
        ...(dryRun ? { 'x-salon-dry-run': 'true' } : {}),
      } },
    };
    sandbox.exports.handler(context, event, (error, result) => error ? reject(error) : resolve(result)).catch(reject);
  });
  return { invoke, sent, maps };
}

test('two or more treatments send one general link with instructions to add every service', async () => {
  for (const service of [undefined, 'Brazilian and brow wax', 'skin needling and chemical peel', 'spray tan, ear piercing and LED facial']) {
    const h = harness();
    const result = await h.invoke({ multiple_services: true, ...(service ? { service } : {}) });
    assert.equal(result.status, 200);
    assert.equal(result.body.status, 'accepted');
    assert.equal(result.body.link_type, 'general');
    assert.equal(h.sent.length, 1);
    const message = h.sent[0].body;
    assert.equal(message.split(GENERIC_URL).length - 1, 1);
    assert.match(message, /You can add all your services there\./);
    assert.match(message, /Reply STOP to opt out$/);
    assert.doesNotMatch(message, /apps\.kitomba|services\[/);
    assert.ok(message.length <= 160);
    assert.match(message, /^[\x20-\x7e\n]+$/);
  }
});

test('single treatments retain every mapped link, including names with an ampersand', async () => {
  for (const entry of Object.values(SERVICES)) {
    const h = harness();
    const result = await h.invoke({ multiple_services: false, service: entry.label });
    assert.equal(result.body.link_type, 'treatment', entry.label);
    assert.equal(h.sent.length, 1);
    assert.equal(h.sent[0].body, `Hi, it's Salon Ten. Book your ${entry.label} online here: ${entry.url}\nReply STOP to opt out`);
  }
});

test('single-treatment aliases and older requests without the new flag retain their links', async () => {
  for (const [service, slug] of [
    ['skin needling', 'microneedling'], ['CIT', 'microneedling'],
    ['chemical peel', 'clinical-skin-peels'], ['hydrafacial', 'aquaglow-hydra-facial'],
    ['spray tan', 'tanning'], ['photofacial', 'bbl-ipl-skin-rejuvenation'],
  ]) {
    const h = harness();
    const result = await h.invoke({ service });
    assert.equal(result.body.link_type, 'treatment', service);
    assert.ok(h.sent[0].body.includes(SERVICES[slug].url), service);
  }
});

test('browsing and ambiguous or unmatched single treatments keep the generic fallback', async () => {
  for (const service of [undefined, 'IPL', 'facial', 'unknown service']) {
    const h = harness();
    const result = await h.invoke({ multiple_services: false, service });
    assert.equal(result.body.link_type, 'general');
    assert.equal(h.sent[0].body, `Hi, it's Salon Ten. Book online here: ${GENERIC_URL}\nReply STOP to opt out`);
  }
});

test('two confidently matched treatments send one link with both services pre-selected', async () => {
  const h = harness();
  const result = await h.invoke({ multiple_services: true, services: ['Skin Microneedling', 'Dermaplaning'] });
  assert.equal(result.body.status, 'accepted');
  assert.equal(result.body.link_type, 'treatments');
  assert.equal(h.sent.length, 1);
  const message = h.sent[0].body;
  const micro = SERVICES['microneedling'];
  const derma = SERVICES['dermaplaning'];
  const microId = micro.url.match(/services\[0\]\[0\]=(\d+)/)[1];
  const dermaId = derma.url.match(/services\[0\]\[0\]=(\d+)/)[1];
  assert.match(message, /Book your Skin Microneedling and Dermaplaning online here:/);
  assert.match(message, new RegExp(`services\\[0\\]\\[0\\]=${microId}&services\\[0\\]\\[1\\]=service&services\\[0\\]\\[2\\]=`));
  assert.match(message, new RegExp(`services\\[1\\]\\[0\\]=${dermaId}&services\\[1\\]\\[1\\]=service&services\\[1\\]\\[2\\]=`));
  assert.match(message, /They're already selected, just pick a time\./);
  assert.match(message, /Reply STOP to opt out$/);
});

test('three confidently matched treatments pre-select all three and join labels with a comma', async () => {
  const h = harness();
  const result = await h.invoke({ multiple_services: true, services: ['spray tan', 'ear piercing', 'skin needling'] });
  assert.equal(result.body.link_type, 'treatments');
  const message = h.sent[0].body;
  assert.match(message, /Book your Spray Tanning, Ear Piercing and Skin Microneedling online here:/);
  assert.equal(message.split('services[').length - 1, 9);
  assert.match(message, /services\[2\]\[0\]=/);
});

test('an unmapped treatment among the requested services falls back to the general link', async () => {
  const h = harness();
  const result = await h.invoke({ multiple_services: true, services: ['Skin Microneedling', 'something made up'] });
  assert.equal(result.body.link_type, 'general');
  assert.equal(h.sent[0].body, `Hi, it's Salon Ten. Book online here: ${GENERIC_URL}\nYou can add all your services there.\nReply STOP to opt out`);
  assert.doesNotMatch(h.sent[0].body, /apps\.kitomba|services\[/);
});

test('services with fewer than two entries or omitted falls back to the general link', async () => {
  for (const services of [undefined, [], ['Skin Microneedling']]) {
    const h = harness();
    const result = await h.invoke({ multiple_services: true, ...(services ? { services } : {}) });
    assert.equal(result.body.link_type, 'general');
  }
});

test('a malformed services field fails validation before reserving a cooldown or sending', async () => {
  for (const services of ['Skin Microneedling', [1, 2], null]) {
    const h = harness();
    const result = await h.invoke({ multiple_services: true, services });
    assert.equal(result.status, 400);
    assert.equal(h.maps.size, 0);
    assert.equal(h.sent.length, 0);
  }
});

test('a repeated multi-treatment request is blocked before a second SMS', async () => {
  const h = harness();
  await h.invoke({ multiple_services: true });
  const repeat = await h.invoke({ multiple_services: true });
  assert.equal(repeat.status, 429);
  assert.equal(h.sent.length, 1);
});

test('dry run previews the multi-treatment SMS without sending or using the live cooldown', async () => {
  const h = harness();
  const result = await h.invoke({ multiple_services: true, service: 'skin needling' }, true);
  assert.equal(result.body.status, 'dry_run');
  assert.equal(result.body.link_type, 'general');
  assert.match(result.body.sms_preview, /You can add all your services there\./);
  assert.equal(h.sent.length, 0);
  assert.equal(h.maps.has('booking-cooldown'), false);
  assert.equal(h.maps.get('booking-cooldown-dryrun').size, 1);
});

test('an invalid multiple_services flag fails before reserving a cooldown or sending', async () => {
  const h = harness();
  const result = await h.invoke({ multiple_services: 'false', service: 'skin needling' });
  assert.equal(result.status, 400);
  assert.equal(h.maps.size, 0);
  assert.equal(h.sent.length, 0);
});

// Kel's 28 Sep 2026 test call: Anne passed every treatment, but the website-only map had no
// brow, lash or waxing services, so the whole request fell back to the generic link.
const CATALOGUE = JSON.parse(fs.readFileSync(path.join(FUNCTIONS, 'kitomba-services.generated.json'), 'utf8')).services;
const byLabel = (label) => CATALOGUE.find((s) => s.label === label);
const KEL_URL = (ids) => `https://apps.kitomba.com/bookings/salonten#services/all?${ids.map((id, i) => `services[${i}][0]=${id}&services[${i}][1]=service&services[${i}][2]=`).join('&')}`;

test("Kel's lash tint + brow tint + brow wax + Brazilian sends ONE link with the combined brow service", async () => {
  const combo = byLabel('Brow Wax, Brow Tint, Lash Tint');
  const brazilian = byLabel('Brazilian Wax');
  assert.ok(combo && brazilian, 'catalogue carries the combined brow service and the Brazilian');
  for (const services of [
    ['lash tint', 'brow tint', 'brow wax', 'Brazilian'],
    ['Lash Tint', 'Brow Tint', 'Brow Shape', 'Brazilian'],
    // Exactly what Anne sent on both of Kel's calls.
    ['Lash Tint', 'Brow Tint', 'Brow Shape, Tint & Lash Tint', 'Brazilian'],
    ['Lash Tint', 'Brow Shape, Tint & Lash Tint', 'Brazilian'],
    ['brazillian wax', 'eyebrow wax and tint', 'lash tint'],
  ]) {
    const h = harness();
    const result = await h.invoke({ multiple_services: true, services });
    assert.equal(result.body.link_type, 'treatments', services.join(' | '));
    assert.equal(h.sent.length, 1);
    assert.equal(h.sent[0].body,
      `Hi, it's Salon Ten. Book your Brow Wax, Brow Tint, Lash Tint and Brazilian Wax online here: ${KEL_URL([combo.id, brazilian.id])}\nThey're already selected, just pick a time.\nReply STOP to opt out`,
      services.join(' | '));
  }
});

test('brow and lash pairs pick the matching two-item combined service', async () => {
  for (const [services, label] of [
    [['brow wax', 'brow tint'], 'Brow Wax & Brow Tint'],
    [['lash tint', 'brow tint'], 'Lash Tint & Brow Tint'],
    [['brow shape', 'lash tint'], 'Brow Wax & Lash Tint'],
  ]) {
    const h = harness();
    const result = await h.invoke({ multiple_services: true, services });
    assert.equal(result.body.link_type, 'treatment', services.join(' | '));
    assert.equal(h.sent[0].body, `Hi, it's Salon Ten. Book your ${label} online here: ${KEL_URL([byLabel(label).id])}\nReply STOP to opt out`);
  }
});

test('single catalogue treatments not on the website map now get their own link', async () => {
  for (const [service, label] of [['lash tint', 'Lash Tint'], ['Brazilian', 'Brazilian Wax'], ['brow wax and tint', 'Brow Wax & Brow Tint'], ['gel pedicure', 'Gel pedicure']]) {
    const h = harness();
    const result = await h.invoke({ multiple_services: false, service });
    assert.equal(result.body.link_type, 'treatment', service);
    assert.equal(h.sent[0].body, `Hi, it's Salon Ten. Book your ${label} online here: ${KEL_URL([byLabel(label).id])}\nReply STOP to opt out`);
  }
});

test('non-waxing lookalikes never map to a wax, and ambiguous names stay generic', async () => {
  const h = harness();
  const result = await h.invoke({ multiple_services: true, services: ['back massage', 'IPL bikini'] });
  assert.doesNotMatch(h.sent[0].body, /Back Wax|Bikini Wax/);
  assert.equal(result.body.link_type, 'treatments');
  for (const services of [['massage', 'brow wax'], ['full leg wax', 'lash tint'], ['lashes', 'Brazilian']]) {
    const g = harness();
    const r = await g.invoke({ multiple_services: true, services });
    assert.equal(r.body.link_type, 'general', services.join(' | '));
  }
});

test('an invented placeholder number is refused before any cooldown or SMS', async () => {
  for (const caller_number of ['+61412345678', '+61400000000', '+61411111111']) {
    const h = harness();
    const result = await h.invoke({ caller_number, multiple_services: true, services: ['lash tint', 'Brazilian'] });
    assert.equal(result.status, 400);
    assert.equal(h.maps.size, 0);
    assert.equal(h.sent.length, 0);
  }
});
