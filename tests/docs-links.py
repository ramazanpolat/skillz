#!/usr/bin/env python3
"""Every relative link and anchor in the repo's markdown resolves.

Checks README.md, AGENTS.md, CHANGELOG.md, docs/ and examples/: a relative link
must point at an existing file or directory, and a #fragment at a heading in the
target file (GitHub's slug rules: lowercase, punctuation dropped, spaces -> -).
External links (a scheme, or mailto:) are not fetched.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def slug(heading):
    h = heading.strip().lower()
    h = re.sub(r"[`*_]", "", h)
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


def anchors(path):
    out, fence = set(), False
    counts = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
            if m:
                s = slug(m.group(1))
                n = counts.get(s, 0)
                out.add(s if n == 0 else f"{s}-{n}")
                counts[s] = n + 1
    return out


def files():
    for top in ("README.md", "AGENTS.md", "CHANGELOG.md"):
        p = os.path.join(ROOT, top)
        if os.path.exists(p):
            yield p
    for d in ("docs", "examples"):
        for dp, _, fns in os.walk(os.path.join(ROOT, d)):
            for fn in fns:
                if fn.endswith(".md"):
                    yield os.path.join(dp, fn)


def main():
    broken, n = [], 0
    for path in files():
        n += 1
        text = open(path, encoding="utf-8").read()
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for target in LINK.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target):
                continue
            ref, _, frag = target.partition("#")
            dest = os.path.normpath(os.path.join(os.path.dirname(path), ref)) if ref else path
            rel = os.path.relpath(path, ROOT)
            if not os.path.exists(dest):
                broken.append(f"{rel}: {target} (no such file)")
                continue
            if frag and os.path.isfile(dest) and dest.endswith(".md") and frag not in anchors(dest):
                broken.append(f"{rel}: {target} (no heading #{frag})")
    for b in broken:
        print("BROKEN", b)
    print(f"docs-links: {n} files, {len(broken)} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
