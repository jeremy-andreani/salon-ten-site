// POST /take-message — records a callback message in Twilio Sync, then texts the salon owner.
// Replaces the engine endpoint in src/Gateway.Api/EndpointMapper.SalonReceptionist.cs.
const crypto = require('crypto');
const common = require(Runtime.getAssets()['/common.js'].path);

exports.handler = async function (context, event, callback) {
  const { reply } = common;
  const authError = common.authenticate(context, event);
  if (authError) return reply(callback, authError.status, { error: authError.error });
  const { body, error } = common.readBody(event);
  if (error) return reply(callback, error.status, { error: error.error });

  const name = common.trimmed(body.name);
  const number = common.trimmed(body.number);
  const reason = common.trimmed(body.reason);
  const preferredTime = common.trimmed(body.preferred_time) || undefined;
  if (!name || name.length > 120 || !common.isE164(number) || !reason || reason.length > 1000 ||
      (preferredTime && preferredTime.length > 200))
    return reply(callback, 400, { error: 'name (1-120 characters), number (E.164) and reason (1-1000 characters) are required. preferred_time is optional (up to 200 characters).' });

  const owners = (context.SALON_OWNER_NOTIFY_NUMBER || '')
    .split(',').map((s) => s.trim()).filter(Boolean);
  if (owners.length && (!owners.every(common.isE164) || !common.isE164(context.SALON_FROM_NUMBER)))
    return reply(callback, 503, { error: 'SALON_OWNER_NOTIFY_NUMBER must be a comma-separated list of E.164 numbers, and SALON_FROM_NUMBER must be an E.164 number, or leave the owner number unset to disable owner SMS.' });
  if (!context.SYNC_SERVICE_SID)
    return reply(callback, 503, { error: 'SYNC_SERVICE_SID is not configured on the Twilio Functions environment.' });

  const dryRun = common.isDryRun(event);
  const client = context.getTwilioClient();
  const id = crypto.randomUUID().replace(/-/g, '');
  const timestamp = new Date().toISOString();
  const entry = { id, timestamp, name, number, reason, preferred_time: preferredTime || null };

  // The record is saved before any owner SMS; storage failure sends nothing.
  try {
    await client.sync.v1.services(context.SYNC_SERVICE_SID)
      .syncLists(dryRun ? 'callback-messages-dryrun' : 'callback-messages')
      .syncListItems.create({ data: entry });
  } catch (err) {
    console.warn('Salon callback storage is unavailable; no owner SMS was sent.');
    return reply(callback, 503, { error: 'The callback message could not be saved. Please try again later.' });
  }

  const sms = `Salon Ten callback: ${name}, ${number}. Reason: ${reason}. Preferred time: ${preferredTime || 'any time'}.`;
  if (!owners.length) {
    console.log(`Salon callback ${id} saved; owner SMS is disabled.`);
    return reply(callback, 200, { status: dryRun ? 'dry_run' : 'saved', id, timestamp, owner_notification: 'disabled' });
  }
  if (dryRun)
    return reply(callback, 200, { status: 'dry_run', id, timestamp, owner_notification: 'skipped_dry_run', owner_count: owners.length, sms_preview: sms });

  // Each recipient gets its own send attempt; one recipient's failure never blocks or retries another's.
  const results = await Promise.all(owners.map((to) => common.sendSms(client, context.SALON_FROM_NUMBER, to, sms)));
  const accepted = results.filter((r) => r === 'accepted').length;
  const overall = accepted === results.length ? 'accepted' : accepted > 0 ? 'partial' : 'failed';
  // The callback is durably saved even if notification fails. Returning success for that
  // completed work prevents an agent retry from saving/sending the same message again.
  console.log(`Salon callback ${id} saved; owner SMS results: ${accepted}/${results.length} accepted.`);
  return reply(callback, 200, {
    status: 'saved', id, timestamp,
    owner_notification: overall,
    ...(overall === 'accepted' ? {} : { warning: 'The message is saved, but not every owner SMS was confirmed. Do not submit the message again.' })
  });
};
