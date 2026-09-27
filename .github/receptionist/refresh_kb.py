#!/usr/bin/env python3
"""Regenerate Salon Ten facts and safely replace Anne's ElevenLabs text document.

Python 3.9+, standard library only. --dry-run performs no API calls or file writes.
"""

import argparse
import copy
import difflib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


KIT = Path(__file__).resolve().parent
DEFAULT_AGENT = "agent_1201m3gynnfxff6t102hxt3759rv"
DOC_NAME = "salon-ten-knowledge-base"
STAFF = "## Staff clarifications (hand-maintained, keep on refresh)"
API_ROOT = "https://api.elevenlabs.io/v1/convai"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class RefreshError(Exception):
    pass


def clean(text):
    return re.sub(r"\s+", " ", text.replace("\u2014", "; ")).strip()


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def find(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or child.has_class(cls)):
                    result.append(child)
                result.extend(child.find(tag, cls))
        return result

    def text(self, omit_classes=()):
        return clean(" ".join(
            child if isinstance(child, str) else child.text(omit_classes)
            for child in self.children
            if isinstance(child, str) or (
                child.tag not in {"script", "style", "nav"}
                and not any(child.has_class(c) for c in omit_classes)
            )
        ))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def one(nodes, label):
    if not nodes:
        raise RefreshError(f"Required website field missing: {label}; nothing uploaded")
    return nodes[0]


def load_pages(site):
    pages = {}
    for file in sorted(site.glob("*.html")):
        parser = PageParser()
        parser.feed(file.read_text(encoding="utf-8"))
        pages[file.name] = parser.root
    for name in ["index.html", "contact.html", "faq.html", "policies.html", "team.html",
                 "about.html", "hair-removal.html", "promotions.html"]:
        if name not in pages or not pages[name].find("main"):
            raise RefreshError(f"Required website page missing or has no main element: {name}")
    return pages


def main(page):
    return one(page.find("main"), "main")


def definitions(page):
    terms = main(page).find("dt")
    values = main(page).find("dd")
    if not terms or len(terms) != len(values):
        raise RefreshError("FAQ/policy definition list is missing or unbalanced")
    return [(term.text(), value.text()) for term, value in zip(terms, values)]


def markdown_sections(text):
    matches = list(re.finditer(r"^#{2,3} [^\n]+\n", text, re.M))
    if not matches:
        raise RefreshError("Knowledge base has no section headings")
    # A staff section may contain its own ### subheadings. They belong to the hand-kept
    # block, which ends only at the next ## heading.
    filtered = []
    inside_staff = False
    for match in matches:
        heading = match.group().rstrip("\n")
        if heading.startswith("## "):
            inside_staff = heading == STAFF
        elif inside_staff:
            continue
        filtered.append(match)
    matches = filtered
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append((match.group().rstrip("\n"), text[match.start():end]))
    return result


def unknown_entries(sections):
    """Keep full unknown bullets; separate only the two legacy mixed fact/unknown fields."""
    retained = {}
    field_unknowns = {}
    for heading, section in sections:
        if heading == STAFF:
            continue
        blocks = re.findall(r"(?m)^- [^\n]*(?:\n(?!- |#{1,3} |\s*$)[^\n]+)*", section)
        for block in blocks:
            if not re.search(r"\bUnknown\b", block, re.I):
                continue
            if heading == "## Team" and block.startswith("- **Kellie**"):
                match = re.search(r"Days worked:.*\bUnknown\b.*", block, re.S)
                if match:
                    field_unknowns["Kellie"] = match.group()
                    continue
            if heading == "### Beauty" and block.startswith("- **IPL Hair Removal**"):
                # Retain this complete unknown entry verbatim, rather than silently making up
                # a resolution when the website has acquired a price since the manual extract.
                field_unknowns["IPL Hair Removal"] = block
                continue
            retained.setdefault(heading, []).append(block)
    return retained, field_unknowns


def bullet(label, value, source):
    return f"- **{clean(label)}**: {clean(value)} (Source: {source})"


def sentences(text):
    return re.split(r"(?<=[.!?])\s+", text)


