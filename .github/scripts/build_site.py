#!/usr/bin/env python3
"""Stage only tracked public site files and reject broken local links before FTP."""

import argparse
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit


SITE_DIRECTORIES = {
    "img",
    "comprehensive-skin-assessment",
    "relaxing-facials",
    "skin-microneedling",
    "specialised-facial-treatments",
}
PUBLIC_SUFFIXES = {
    ".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".avif", ".svg", ".ico", ".woff", ".woff2",
}
PROTECTED = {"old-wordpress", "cgi-bin", ".well-known", "new-site-test"}
REQUIRED = {
    ".htaccess", "index.html", "style.css", "nav.js", "conversion.js",
    *(f"{name}/index.html" for name in SITE_DIRECTORIES if name != "img"),
}


def is_public(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or set(path.parts) & PROTECTED:
        return False
    if name == ".htaccess":
        return True
    if any(part.startswith(".") for part in path.parts):
        return False
    return path.suffix.lower() in PUBLIC_SUFFIXES and (
        len(path.parts) == 1 or path.parts[0] in SITE_DIRECTORIES
    )


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(value for key, value in attrs
                            if key in {"href", "src"} and value)


def check_links(site):
    checked = 0
    for file in sorted(site.rglob("*")):
        if file.suffix == ".html":
            parser = Links()
            parser.feed(file.read_text(encoding="utf-8"))
            targets = parser.targets
        elif file.suffix == ".css":
            targets = re.findall(r"url\(\s*['\"]?([^)'\"\s]+)",
                                 file.read_text(encoding="utf-8"))
        else:
            continue
        for target in targets:
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            decoded = unquote(url.path)
            resolved = ((site / decoded.lstrip("/")) if decoded.startswith("/")
                        else (file.parent / decoded)).resolve()
            if resolved.is_dir():
                resolved /= "index.html"
            if not resolved.is_relative_to(site) or not resolved.is_file():
                raise ValueError(f"Broken local link: {file.relative_to(site)} -> {target}")
            checked += 1
    return checked


def build(repo, destination):
    names = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=repo
    ).decode("utf-8").split("\0")
    selected = {name for name in names if name and is_public(name)}
    missing = REQUIRED - selected
    if missing:
        raise ValueError(f"Required website files missing from git: {sorted(missing)}")
    destination = destination.resolve()
    # Refuse to reuse a directory; stale files must never leak into an upload.
    destination.mkdir(parents=True, exist_ok=False)
    for name in sorted(selected):
        source = repo / name
        if any(part.is_symlink() for part in (source, *source.parents)):
            raise ValueError(f"Symlinks cannot be published: {name}")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    checked = check_links(destination)
    print(f"Built {len(selected)} public files; checked {checked} local links.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="A new, empty output directory")
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[2], args.destination)
