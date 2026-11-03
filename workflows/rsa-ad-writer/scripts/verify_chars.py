#!/usr/bin/env python3
"""
Check Google Ads responsive search ad (RSA) copy before you upload it.

Reads a text file with lines like:
    H1: Emergency Plumber Austin (24) - Feature
    D1: Burst pipe? We arrive in 60 minutes or less, day or night. Call now. (69) - Offer

and checks:
  - every headline is 30 characters or less, every description 90 or less
  - there are exactly 15 headlines and 4 descriptions
  - no two headlines share more than 60% of their words (near-duplicates)
  - optionally, that a keyword appears in at least 2 headlines (--keyword)

Exits with code 1 if anything fails, so an agent can't call the copy "verified"
unless this script passed.

Usage:
    python verify_chars.py output.txt
    python verify_chars.py output.txt --keyword "emergency plumber"
    cat output.txt | python verify_chars.py
"""

import argparse
import re
import sys

HEADLINE_LIMIT = 30
DESC_LIMIT = 90
HEADLINES_NEEDED = 15
DESCRIPTIONS_NEEDED = 4
OVERLAP_LIMIT = 0.6

# Windows consoles default to a legacy code page; force UTF-8 so the output never crashes.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Text after the copy: "(24)", "— Feature", "- Feature", "| Feature".
TRAILER = re.compile(r"\s+(?:\(\d+\)|[—–|]|-\s).*$")


def clean(raw: str) -> str:
    return TRAILER.sub("", raw).strip()


def extract_assets(text: str):
    headlines, descriptions = {}, {}
    for m in re.finditer(r"^\s*H(\d+):\s*(.+)$", text, re.M):
        headlines[int(m.group(1))] = clean(m.group(2))
    for m in re.finditer(r"^\s*D(\d+):\s*(.+)$", text, re.M):
        descriptions[int(m.group(1))] = clean(m.group(2))
    return headlines, descriptions


def near_duplicates(headlines):
    issues = []
    items = sorted(headlines.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (n1, h1), (n2, h2) = items[i], items[j]
            w1, w2 = set(h1.lower().split()), set(h2.lower().split())
            if not w1 or not w2:
                continue
            overlap = len(w1 & w2) / min(len(w1), len(w2))
            if overlap > OVERLAP_LIMIT:
                issues.append(f"H{n1} and H{n2} share {round(overlap * 100)}% of their words: '{h1}' / '{h2}'")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check RSA headlines and descriptions.")
    parser.add_argument("file", nargs="?", help="Text file with H1:-H15: and D1:-D4: lines (default: stdin)")
    parser.add_argument("--keyword", help="Keyword that should appear in at least 2 headlines")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    headlines, descriptions = extract_assets(text)
    failures, warnings = [], []

    print("\n" + "=" * 56)
    print("RSA CHECK")
    print("=" * 56)

    print(f"\nHeadlines: {len(headlines)} found, need {HEADLINES_NEEDED}")
    for n in sorted(headlines):
        h = headlines[n]
        ok = len(h) <= HEADLINE_LIMIT
        print(f"  H{n:<2} {len(h):>2} chars  {'ok  ' if ok else 'OVER'}  {h}")
        if not ok:
            failures.append(f"H{n} is {len(h)} characters (limit {HEADLINE_LIMIT}): '{h}'")

    print(f"\nDescriptions: {len(descriptions)} found, need {DESCRIPTIONS_NEEDED}")
    for n in sorted(descriptions):
        d = descriptions[n]
        ok = len(d) <= DESC_LIMIT
        print(f"  D{n:<2} {len(d):>2} chars  {'ok  ' if ok else 'OVER'}  {d}")
        if not ok:
            failures.append(f"D{n} is {len(d)} characters (limit {DESC_LIMIT}): '{d}'")

    if len(headlines) != HEADLINES_NEEDED:
        failures.append(f"Found {len(headlines)} headlines, need exactly {HEADLINES_NEEDED}")
    if len(descriptions) != DESCRIPTIONS_NEEDED:
        failures.append(f"Found {len(descriptions)} descriptions, need exactly {DESCRIPTIONS_NEEDED}")

    exact = {}
    for n, h in headlines.items():
        exact.setdefault(h.lower(), []).append(n)
    for h, nums in exact.items():
        if len(nums) > 1:
            failures.append("Identical headlines: " + ", ".join(f"H{n}" for n in sorted(nums)))

    if args.keyword:
        kw = args.keyword.lower()
        hits = [n for n, h in headlines.items() if kw in h.lower()]
        if len(hits) < 2:
            failures.append(f"Keyword '{args.keyword}' is in {len(hits)} headline(s), need at least 2")

    warnings.extend(near_duplicates(headlines))
    if warnings:
        print("\nNear-duplicates (review these):")
        for w in warnings:
            print("  " + w)

    print("\n" + "=" * 56)
    if failures:
        print(f"FAILED: {len(failures)} problem(s)")
        for f in failures:
            print("  - " + f)
        print("\nFix these before uploading to Google Ads.")
        print("=" * 56 + "\n")
        return 1
    print("PASSED: counts and character limits are all fine.")
    if warnings:
        print(f"  {len(warnings)} near-duplicate warning(s) above. Rewrite one of each pair if they say the same thing.")
    print("=" * 56 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