def service_facts(page, filename, label):
    articles = main(page).find("article", "treatment")
    if not articles:
        raise RefreshError(f"No treatment cards in {filename}; refusing to lose {label}")
    rows = []
    for article in articles:
        heading = article.find("h2")
        name = heading[0].text(("price",)) if heading else label
        facts = [node.text() for node in article.find(cls="price")]
        facts += [node.text() for node in article.find(cls="lead-price")]
        facts += [node.text() for node in article.find(cls="duration")]
        facts += [node.text() for node in article.find(cls="also-known")]
        facts += [node.text() for node in article.find(cls="sub-prices")]
        # Only operational details, treatment inclusions and durations. Do not turn website
        # marketing claims or suitability descriptions into receptionist advice.
        for paragraph in article.find("p"):
            if paragraph.attrs.get("class") or paragraph.find("a"):
                continue
            for sentence in sentences(paragraph.text()):
                if re.search(r"\brequired\b|\bnot offered\b|\bdoes not remove\b|^For ages\b|"
                             r"^All ear piercings include\b|^Includes\b|^A consultation is included",
                             sentence, re.I):
                    facts.append(sentence)
            durations = re.findall(r"\b\d+[ -](?:minutes?|hours?)\b|\b(?:an hour|two-hour|Seventy minutes)\b",
                                   paragraph.text(), re.I)
            if durations:
                facts.append("Duration mentioned on site: " + ", ".join(dict.fromkeys(durations)))
        facts += [node.text() for node in article.find("li")]
        if not facts:
            facts = ["Price and duration: Unknown (not stated in the selected website fields)."]
        rows.append(bullet(name, " · ".join(dict.fromkeys(facts)), filename))
    return rows


