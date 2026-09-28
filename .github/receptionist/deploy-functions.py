#!/usr/bin/env python3
"""Deploy Anne's two webhook tools as Twilio Functions, with Twilio Sync for state.

Idempotent: reuses the Sync service, Serverless service and environment recorded in
.state.json (git-ignored), uploads the current sources in functions/, builds, deploys and sets
environment variables. Reads credentials from the environment or
~/.config/salon-receptionist/keys.env and never prints them.

  python3 deploy-functions.py            deploy
  python3 deploy-functions.py --dry-run  show what would be deployed; no API writes
  python3 deploy-functions.py --preserve-owner-notify  preserve callback and booking alerts
"""
import argparse, base64, json, os, shlex, sys, time, urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state.json"
KEYS = Path.home() / ".config" / "salon-receptionist" / "keys.env"
SERVICE_NAME = "salon-receptionist"
RUNTIME = "node22"
DEPENDENCIES = [{"name": "twilio", "version": "5.3.5"}, {"name": "@twilio/runtime-handler", "version": "2.0.3"}]
FUNCTIONS = [("send-booking-link", "functions/send-booking-link.js"), ("take-message", "functions/take-message.js")]
# service-links.generated.json is derived from the website (see refresh_kb.py service_links /
# --links-only) and must be regenerated before deploying if the site's treatment pages changed.
# kitomba-services.generated.json is Kitomba's full public service catalogue (refresh_catalogue.py);
# regenerate it before deploying if the salon adds, renames or removes services in Kitomba.
ASSETS = [("common", "functions/common.private.js", "/common.js", "application/javascript"),
          ("service-links", "functions/service-links.generated.json", "/service-links.json", "application/json"),
          ("kitomba-services", "functions/kitomba-services.generated.json", "/kitomba-services.json", "application/json")]
SYNC_MAPS = ["booking-cooldown", "booking-cooldown-dryrun"]
SYNC_LISTS = ["callback-messages", "callback-messages-dryrun"]
NOTIFY_KEYS = ("SALON_OWNER_NOTIFY_NUMBER", "SALON_BOOKING_LINK_NOTIFY_NUMBER")


def load_keys():
    values = {}
    for raw in KEYS.read_text().splitlines() if KEYS.exists() else []:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        parts = shlex.split(value, comments=True)
        values[key.strip()] = parts[0] if parts else ""
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
                "SALON_WEBHOOK_SECRET", *NOTIFY_KEYS):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


class Twilio:
    def __init__(self, sid, token):
        self.auth = "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode()

    def call(self, method, url, fields=None, files=None):
        headers = {"Authorization": self.auth}
        data = None
        if files:
            boundary = uuid.uuid4().hex
            parts = []
            for k, v in (fields or []):
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            for k, (filename, content, ctype) in files.items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{filename}"\r\n'
                             f'Content-Type: {ctype}\r\n\r\n'.encode() + content + b"\r\n")
            data = b"".join(parts) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif fields is not None:
            data = urllib.parse.urlencode(fields).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            detail = json.loads(e.read() or b"{}")
            # Do not print a provider message which might echo a submitted variable value.
            raise SystemExit(f"Twilio {method} {url.split('?')[0]} failed: HTTP {e.code}, code {detail.get('code')}")
        except urllib.error.URLError:
            raise SystemExit(f"Twilio {method} {url.split('?')[0]} failed: network unavailable") from None

    def find_or_create(self, list_url, key, match, fields):
        page = self.call("GET", list_url + "?PageSize=100")
        items = next(v for k, v in page.items() if isinstance(v, list))
        for item in items:
            if item.get(key) == match:
                return item, False
        return self.call("POST", list_url, fields), True


def set_variables(tw, var_url, existing, variables, notifications, preserve_owner):
    """CI preserves both alert settings; local deploys manage the two lists independently."""
    variables = dict(variables)
    if not preserve_owner:
        variables.update({key: value for key, value in notifications.items() if value})
    for key, value in variables.items():
        if key in existing:
            tw.call("POST", f"{var_url}/{existing[key]['sid']}", {"Value": value})
        else:
            tw.call("POST", var_url, {"Key": key, "Value": value})
    if not preserve_owner:
        for key, value in notifications.items():
            if not value and key in existing:
                tw.call("DELETE", f"{var_url}/{existing[key]['sid']}")


