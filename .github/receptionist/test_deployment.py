"""Offline checks for fresh-runner deployment and owner-setting preservation."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


deploy = module("deploy_functions", "deploy-functions.py")
verify = module("verify_deployment", "verify-deployment.py")


class FakeTwilio:
    def __init__(self, build_status="completed", owner=True, booking=True):
        self.calls = []
        self.build_status = build_status
        self.live_build = "previous-build"
        self.variables = [
            {"key": "SYNC_SERVICE_SID", "sid": "sync-var", "value": "live-sync"},
            {"key": "SALON_FROM_NUMBER", "sid": "from-var", "value": "+61400000001"},
        ]
        if owner:
            self.variables.append({"key": "SALON_OWNER_NOTIFY_NUMBER", "sid": "owner-var", "value": "existing-owner"})
        if booking:
            self.variables.append({"key": "SALON_BOOKING_LINK_NOTIFY_NUMBER", "sid": "booking-var", "value": "existing-booking"})

    def find_or_create(self, url, key, match, fields):
        self.calls.append(("FIND", url, fields))
        if match == "salon-receptionist":
            return {"sid": "service"}, False
        if match == "production":
            return {"sid": "environment", "domain_name": "example.twil.io"}, False
        if match == "Salon Ten receptionist":
            raise AssertionError("Fresh CI must use the live Sync SID, not rediscover a duplicate by name")
        return {"sid": "resource-" + match}, False

    def call(self, method, url, fields=None, files=None):
        self.calls.append((method, url, fields))
        if method == "GET" and "/Variables?" in url:
            return {"variables": self.variables}
        if method == "GET" and url.endswith("/live-sync"):
            return {"sid": "live-sync"}
        if method == "POST" and url.endswith("/Versions"):
            return {"sid": "version-" + url.split("/")[-2]}
        if method == "POST" and url.endswith("/Builds"):
            return {"sid": "new-build"}
        if method == "GET" and url.endswith("/Status"):
            return {"status": self.build_status}
        if method == "POST" and "/Variables" in url:
            if url.endswith("/Variables"):
                self.variables.append({"key": fields["Key"], "sid": fields["Key"] + "-var", "value": fields["Value"]})
            else:
                variable = next(v for v in self.variables if url.endswith("/" + v["sid"]))
                variable["value"] = fields["Value"]
            return {}
        if method == "DELETE" and "/Variables/" in url:
            self.variables = [v for v in self.variables if not url.endswith("/" + v["sid"])]
            return {}
        if method == "POST" and url.endswith("/Deployments"):
            self.live_build = fields["BuildSid"]
            return {}
        if method == "GET" and url.endswith("/Environments/environment"):
            return {"build_sid": self.live_build}
        raise AssertionError(f"Unexpected API operation: {method} {url}")


class DeploymentTests(unittest.TestCase):
    def run_deploy(self, tw, path, owner="", booking=None, preserve=True):
        keys = {"TWILIO_ACCOUNT_SID": "account", "TWILIO_AUTH_TOKEN": "token",
                "SALON_WEBHOOK_SECRET": "webhook", "SALON_OWNER_NOTIFY_NUMBER": owner}
        if booking is not None:
            keys["SALON_BOOKING_LINK_NOTIFY_NUMBER"] = booking
        with patch.object(deploy, "load_keys", return_value=keys), patch.object(deploy, "STATE", path), \
                patch.object(deploy, "Twilio", return_value=tw), contextlib.redirect_stdout(io.StringIO()):
            deploy.main(["--preserve-owner-notify"] if preserve else [])

    def test_fresh_checkout_reuses_live_sync_and_never_changes_owner(self):
        for configured_owner in ("", "different-owner"):
            for live_owner in (True, False):
                with self.subTest(configured=configured_owner, live=live_owner), tempfile.TemporaryDirectory() as tmp:
                    state = Path(tmp) / ".state.json"
                    tw = FakeTwilio(owner=live_owner)
                    self.run_deploy(tw, state, configured_owner)
                    written = json.loads(state.read_text())
                    self.assertEqual(written["sync_service_sid"], "live-sync")
                    self.assertEqual(written["functions_build_sid"], "new-build")
                    self.assertEqual(len(written["functions_asset_versions"]), 3)
                    mutations = [(m, u, f) for m, u, f in tw.calls if m in ("POST", "DELETE")]
                    self.assertFalse(any("owner-var" in u or "SALON_OWNER_NOTIFY_NUMBER" in str(f) for m, u, f in mutations))
                    self.assertFalse(any("booking-var" in u or "SALON_BOOKING_LINK_NOTIFY_NUMBER" in str(f) for m, u, f in mutations))

    def test_automated_deploy_preserves_booking_alerts_even_with_a_local_override(self):
        for live_booking in (True, False):
            with self.subTest(live=live_booking), tempfile.TemporaryDirectory() as tmp:
                tw = FakeTwilio(booking=live_booking)
                self.run_deploy(tw, Path(tmp) / ".state.json", booking="different-booking")
                mutations = [(m, u, f) for m, u, f in tw.calls if m in ("POST", "DELETE")]
                self.assertFalse(any("booking-var" in u or "SALON_BOOKING_LINK_NOTIFY_NUMBER" in str(f) for m, u, f in mutations))

    def test_local_deploy_manages_booking_and_callback_alerts_independently(self):
        for live_booking in (True, False):
            for booking in (None, "", "+61400000002,+61400000003"):
                with self.subTest(live=live_booking, configured=booking), tempfile.TemporaryDirectory() as tmp:
                    tw = FakeTwilio(booking=live_booking)
                    self.run_deploy(tw, Path(tmp) / ".state.json", owner="existing-owner", booking=booking, preserve=False)
                    values = {v["key"]: v["value"] for v in tw.variables}
                    self.assertEqual(values["SALON_OWNER_NOTIFY_NUMBER"], "existing-owner")
                    if booking:
                        self.assertEqual(values["SALON_BOOKING_LINK_NOTIFY_NUMBER"], booking)
                    else:
                        self.assertNotIn("SALON_BOOKING_LINK_NOTIFY_NUMBER", values)
        with tempfile.TemporaryDirectory() as tmp:
            tw = FakeTwilio()
            self.run_deploy(tw, Path(tmp) / ".state.json", owner="", booking="booking-only", preserve=False)
            values = {v["key"]: v["value"] for v in tw.variables}
            self.assertNotIn("SALON_OWNER_NOTIFY_NUMBER", values)
            self.assertEqual(values["SALON_BOOKING_LINK_NOTIFY_NUMBER"], "booking-only")

    def test_booking_alert_setting_is_verified_by_reading_live_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            tw = FakeTwilio()
            original_call = tw.call
            def ignore_booking_write(method, url, fields=None, files=None):
                if method == "POST" and url.endswith("/booking-var"):
                    return {}
                return original_call(method, url, fields, files)
            tw.call = ignore_booking_write
            state = Path(tmp) / ".state.json"
            with self.assertRaisesRegex(SystemExit, "did not confirm the expected SALON_BOOKING_LINK_NOTIFY_NUMBER"):
                self.run_deploy(tw, state, booking="new-booking", preserve=False)
            self.assertFalse(state.exists())

    def test_failed_build_does_not_deploy_or_write_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / ".state.json"
            tw = FakeTwilio(build_status="failed")
            with self.assertRaisesRegex(SystemExit, "ended with status failed"):
                self.run_deploy(tw, state)
            self.assertFalse(state.exists())
            self.assertFalse(any("/Deployments" in u for _, u, _ in tw.calls))
            self.assertFalse(any(m == "POST" and "/Variables" in u for m, u, _ in tw.calls))

    def test_env_credentials_work_without_a_local_key_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(deploy, "KEYS", Path(tmp) / "absent"), \
                patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "ci-account", "TWILIO_AUTH_TOKEN": "ci-token"}, clear=True):
            self.assertEqual(deploy.load_keys(), {"TWILIO_ACCOUNT_SID": "ci-account", "TWILIO_AUTH_TOKEN": "ci-token"})

    def test_env_credentials_override_local_values_without_printing(self):
        with tempfile.TemporaryDirectory() as tmp:
            keys = Path(tmp) / "keys.env"
            keys.write_text("export TWILIO_AUTH_TOKEN='local-token' # comment\n")
            output = io.StringIO()
            with patch.object(deploy, "KEYS", keys), patch.dict(os.environ, {"TWILIO_AUTH_TOKEN": "ci-token"}, clear=True), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(deploy.load_keys()["TWILIO_AUTH_TOKEN"], "ci-token")
            self.assertEqual(output.getvalue(), "")

    def test_booking_alert_environment_overrides_local_values_including_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            keys = Path(tmp) / "keys.env"
            keys.write_text("SALON_BOOKING_LINK_NOTIFY_NUMBER='+61400000002,+61400000003'\n")
            with patch.object(deploy, "KEYS", keys), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(deploy.load_keys()["SALON_BOOKING_LINK_NOTIFY_NUMBER"], "+61400000002,+61400000003")
                for value in ("+61400000004", ""):
                    with patch.dict(os.environ, {"SALON_BOOKING_LINK_NOTIFY_NUMBER": value}):
                        self.assertEqual(deploy.load_keys()["SALON_BOOKING_LINK_NOTIFY_NUMBER"], value)

    def test_verification_uses_dry_run_and_rejects_wrong_lookup(self):
        with patch.object(verify, "fetch", return_value=b'{"status":"dry_run","sms_preview":"services[0][0]=15822"}') as fetch:
            verify.check_booking("https://example.twil.io", "secret", {"services": ["brow wax"]}, "15822")
            self.assertEqual(fetch.call_args.args[1]["X-Salon-Dry-Run"], "true")
        for result in (b'{"status":"accepted","sms_preview":"15822"}', b'{"status":"dry_run","sms_preview":"wrong"}'):
            with patch.object(verify, "fetch", return_value=result), self.assertRaises(SystemExit):
                verify.check_booking("https://example.twil.io", "secret", {}, "15822")


if __name__ == "__main__":
    unittest.main()