def generate(original, site):
    sections = markdown_sections(original)
    staff_sections = [raw for heading, raw in sections if heading == STAFF]
    if len(staff_sections) != 1:
        raise RefreshError(f"Expected exactly one '{STAFF}' section; nothing uploaded")
    staff = staff_sections[0]
    preserved, fields = unknown_entries(sections)
    pages = load_pages(site)
    faq = definitions(pages["faq.html"])
    policy = definitions(pages["policies.html"])
    generated = {}
    notices = []

    identity = one(pages["contact.html"].find("footer"), "site footer").find("p")
    generated["## Salon identity"] = [bullet("Name", "Salon Ten", "contact.html"),
                                      bullet("Salon", one(identity, "salon description").text(), "contact.html")]
    generated["## Salon identity"] += [bullet("Award", n.text(), "about.html")
                                       for n in main(pages["about.html"]).find("li")]
    generated["## Salon identity"] += [bullet(title, value, "policies.html")
                                       for title, value in policy if "ABIC" in title]

    contact = one(main(pages["contact.html"]).find(cls="contact-list"), "contact list")
    contact_rows = []
    for item in contact.find("li"):
        label = one(item.find(cls="label"), "contact label").text()
        value = item.text(("label",))
        links = [n.attrs.get("href", "") for n in item.find("a")]
        if links and links[0].startswith("https://"):
            value += " " + links[0]
        contact_rows.append(bullet(label, value, "contact.html"))
    contact_rows += [bullet(title, value, "faq.html") for title, value in faq
                     if "parking" in title.lower() or "located" in title.lower()]
    generated["## Contact"] = contact_rows

    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours = {}
    for row in main(pages["contact.html"]).find(cls="loc-row"):
        label = one(row.find(cls="label"), "location row label").text()
        if label in weekdays:
            hours[label] = row.text(("label",))
    if set(hours) != set(weekdays) or any(not value for value in hours.values()):
        raise RefreshError("Contact page must state all seven opening days; nothing uploaded")
    generated["## Hours"] = [f"- {day}: {hours[day]}" for day in weekdays]

    booking_links = [n.attrs["href"] for n in main(pages["contact.html"]).find("a")
                     if n.text() == "Book Now" and n.attrs.get("href", "").startswith("https://")]
    generated["## Booking"] = [bullet("Online booking link", one(booking_links, "booking link"), "contact.html")]
    generated["## Booking"] += [bullet(title, value, "faq.html") for title, value in faq
                                 if re.search(r"bookings essential|gift voucher|booked online", title, re.I)]

    team = []
    for card in main(pages["team.html"]).find(cls="team-card"):
        name = one(card.find("h2"), "team member name").text()
        facts = [one(card.find(cls="role"), "team member role").text()]
        text = card.text()
        match = re.search(r"\bavailable ((?:(?:Mondays?|Tuesdays?|Wednesdays?|Thursdays?|Fridays?|Saturdays?|Sundays?)[, ]*(?:and )?)+)", text, re.I)
        if match and name not in fields:
            facts.append("Available " + match.group(1).rstrip(" ,"))
        if re.search(r"diploma[ -]qualified", text, re.I):
            facts.append("Diploma-qualified")
        experience = re.search(r"\b\d+ years[’']? experience\b", text)
        if experience:
            facts.append(experience.group())
        career = re.search(r"started my career in \d{4}", text, re.I)
        if career:
            facts.append(career.group().replace("my", "her"))
        studies = re.search(r"undergraduate studies in [^.]+", text, re.I)
        if studies:
            facts.append(studies.group())
        team.append(bullet(name, ". ".join(facts), "team.html"))
        if name in fields:
            team[-1] += " " + fields[name]
    if not team:
        raise RefreshError("No team cards found; nothing uploaded")
    generated["## Team"] = team

    generated["## Policies (site: Policies page)"] = [bullet(title, value, "policies.html")
        for title, value in policy if title not in {"Expert Education & Training", "Environment Sustainability", "ABIC Members"}]
    generated["## Policies (site: Policies page)"] += [bullet(title, value, "faq.html")
        for title, value in faq if re.search(r"payment|referral|arrive", title, re.I)]

    category_map = {"Skin": "### Skin", "Body": "### Body (relax/unwind)", "Beauty": "### Beauty"}
    seen = set()
    for group in main(pages["index.html"]).find(cls="treat-cat"):
        category = one(group.find(cls="sub"), "treatment category").text()
        if category not in category_map:
            raise RefreshError(f"Unmapped treatment category {category!r}; add it to the KB structure first")
        heading = category_map[category]
        generated.setdefault(heading, [])
        for link in group.find("a"):
            filename = urlsplit(link.attrs.get("href", "")).path
            if filename in seen or filename == "promotions.html":
                continue
            seen.add(filename)
            label = link.text(("arrow",))
            if filename not in pages:
                raise RefreshError(f"Treatment page {filename!r} referenced by index.html is missing")
            if label in fields:
                generated[heading].append(fields[label])
                notices.append(f"Retained {label} Unknown entry verbatim; website facts for this entry remain withheld until staff resolve it.")
            else:
                generated[heading] += service_facts(pages[filename], filename, label)
    if any(not generated.get(heading) for heading in category_map.values()):
        raise RefreshError("Skin, Body and Beauty treatment categories must all be populated")
    # Staff instructions stay authoritative even if an older checkout omits the inline note.
    if "Brazilian waxing is offered for women only, not men." in staff:
        for index, row in enumerate(generated["### Beauty"]):
            if "Brazilian $" in row and "women only" not in row:
                generated["### Beauty"][index] = re.sub(r"Brazilian (\$[\d,.]+)",
                    r"Brazilian \1 (women only, not men)", row)
        generated["### Beauty"].append("- Brazilian waxing is offered for women only, not men. (Source: Staff clarifications)")

    promo_head = next((heading for heading, _ in sections if heading.startswith("### Promotions")), None)
    if not promo_head:
        raise RefreshError("Knowledge base is missing its Promotions section")
    generated[promo_head] = service_facts(pages["promotions.html"], "promotions.html", "Promotions")
    generated[promo_head] += [bullet("Promotion currency", n.text(), "promotions.html")
                              for n in main(pages["promotions.html"]).find(cls="promo-note")]
    generated[promo_head].append("- Confirm seasonal offers through the booking link; do not promise they are current.")
    generated["## Reviews (for colour only, never quote as a guarantee of outcome)"] = [
        "- Website testimonials are customer opinions. Never quote them as a guarantee of outcome."]
    generated["## Feedback and complaints"] = [bullet(title, value, "faq.html")
        for title, value in faq if "feedback" in title.lower()]
    generated["## Charity"] = [bullet(title, value, "faq.html")
        for title, value in faq if "charity" in title.lower()]
    if "IPL Hair Removal" in fields and fields["IPL Hair Removal"] not in generated["### Beauty"]:
        generated["### Beauty"].append(fields["IPL Hair Removal"])
    if "Kellie" in fields and not any(fields["Kellie"] in row for row in generated["## Team"]):
        generated["## Team"].append("- Kellie (hand-kept field): " + fields["Kellie"])
    for heading, rows in generated.items():
        if not rows:
            raise RefreshError(f"No facts extracted for {heading}")

    introduction = (
        "# Salon Ten - Knowledge Base\n\n"
        "Source: Salon Ten website HTML in the Git checkout. Each generated entry names its source page.\n"
        "Staff clarifications below take precedence over general website descriptions. Retained\n"
        "Unknown entries stay unknown until staff resolve them; never guess a missing fact.\n\n"
    )
    output = [introduction]
    for heading, raw in sections:
        if heading == STAFF or heading not in generated:
            output.append(raw)
            continue
        rows = generated[heading]
        for unknown in preserved.get(heading, []):
            # A hand-kept field can also appear in structured HTML: its Unknown wins.
            key = re.split(r"[:\u2014]", unknown[2:], maxsplit=1)[0].replace("**", "").strip().lower()
            rows = [row for row in rows if re.split(r"[:\u2014]", row[2:], maxsplit=1)[0].replace("**", "").strip().lower() != key]
            if unknown not in rows:
                rows.append(unknown)
        output.append(heading + "\n\n" + "\n".join(rows) + "\n\n")
    result = "".join(output)
    if staff not in result:
        raise RefreshError("Hand-maintained clarifications changed during extraction")
    for entries in preserved.values():
        if any(entry not in result for entry in entries):
            raise RefreshError("A hand-kept Unknown entry was lost")
    if any(field not in result for field in fields.values()):
        raise RefreshError("A legacy Unknown field was lost")
    return result, notices


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ElevenLabs:
    def __init__(self, key):
        self.key = key
        self.opener = build_opener(NoRedirects())

    def request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(API_ROOT + path, data=data, method=method,
                          headers={"xi-api-key": self.key, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=25) as response:
                payload = response.read()
                return json.loads(payload) if payload else {}
        except HTTPError as error:
            # Never print headers, credentials, provider bodies or a response that may echo them.
            raise RefreshError(f"ElevenLabs {method} {path} failed: HTTP {error.code}") from None
        except (URLError, OSError, ValueError) as error:
            reason = str(error).replace(self.key, "[redacted]")
            raise RefreshError(f"ElevenLabs {method} {path} failed: {reason}") from None


def read_key(keys_file):
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"]
    if keys_file.exists():
        for line in keys_file.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*(?:export\s+)?ELEVENLABS_API_KEY\s*=\s*(.*)", line)
            if match:
                values = shlex.split(match.group(1), comments=True)
                if len(values) == 1 and values[0]:
                    return values[0]
    raise RefreshError(f"ELEVENLABS_API_KEY is absent from the environment and {keys_file}")


def references(agent):
    try:
        refs = agent["conversation_config"]["agent"]["prompt"]["knowledge_base"]
    except (KeyError, TypeError):
        raise RefreshError("Agent GET did not include knowledge_base; refusing to replace it") from None
    if not isinstance(refs, list) or any(not isinstance(ref, dict) or not ref.get("id") for ref in refs):
        raise RefreshError("Malformed knowledge_base in agent GET")
    return refs


def patch_body(refs):
    return {"conversation_config": {"agent": {"prompt": {"knowledge_base": refs}}}}


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def publish(api, agent_id, text, state_path):
    """Discover live references, create, attach, GET-verify, then delete. Never force-delete."""
    path = "/agents/" + quote(agent_id, safe="")
    before = references(api.request("GET", path))
    matching = [ref for ref in before if ref.get("name") == DOC_NAME and ref.get("type") == "text"]
    if len(matching) != 1:
        raise RefreshError(f"Expected one attached text document named {DOC_NAME}; found {len(matching)}. Nothing changed.")
    old = matching[0]
    # Check local state can be read before modifying the agent; it is never used for discovery.
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    created = api.request("POST", "/knowledge-base/text", {"name": DOC_NAME, "text": text})
    new_id = created.get("id")
    if not isinstance(new_id, str) or not new_id or new_id == old["id"]:
        raise RefreshError("Create document response had no new id; agent was not changed")
    print(f"Created replacement text document {new_id}; old document {old['id']} is still retained.")
    desired = copy.deepcopy(before)
    desired[before.index(old)]["id"] = new_id
    # Preserve usage_mode and all other documents, and do not patch the prompt, voice or tools.
    try:
        current = references(api.request("GET", path))
        if current != before:
            raise RefreshError("Agent KB changed during refresh; refusing to overwrite concurrent edits")
        api.request("PATCH", path, patch_body(desired))
        confirmed = references(api.request("GET", path))
        if confirmed != desired:
            ids = {ref["id"] for ref in confirmed}
            if new_id not in ids and old["id"] not in ids:
                # Repair an observed missing salon attachment, retaining any unrelated current
                # documents. An empty response is restored to the entire known working list.
                restored = copy.deepcopy(confirmed) + [copy.deepcopy(old)] if confirmed else before
                api.request("PATCH", path, patch_body(restored))
                if references(api.request("GET", path)) != restored:
                    raise RefreshError("URGENT: salon KB is missing and restoring it could not be verified")
                raise RefreshError("Salon KB was missing; restored the original attachment and verified it by GET")
            raise RefreshError("Agent GET did not confirm the complete replacement knowledge_base")
    except RefreshError as error:
        # A timed-out PATCH may have succeeded. Never delete either document on an uncertain
        # attach, and never overwrite a later edit with an automatic blind rollback.
        raise RefreshError(f"{error}. Old document {old['id']} and replacement {new_id} retained; no deletion attempted.") from None
    print(f"Verified live by GET: {agent_id} references {new_id}, not {old['id']}.")
    # Save the verified live id before cleanup so a failed delete cannot leave misleading state.
    state.update(agent_id=agent_id, kb_doc_id=new_id)
    atomic_write(state_path, json.dumps(state, indent=2) + "\n")
    try:
        api.request("DELETE", "/knowledge-base/" + quote(old["id"], safe=""))
    except RefreshError as error:
        raise RefreshError(f"Replacement is verified live and state is updated, but old-document cleanup failed: {error}") from None
    print(f"Deleted old document {old['id']}; updated {state_path.name}.")
    return new_id


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print a diff; no API calls, credentials or writes")
    parser.add_argument("--upload-existing", action="store_true", help="Publish only the hand-edited KB, without regeneration")
    parser.add_argument("--site-dir", type=Path, default=KIT.parents[1] / "src/Gateway.Api/wwwroot/salon-ten")
    parser.add_argument("--kb-file", type=Path, default=KIT / "knowledge-base.md")
    parser.add_argument("--state-file", type=Path, default=KIT / ".state.json")
    parser.add_argument("--keys-file", type=Path, default=Path.home() / ".config/salon-receptionist/keys.env")
    parser.add_argument("--agent-id", default=os.environ.get("ELEVENLABS_AGENT_ID", DEFAULT_AGENT))
    args = parser.parse_args(argv)
    try:
        original = args.kb_file.read_text(encoding="utf-8")
        if args.upload_existing:
            updated, notices = original, []
        else:
            updated, notices = generate(original, args.site_dir)
        if not updated.strip() or STAFF not in updated:
            raise RefreshError("Knowledge base is empty or missing staff clarifications")
        diff = "".join(difflib.unified_diff(original.splitlines(keepends=True), updated.splitlines(keepends=True),
                                          fromfile="knowledge-base.md (current)", tofile="knowledge-base.md (refreshed)"))
        print(diff or "No local text changes.", end="" if diff else "\n")
        for notice in notices:
            print("NOTICE: " + notice)
        if args.dry_run:
            print("Dry run complete: no API calls, credential reads or file writes.")
            return 0
        key = read_key(args.keys_file)
        publish(ElevenLabs(key), args.agent_id, updated, args.state_file)
        if updated != original:
            atomic_write(args.kb_file, updated)
        return 0
    except (RefreshError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run())
