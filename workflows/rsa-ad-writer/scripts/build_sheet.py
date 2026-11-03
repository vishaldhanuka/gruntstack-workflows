#!/usr/bin/env python3
"""
Turn checked RSA copy into files you can use:
  - an .xlsx review sheet (type, number, copy, characters, category, pin, notes)
  - a .csv you can paste or import into Google Ads Editor

Input is the same text file verify_chars.py reads. Each line can carry a
category after a dash and an optional pin in square brackets:

    H1: Emergency Plumber Austin (24) - Feature [pin: 1]
    D2: Licensed, insured and rated 4.9 by Austin homeowners. Book online. (71) - Proof

Run verify_chars.py first. This script refuses to build files from copy that
breaks Google's limits.

Usage:
    python build_sheet.py output.txt --campaign "Search - Plumbing" --ad-group "Emergency Plumber" \
        --final-url https://example.com/emergency --path1 emergency --path2 austin
    python build_sheet.py output.txt --out my-ads   # writes my-ads.xlsx and my-ads-editor.csv
"""

import argparse
import csv
import re
import sys

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

LIMITS = {"Headline": 30, "Description": 90}
LINE = re.compile(r"^\s*([HD])(\d+):\s*(.+)$", re.M)
PIN = re.compile(r"\[\s*pin\s*:?\s*(\d)\s*\]", re.I)
COUNT = re.compile(r"\s+\(\d+\)")
SPLIT = re.compile(r"\s+(?:[—–|]|-\s)\s*")


def parse(text: str):
    rows = []
    for kind, num, rest in LINE.findall(text):
        pin = None
        m = PIN.search(rest)
        if m:
            pin = int(m.group(1))
            rest = PIN.sub("", rest)
        parts = SPLIT.split(COUNT.sub("", rest).strip(), maxsplit=1)
        copy = parts[0].strip()
        category = parts[1].strip() if len(parts) > 1 else ""
        rows.append({
            "type": "Headline" if kind == "H" else "Description",
            "num": int(num),
            "copy": copy,
            "chars": len(copy),
            "category": category,
            "pin": pin,
        })
    return rows


def write_xlsx(rows, path):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        print("openpyxl isn't installed, so no .xlsx was written. Install it with: pip install openpyxl")
        return False
    wb = Workbook()
    ws = wb.active
    ws.title = "RSA"
    ws.append(["Asset type", "Number", "Copy", "Characters", "Category", "Pin", "Notes"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        limit = LIMITS[r["type"]]
        ws.append([
            r["type"], r["num"], r["copy"], r["chars"], r["category"],
            f"Position {r['pin']}" if r["pin"] else "None",
            f"{limit - r['chars']} characters to spare",
        ])
    for col, width in zip("ABCDEFG", (12, 8, 60, 11, 14, 12, 24)):
        ws.column_dimensions[col].width = width
    wb.save(path)
    return True


def write_editor_csv(rows, path, args):
    heads = sorted((r for r in rows if r["type"] == "Headline"), key=lambda r: r["num"])
    descs = sorted((r for r in rows if r["type"] == "Description"), key=lambda r: r["num"])
    header = ["Campaign", "Ad group", "Ad type", "Final URL", "Path 1", "Path 2"]
    values = [args.campaign, args.ad_group, "Responsive search ad", args.final_url, args.path1, args.path2]
    for i, h in enumerate(heads, 1):
        header += [f"Headline {i}", f"Headline {i} position"]
        values += [h["copy"], str(h["pin"]) if h["pin"] else ""]
    for i, d in enumerate(descs, 1):
        header += [f"Description {i}"]
        values += [d["copy"]]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(values)


def main() -> int:
    p = argparse.ArgumentParser(description="Build an .xlsx review sheet and a Google Ads Editor CSV from RSA copy.")
    p.add_argument("file", help="Text file with H1:-H15: and D1:-D4: lines")
    p.add_argument("--out", default="rsa", help="Output name without extension (default: rsa)")
    p.add_argument("--campaign", default="", help="Campaign name, exactly as it appears in Google Ads")
    p.add_argument("--ad-group", default="", help="Ad group name, exactly as it appears in Google Ads")
    p.add_argument("--final-url", default="", help="Landing page URL")
    p.add_argument("--path1", default="", help="Display path 1 (15 characters max)")
    p.add_argument("--path2", default="", help="Display path 2 (15 characters max)")
    args = p.parse_args()

    with open(args.file, encoding="utf-8") as f:
        rows = parse(f.read())

    problems = [f"{r['type']} {r['num']} is {r['chars']} characters (limit {LIMITS[r['type']]})"
                for r in rows if r["chars"] > LIMITS[r["type"]]]
    for name, val in (("--path1", args.path1), ("--path2", args.path2)):
        if len(val) > 15:
            problems.append(f"{name} is {len(val)} characters (limit 15)")
    if problems:
        print("Not building files. Fix these first (run verify_chars.py):")
        for x in problems:
            print("  - " + x)
        return 1

    xlsx_ok = write_xlsx(rows, f"{args.out}.xlsx")
    write_editor_csv(rows, f"{args.out}-editor.csv", args)
    if xlsx_ok:
        print(f"Wrote {args.out}.xlsx")
    print(f"Wrote {args.out}-editor.csv")
    if not (args.campaign and args.ad_group):
        print("Note: add --campaign and --ad-group before importing the CSV into Google Ads Editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
