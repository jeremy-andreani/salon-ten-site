"""Offline regression tests for changing website facts and safe live-document replacement."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import refresh_kb as refresh


ROOT = Path(__file__).resolve().parents[2]
SITE = Path(os.environ.get("SALON_SITE_DIR", ROOT / "src/Gateway.Api/wwwroot/salon-ten"))
KB = Path(__file__).with_name("knowledge-base.md")


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.site = Path(self.temporary.name) / "site"
        self.site.mkdir()
        for file in SITE.glob("*.html"):
            shutil.copyfile(file, self.site / file.name)
        self.original = KB.read_text()

    def edit(self, name, before, after):
        path = self.site / name
        text = path.read_text()
        self.assertIn(before, text)
        path.write_text(text.replace(before, after))

    def test_fresh_prices_hours_policies_and_team_without_stale_values(self):
        self.edit("hair-removal.html", "Brazilian $75", "Brazilian $81")
        self.edit("contact.html", "Monday</span><span>9:00", "Monday</span><span>10:00")
        self.edit("policies.html", "24 hours", "36 hours")
        self.edit("team.html", "Mondays, Thursdays and Fridays", "Tuesdays, Thursdays and Fridays")
        generated, _ = refresh.generate(self.original, self.site)
        self.assertIn("Brazilian $81 (women only, not men)", generated)
        self.assertNotIn("Brazilian $75", generated)
        self.assertIn("Monday: 10:00", generated)
        self.assertIn("minimum of 36 hours", generated)
        self.assertIn("Available Tuesdays, Thursdays and Fridays", generated)
        self.assertNotIn("Available Mondays, Thursdays and Fridays", generated)

    def test_hand_section_with_subheading_and_unknowns_survive_verbatim(self):
        original = self.original.replace("## Salon identity", "### Staff-only detail\n\nKeep  these spaces.\n\n## Salon identity", 1)
        extra = "- Allergies: **Unknown** (ask staff).\n  Keep this continuation exactly."
        original = original.replace("## Booking", extra + "\n\n## Booking", 1)
        staff = dict(refresh.markdown_sections(original))[refresh.STAFF]
        generated, _ = refresh.generate(original, self.site)
        self.assertEqual(staff, dict(refresh.markdown_sections(generated))[refresh.STAFF])
        self.assertIn(extra, generated)
        self.assertIn("- Instagram handle: **Unknown** (not stated on the site).", generated)
        self.assertIn("Days worked: Unknown (not stated on the site).", generated)
        self.assertIn("Price: **Unknown** (not\n  stated in the extracted source).", generated)
        self.assertNotIn("Underarm 20 min $40", generated)
        self.assertEqual([h for h, _ in refresh.markdown_sections(original)],
                         [h for h, _ in refresh.markdown_sections(generated)])

    def test_second_generation_is_stable(self):
        first, _ = refresh.generate(self.original, self.site)
        second, _ = refresh.generate(first, self.site)
        self.assertEqual(first, second)

    def test_missing_source_fails_instead_of_retaining_stale_facts(self):
        (self.site / "contact.html").unlink()
        with self.assertRaisesRegex(refresh.RefreshError, "Required website page missing"):
            refresh.generate(self.original, self.site)

    def test_older_site_without_ipl_still_preserves_its_unknown(self):
        path = self.site / "index.html"
        import re
        path.write_text(re.sub(r'<li><a href="ipl-hair-removal.html".*?</li>', "", path.read_text()))
        generated, _ = refresh.generate(self.original, self.site)
        self.assertIn("Price: **Unknown** (not\n  stated in the extracted source).", generated)

    def test_staff_rule_survives_a_site_without_inline_restriction(self):
        path = self.site / "hair-removal.html"
        text = path.read_text().replace(" (women only, not men)", "").replace(
            " Sorry, intimate waxing is available to female clients only.", "")
        self.assertNotIn("women only", text)
        self.assertNotIn("female clients only", text)
        path.write_text(text)
        generated, _ = refresh.generate(self.original, self.site)
        self.assertIn("Brazilian $75 (women only, not men)", generated)

    def test_service_links_only_include_pages_with_a_specific_booking_id(self):
        pages = refresh.load_pages(self.site)
        links = refresh.service_links(pages)
        self.assertIn("microneedling", links)
        self.assertEqual("Skin Microneedling", links["microneedling"]["label"])
        self.assertIn("services[0][0]=100000000172113330", links["microneedling"]["url"])
        # Multi-treatment category pages carry only the generic all-services link.
        self.assertNotIn("massage", links)
        self.assertNotIn("hair-removal", links)
        self.assertNotIn("promotions", links)

    def test_service_links_track_a_site_change(self):
        self.edit("microneedling.html",
                   "services[0][0]=100000000172113330", "services[0][0]=999999")
        pages = refresh.load_pages(self.site)
        links = refresh.service_links(pages)
        self.assertIn("services[0][0]=999999", links["microneedling"]["url"])

    def test_links_only_writes_generated_map_without_kb_or_credentials(self):
        links_file = Path(self.temporary.name) / "service-links.json"
        with patch.object(refresh, "read_key", side_effect=AssertionError("credential read")), \
             patch.object(refresh, "ElevenLabs", side_effect=AssertionError("API call")), \
             contextlib.redirect_stdout(io.StringIO()):
            result = refresh.run(["--links-only", "--site-dir", str(self.site),
                                  "--links-file", str(links_file)])
        self.assertEqual(0, result)
        written = json.loads(links_file.read_text())
        self.assertIn("microneedling", written["services"])
        self.assertEqual(11, len(written["services"]))

    def test_links_only_dry_run_writes_nothing(self):
        links_file = Path(self.temporary.name) / "service-links.json"
        with contextlib.redirect_stdout(io.StringIO()):
            result = refresh.run(["--links-only", "--dry-run", "--site-dir", str(self.site),
                                  "--links-file", str(links_file)])
        self.assertEqual(0, result)
        self.assertFalse(links_file.exists())

    def test_dry_run_never_loads_credentials_calls_api_or_writes_files(self):
        state = Path(self.temporary.name) / "state.json"
        copy_kb = Path(self.temporary.name) / "knowledge-base.md"
        copy_kb.write_text(self.original)
        with patch.object(refresh, "read_key", side_effect=AssertionError("credential read")), \
             patch.object(refresh, "ElevenLabs", side_effect=AssertionError("API call")), \
             patch.object(refresh, "atomic_write", side_effect=AssertionError("file write")), \
             contextlib.redirect_stdout(io.StringIO()):
            result = refresh.run(["--dry-run", "--site-dir", str(self.site),
                                  "--kb-file", str(copy_kb), "--state-file", str(state)])
        self.assertEqual(0, result)
        self.assertEqual(self.original, copy_kb.read_text())
        self.assertFalse(state.exists())


class FakeAPI:
    def __init__(self, fail=None, drift=False, empty=False):
        self.refs = [{"id": "live-old", "name": refresh.DOC_NAME, "type": "text", "usage_mode": "auto"},
                     {"id": "unrelated", "name": "other", "type": "file"}]
        self.before = copy.deepcopy(self.refs)
        self.calls = []
        self.fail = fail
        self.drift = drift
        self.empty = empty
        self.gets = 0

    def request(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if self.fail == method:
            raise refresh.RefreshError(f"simulated {method} failure")
        if method == "GET":
            self.gets += 1
            if self.drift and self.gets == 2:
                self.refs.append({"id": "concurrent", "name": "new staff file", "type": "text"})
            return {"conversation_config": {"agent": {"prompt": {"knowledge_base": copy.deepcopy(self.refs)}}}}
        if method == "POST":
            return {"id": "live-new", "name": refresh.DOC_NAME}
        if method == "PATCH":
            self.refs = copy.deepcopy(body["conversation_config"]["agent"]["prompt"]["knowledge_base"])
            if self.empty:
                self.refs = []
                self.empty = False
        return {}


class SwapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / ".state.json"

    def publish(self, api):
        with contextlib.redirect_stdout(io.StringIO()):
            return refresh.publish(api, refresh.DEFAULT_AGENT, KB.read_text(), self.state)

    def test_fresh_ci_discovers_live_doc_and_only_deletes_after_confirmation(self):
        api = FakeAPI()
        self.assertEqual("live-new", self.publish(api))
        self.assertEqual(["GET", "POST", "GET", "PATCH", "GET", "DELETE"], [c[0] for c in api.calls])
        self.assertEqual(api.before[1], api.refs[1])
        self.assertEqual("auto", api.refs[0]["usage_mode"])
        self.assertEqual("live-new", json.loads(self.state.read_text())["kb_doc_id"])
        self.assertEqual("/knowledge-base/live-old", api.calls[-1][1])
        self.assertEqual({"knowledge_base"}, set(api.calls[3][2]["conversation_config"]["agent"]["prompt"]))

    def test_stale_local_state_cannot_select_the_wrong_old_doc(self):
        self.state.write_text(json.dumps({"kb_doc_id": "obsolete-id", "other_setting": "keep"}))
        api = FakeAPI()
        self.publish(api)
        self.assertEqual("/knowledge-base/live-old", api.calls[-1][1])
        self.assertEqual("keep", json.loads(self.state.read_text())["other_setting"])

    def test_create_failure_keeps_existing_attachment(self):
        api = FakeAPI(fail="POST")
        with self.assertRaisesRegex(refresh.RefreshError, "POST failure"):
            self.publish(api)
        self.assertEqual(api.before, api.refs)
        self.assertFalse(self.state.exists())

    def test_patch_failure_does_not_delete_either_document_or_update_state(self):
        api = FakeAPI(fail="PATCH")
        with self.assertRaisesRegex(refresh.RefreshError, "no deletion attempted"):
            self.publish(api)
        self.assertEqual(api.before, api.refs)
        self.assertNotIn("DELETE", [c[0] for c in api.calls])
        self.assertFalse(self.state.exists())

    def test_concurrent_change_is_not_overwritten(self):
        api = FakeAPI(drift=True)
        with self.assertRaisesRegex(refresh.RefreshError, "concurrent edits"):
            self.publish(api)
        self.assertNotIn("PATCH", [c[0] for c in api.calls])
        self.assertNotIn("DELETE", [c[0] for c in api.calls])

    def test_empty_attachment_is_restored_before_reporting_failure(self):
        api = FakeAPI(empty=True)
        with self.assertRaisesRegex(refresh.RefreshError, "restored the original attachment"):
            self.publish(api)
        self.assertEqual(api.before, api.refs)
        self.assertNotIn("DELETE", [c[0] for c in api.calls])

    def test_failed_confirmation_retains_both_documents_and_no_success_state(self):
        api = FakeAPI()
        request = api.request
        def fail_confirmation(method, path, body=None):
            if method == "GET" and api.gets == 2:
                raise refresh.RefreshError("confirmation GET unavailable")
            return request(method, path, body)
        api.request = fail_confirmation
        with self.assertRaisesRegex(refresh.RefreshError, "no deletion attempted"):
            self.publish(api)
        self.assertEqual("live-new", api.refs[0]["id"])
        self.assertNotIn("DELETE", [c[0] for c in api.calls])
        self.assertFalse(self.state.exists())

    def test_ambiguous_live_documents_stop_before_creation(self):
        api = FakeAPI()
        api.refs.append(dict(api.refs[0], id="duplicate"))
        with self.assertRaisesRegex(refresh.RefreshError, "found 2"):
            self.publish(api)
        self.assertEqual(["GET"], [c[0] for c in api.calls])

    def test_failed_cleanup_keeps_new_doc_live_and_state_accurate(self):
        api = FakeAPI(fail="DELETE")
        with self.assertRaisesRegex(refresh.RefreshError, "Replacement is verified live"):
            self.publish(api)
        self.assertEqual("live-new", api.refs[0]["id"])
        self.assertEqual("live-new", json.loads(self.state.read_text())["kb_doc_id"])


if __name__ == "__main__":
    unittest.main()
