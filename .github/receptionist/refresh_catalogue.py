#!/usr/bin/env python3
"""Regenerate functions/kitomba-services.generated.json from Salon Ten's public Kitomba catalogue.

Read-only: GETs the same public endpoints the online-booking app loads (service list and
categories for "salonten"). Never logs in, never touches availability or bookings. The result is
the full bookable service list (id, caller-facing label, category, price) that
send-booking-link.js uses to pre-select any treatment, and to prefer a combined service (e.g.
Brow Shape, Brow Tint, Lash Tint) when a caller's items match one. Deploy with
deploy-functions.py afterwards.

  python3 refresh_catalogue.py            write the file if the catalogue changed
  python3 refresh_catalogue.py --dry-run  print the catalogue; no writes
"""
import argparse, json, os, re, sys, tempfile, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "functions" / "kitomba-services.generated.json"
API = "https://apps.kitomba.com/api/public/"
BUSINESS = "salonten"


def fetch(path):
    req = urllib.request.Request(API + path, headers={"Accept": "application/json", "User-Agent": "salon-ten-anne-catalogue"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def label(name):
    """Caller-facing label: drop the menu ordering prefix ("2. ") and turn "Waxing - Brazilian"
    into "Brazilian Wax" so the SMS reads naturally."""
    text = re.sub(r"\s+", " ", re.sub(r"^\s*\d+\.\s*", "", name)).strip()
    waxing = re.match(r"^Waxing\s*-\s*(.+)$", text, re.I)
    if waxing:
        area = waxing.group(1).strip()
        if not re.search(r"\bwax", area, re.I):
            head, paren, tail = area.partition(" (")
            area = f"{head} Wax" + (paren + tail if paren else "")
        text = area
    return text


def build(services, categories):
    names = {c["id"]: label(c["name"]) for c in categories}
    rows = [{"id": str(s["id"]), "name": s["name"].strip(), "label": label(s["name"]),
             "category": names.get(s.get("categoryId"), ""), "price": s.get("price")}
            for s in services if s.get("visible") and re.fullmatch(r"\d+", str(s.get("id", "")))]
    if len(rows) < 20:
        raise SystemExit(f"Only {len(rows)} visible services returned; refusing to write a partial catalogue")
    rows.sort(key=lambda r: (r["category"], r["name"]))
    return {"generated_from": f"{API}service/{BUSINESS} (public online-booking catalogue; see refresh_catalogue.py)",
            "booking_base": f"https://apps.kitomba.com/bookings/{BUSINESS}", "services": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    data = build(fetch(f"service/{BUSINESS}"), fetch(f"category/{BUSINESS}"))
    text = json.dumps(data, indent=2) + "\n"
    changed = not OUT.exists() or OUT.read_text(encoding="utf-8") != text
    print(f"Kitomba catalogue: {len(data['services'])} visible services, {'changed' if changed else 'unchanged'}.")
    if args.dry_run:
        for row in data["services"]:
            print(f"  {row['id']:>20}  {row['category'][:28]:28}  {row['label']}")
    elif changed:
        fd, tmp = tempfile.mkstemp(dir=OUT.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
