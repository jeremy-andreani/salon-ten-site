// Shared helpers for Anne's two Twilio Functions. Private asset: not reachable over HTTP.
const crypto = require('crypto');

const MAX_BODY_BYTES = 8192;

function reply(callback, status, body, headers = {}) {
  const response = new Twilio.Response();
  response.setStatusCode(status);
  response.appendHeader('Content-Type', 'application/json');
  for (const [k, v] of Object.entries(headers)) response.appendHeader(k, v);
  response.setBody(body);
  return callback(null, response);
}

// Constant-time comparison of the shared secret header against SALON_WEBHOOK_SECRET.
function authenticate(context, event) {
  const expected = context.SALON_WEBHOOK_SECRET || '';
  if (!expected) return { status: 503, error: 'SALON_WEBHOOK_SECRET is not configured on the Twilio Functions environment.' };
  const headers = (event.request && event.request.headers) || {};
  const supplied = headers['x-salon-webhook-secret'];
  const hash = (s) => crypto.createHash('sha256').update(String(s), 'utf8').digest();
  if (typeof supplied !== 'string' || !supplied || !crypto.timingSafeEqual(hash(expected), hash(supplied)))
    return { status: 401, error: 'Missing or invalid X-Salon-Webhook-Secret header.' };
  return null;
}

// Twilio parses the JSON body into event; recover the caller fields and bound their size.
function readBody(event) {
  const headers = (event.request && event.request.headers) || {};
  const type = String(headers['content-type'] || '');
  if (!/^application\/([a-z0-9.+-]*\+)?json\b/i.test(type)) return { error: { status: 415, error: 'Content-Type must be application/json.' } };
  const length = Number(headers['content-length'] || 0);
  const body = {};
  for (const [k, v] of Object.entries(event)) if (k !== 'request') body[k] = v;
  if (length > MAX_BODY_BYTES || Buffer.byteLength(JSON.stringify(body), 'utf8') > MAX_BODY_BYTES)
    return { error: { status: 413, error: `Request body must not exceed ${MAX_BODY_BYTES} bytes.` } };
  return { body };
}

// Dry run: header only, so ElevenLabs can never trigger it. Validates and exercises Sync
// under separate names, but sends no SMS and never touches the live records.
function isDryRun(event) {
  const headers = (event.request && event.request.headers) || {};
  return String(headers['x-salon-dry-run'] || '').toLowerCase() === 'true';
}

const isE164 = (v) => typeof v === 'string' && /^\+[1-9][0-9]{6,14}$/.test(v);
const isAuMobileOrLocal = (v) => typeof v === 'string' && /^\+61[1-9][0-9]{8}$/.test(v);
const trimmed = (v) => (typeof v === 'string' ? v.trim() : v === undefined || v === null ? undefined : String(v).trim());

// Returns 'accepted' | 'rejected' | 'unconfirmed'. Never logs bodies, numbers or provider errors.
async function sendSms(client, from, to, body) {
  try {
    await client.messages.create({ from, to, body });
    return 'accepted';
  } catch (err) {
    if (err && typeof err.status === 'number') {
      console.warn(`Salon SMS rejected by Twilio (HTTP ${err.status}).`);
      return 'rejected';
    }
    console.warn('Salon SMS delivery is unconfirmed after a transport failure; no retry was attempted.');
    return 'unconfirmed';
  }
}

module.exports = { reply, authenticate, readBody, isDryRun, isE164, isAuMobileOrLocal, trimmed, sendSms };
