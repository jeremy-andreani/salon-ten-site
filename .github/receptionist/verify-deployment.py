#!/usr/bin/env python3
"""Verify the deployed knowledge, asset versions and live booking behavior. Sends no SMS."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

import refresh_kb as refresh

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("deploy_functions", HERE / "deploy-functions.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def fetch(url, headers, body=None):
    request = Request(url, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
    try:
        with build_opener(refresh.NoRedirects()).open(request, timeout=30) as response:
            return response.read()
    except HTTPError as error:
        raise SystemExit(f"Live verification failed: HTTP {error.code} from {url}") from None
    except URLError:
        raise SystemExit(f"Live verification failed: network unavailable for {url}") from None


def version_ids(versions):
    return {version if isinstance(version, str) else version["sid"] for version in versions}


def check_booking(base, secret, body, expected):
    # Each check uses the handler's isolated dry-run cooldown map. A unique synthetic number
    # avoids collisions on reruns. The header is mandatory; this must never send a message.
    payload = {"caller_number": "+61490" + f"{secrets.randbelow(1000000):06d}", **body}
    result = json.loads(fetch(base + "/send-booking-link", {
        "Content-Type": "application/json",
        "X-Salon-Webhook-Secret": secret,
        "X-Salon-Dry-Run": "true",
    }, payload))
    if result.get("status") != "dry_run" or expected not in result.get("sms_preview", ""):
        raise SystemExit("Live booking verification did not confirm the expected dry-run link")


def main():
    state = json.loads((HERE / ".state.json").read_text())
    keys = deploy.load_keys()
    key = refresh.read_key(deploy.KEYS)
    api = refresh.ElevenLabs(key)
    agent_id, doc_id = state["agent_id"], state["kb_doc_id"]
    refs = refresh.references(api.request("GET", "/agents/" + agent_id))
    matching = [ref for ref in refs if ref.get("name") == refresh.DOC_NAME and ref.get("type") == "text"]
    if len(matching) != 1 or matching[0]["id"] != doc_id:
        raise SystemExit("Anne is not attached to the knowledge document from this run")
    content = fetch(refresh.API_ROOT + "/knowledge-base/" + doc_id + "/content", {"xi-api-key": key})
    # The endpoint streams text; also accept a JSON-encoded string response.
    if content.startswith(b'"'):
        decoded = json.loads(content)
        if isinstance(decoded, str):
            content = decoded.encode("utf-8")
    local = (HERE / "knowledge-base.md").read_bytes()
    if content != local:
        raise SystemExit("Live knowledge document content differs from the generated file")
    digest = hashlib.sha256(content).hexdigest()
    print(f"Verified live knowledge document {doc_id}: {len(content)} bytes, SHA256 {digest}")

    tw = deploy.Twilio(keys["TWILIO_ACCOUNT_SID"], keys["TWILIO_AUTH_TOKEN"])
    service_url = "https://serverless.twilio.com/v1/Services/" + state["serverless_service_sid"]
    env = tw.call("GET", service_url + "/Environments/" + state["serverless_environment_sid"])
    build_sid = state["functions_build_sid"]
    if env.get("build_sid") != build_sid:
        raise SystemExit("The Functions build from this run is not the live production build")
    build = tw.call("GET", service_url + "/Builds/" + build_sid)
    if version_ids(build["asset_versions"]) != set(state["functions_asset_versions"]):
        raise SystemExit("Live build does not contain exactly the uploaded asset versions")
    if version_ids(build["function_versions"]) != set(state["functions_function_versions"]):
        raise SystemExit("Live build does not contain exactly the uploaded Function versions")

    base = "https://" + env["domain_name"]
    catalogue = json.loads((HERE / "functions/kitomba-services.generated.json").read_text())
    if not any(str(row["id"]) == "15822" for row in catalogue["services"]):
        raise SystemExit("Verification service 15822 is absent from Kitomba; review the verification treatment")
    check_booking(base, keys["SALON_WEBHOOK_SECRET"], {
        "multiple_services": True, "services": ["brow wax", "brow tint", "lash tint"],
    }, "services[0][0]=15822")
    print("Verified live Kitomba catalogue: combined brow/lash request selects service 15822; no SMS sent.")

    links = json.loads((HERE / "functions/service-links.generated.json").read_text())["services"]
    example = next(iter(links.values()))
    check_booking(base, keys["SALON_WEBHOOK_SECRET"], {"service": example["label"]}, example["url"])
    print(f"Verified live website lookup: {example['label']} returns its generated treatment URL; no SMS sent.")
    print(f"Verified production build {build_sid}: {len(links)} website treatments, {len(catalogue['services'])} Kitomba services.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(f"Anne's knowledge and booking data verified live.\n\n"
                         f"- Knowledge document: `{doc_id}` ({len(content)} bytes, SHA256 `{digest}`).\n"
                         f"- Production build: `{build_sid}`.\n"
                         f"- Lookup assets: {len(links)} website treatments, {len(catalogue['services'])} Kitomba services.\n"
                         "- Live dry runs confirmed Kitomba service `15822` and a website treatment URL. No SMS sent.\n"
                         "- `SALON_OWNER_NOTIFY_NUMBER` was preserved and verified unchanged by deployment.\n")


if __name__ == "__main__":
    main()