def notification_setting(variables, key):
    value = variables.get(key)
    return (value is not None, value.get("value") if value else None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preserve-owner-notify", action="store_true",
                        help="Never write or delete either live callback or booking-link notification setting")
    args = parser.parse_args(argv)
    keys = load_keys()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "SALON_WEBHOOK_SECRET"):
        if not keys.get(k):
            raise SystemExit(f"Missing {k} in the environment or {KEYS}")
    from_number = keys.get("TWILIO_FROM_NUMBER") or state.get("twilio_number", "")
    notifications = {key: keys.get(key, "") for key in NOTIFY_KEYS}
    print("Callback and booking-link notification settings:", "preserved" if args.preserve_owner_notify else "managed from local configuration")
    if args.dry_run:
        print("[dry-run] would ensure Sync service, maps", SYNC_MAPS, "lists", SYNC_LISTS)
        print("[dry-run] would upload", [f for f, _ in FUNCTIONS], "and assets", [r for _, _, r, _ in ASSETS], "build on", RUNTIME, "and deploy")
        return

    tw = Twilio(keys["TWILIO_ACCOUNT_SID"], keys["TWILIO_AUTH_TOKEN"])
    SL = "https://serverless.twilio.com/v1/Services"
    UP = "https://serverless-upload.twilio.com/v1/Services"
    svc, _ = tw.find_or_create(SL, "unique_name", SERVICE_NAME,
                               {"UniqueName": SERVICE_NAME, "FriendlyName": "Salon Ten receptionist", "IncludeCredentials": "true", "UiEditable": "false"})
    env, _ = tw.find_or_create(f"{SL}/{svc['sid']}/Environments", "unique_name", "production", {"UniqueName": "production", "DomainSuffix": "prod"})
    var_url = f"{SL}/{svc['sid']}/Environments/{env['sid']}/Variables"
    existing = {v["key"]: v for v in tw.call("GET", var_url + "?PageSize=100")["variables"]}
    original_notifications = {key: notification_setting(existing, key) for key in NOTIFY_KEYS}
    from_number = from_number or existing.get("SALON_FROM_NUMBER", {}).get("value", "")
    if not from_number:
        raise SystemExit("TWILIO_FROM_NUMBER is absent and the live environment has no SALON_FROM_NUMBER")
    SYNC = "https://sync.twilio.com/v1/Services"
    # The Sync Service resource itself has no unique_name field (only its Maps/Lists/Documents
    # subresources do); matching by unique_name here always missed and created a fresh duplicate
    # service on every deploy. A fresh CI checkout must reuse the LIVE environment's SID,
    # not choose an older duplicate by name and lose the current cooldown/message state.
    sync_sid = existing.get("SYNC_SERVICE_SID", {}).get("value") or state.get("sync_service_sid")
    if sync_sid:
        sync = tw.call("GET", f"{SYNC}/{sync_sid}")
    else:
        sync, _ = tw.find_or_create(SYNC, "friendly_name", "Salon Ten receptionist", {"FriendlyName": "Salon Ten receptionist"})
    for name in SYNC_MAPS:
        tw.find_or_create(f"{SYNC}/{sync['sid']}/Maps", "unique_name", name, {"UniqueName": name})
    for name in SYNC_LISTS:
        tw.find_or_create(f"{SYNC}/{sync['sid']}/Lists", "unique_name", name, {"UniqueName": name})
    print("Sync service:", sync["sid"])

    fversions, aversions = [], []
    for name, path in FUNCTIONS:
        fn, _ = tw.find_or_create(f"{SL}/{svc['sid']}/Functions", "friendly_name", name, {"FriendlyName": name})
        v = tw.call("POST", f"{UP}/{svc['sid']}/Functions/{fn['sid']}/Versions", [("Path", f"/{name}"), ("Visibility", "public")],
                    {"Content": (f"{name}.js", (HERE / path).read_bytes(), "application/javascript")})
        fversions.append(v["sid"])
    for name, path, route, content_type in ASSETS:
        asset, _ = tw.find_or_create(f"{SL}/{svc['sid']}/Assets", "friendly_name", name, {"FriendlyName": name})
        v = tw.call("POST", f"{UP}/{svc['sid']}/Assets/{asset['sid']}/Versions", [("Path", route), ("Visibility", "private")],
                    {"Content": (Path(path).name, (HERE / path).read_bytes(), content_type)})
        aversions.append(v["sid"])

    fields = [("FunctionVersions", s) for s in fversions] + [("AssetVersions", s) for s in aversions]
    fields += [("Dependencies", json.dumps(DEPENDENCIES)), ("Runtime", RUNTIME)]
    build = tw.call("POST", f"{SL}/{svc['sid']}/Builds", fields)
    for _ in range(60):
        status = tw.call("GET", f"{SL}/{svc['sid']}/Builds/{build['sid']}/Status")["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(5)
    if status != "completed":
        raise SystemExit(f"Build {build['sid']} ended with status {status}")

    variables = {"SALON_WEBHOOK_SECRET": keys["SALON_WEBHOOK_SECRET"], "SALON_FROM_NUMBER": from_number, "SYNC_SERVICE_SID": sync["sid"]}
    set_variables(tw, var_url, existing, variables, notifications, args.preserve_owner_notify)

    tw.call("POST", f"{SL}/{svc['sid']}/Environments/{env['sid']}/Deployments", {"BuildSid": build["sid"]})
    live_env = tw.call("GET", f"{SL}/{svc['sid']}/Environments/{env['sid']}")
    if live_env.get("build_sid") != build["sid"]:
        raise SystemExit("Deployment GET did not confirm the new build is live")
    live_vars = {v["key"]: v for v in tw.call("GET", var_url + "?PageSize=100")["variables"]}
    for key in NOTIFY_KEYS:
        expected = original_notifications[key] if args.preserve_owner_notify else (bool(notifications[key]), notifications[key] or None)
        if notification_setting(live_vars, key) != expected:
            raise SystemExit(f"Deployment GET did not confirm the expected {key} setting")
        print(f"Verified {key} is " + ("unchanged." if args.preserve_owner_notify else "configured as requested."))
    base = f"https://{env['domain_name']}"
    state.update({"sync_service_sid": sync["sid"], "serverless_service_sid": svc["sid"], "serverless_environment_sid": env["sid"],
                  "functions_base_url": base, "functions_build_sid": build["sid"],
                  "functions_asset_versions": aversions, "functions_function_versions": fversions})
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print("Deployed build", build["sid"])
    for name, _ in FUNCTIONS:
        print(f"  {base}/{name}")


if __name__ == "__main__":
    main()
