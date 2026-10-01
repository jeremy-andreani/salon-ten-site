#!/usr/bin/env python3
"""Make a built copy of the site safe to publish as the staging preview."""

import argparse
from pathlib import Path
import re

NOINDEX = '<meta name="robots" content="noindex, nofollow">'
GTAG_LOADER = re.compile(
    r'<script[^>]*src="https://www\.googletagmanager\.com/gtag/js[^"]*"[^>]*>\s*</script>',
    re.IGNORECASE)
# The Meta snippet exits early when window.fbq already exists, so a stub keeps the pixel off.
TRACKING_OFF = ('<script>window.fbq=function(){};window._fbq=window.fbq;</script>')
HEAD = re.compile(r"<head[^>]*>", re.IGNORECASE)


def stage(site):
    pages = sorted(site.rglob("*.html"))
    if not pages:
        raise ValueError("No HTML pages found to stage")
    for page in pages:
        html = page.read_text(encoding="utf-8")
        html, removed = GTAG_LOADER.subn("", html)
        html, injected = HEAD.subn(lambda m: f"{m.group(0)}\n{NOINDEX}\n{TRACKING_OFF}", html, count=1)
        if injected != 1:
            raise ValueError(f"No <head> found in {page.relative_to(site)}")
        page.write_text(html, encoding="utf-8")
    (site / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if NOINDEX not in html or "googletagmanager.com/gtag/js" in html:
            raise ValueError(f"Staging check failed for {page.relative_to(site)}")
    print(f"Staged {len(pages)} pages: noindex added, tracking off, robots.txt disallows all.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="A directory produced by build_site.py")
    stage(parser.parse_args().site.resolve())
