#!/usr/bin/env python3
"""
Pull the public comments from YouTube videos into one CSV, ready to read.

Point it at videos (yours or a competitor's), or at a channel and it takes the
latest uploads. It keeps the comment text, likes and reply count. It does not
keep commenter names: you need the question, not the person.

It also marks each comment with a rough signal so the AI can read the useful
ones first:
  question  - asks something ("how do I...", "does it...", ends with ?)
  request   - asks for something ("can you do a video on...", "please make...")
  (blank)   - everything else, which may still matter

Needs a YouTube Data API key in the YOUTUBE_API_KEY environment variable. It's
free: Google Cloud console > APIs & Services > enable "YouTube Data API v3" >
Credentials > Create API key. Reading comments costs 1 unit per 100 comments
against a free 10,000 units a day, so quota is rarely the limit.

Usage:
    python fetch_comments.py --video https://youtu.be/VIDEO_ID --video OTHER_ID
    python fetch_comments.py --channel @somechannel --latest 10
    python fetch_comments.py --channel @somechannel --latest 5 --max-per-video 300 --out comments.csv

Python 3.9+ and nothing else to install.
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

API = "https://www.googleapis.com/youtube/v3/"

QUESTION_START = re.compile(
    r"^(how|what|why|when|where|which|who|can|could|does|do|did|is|are|will|would|should|any|anyone)\b",
    re.I,
)
REQUEST = re.compile(
    r"(video on|video about|tutorial on|please (make|do|cover|show)|can you (make|do|cover|show)|"
    r"could you (make|do|cover|show)|would love (a|to see)|next video|part 2|deep dive|walk ?through)",
    re.I,
)


class ApiError(Exception):
    pass


def api_get(endpoint, params, key):
    """One GET to the YouTube Data API. Returns the parsed JSON."""
    query = urllib.parse.urlencode({**params, "key": key})
    try:
        with urllib.request.urlopen(f"{API}{endpoint}?{query}", timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e)["error"]
            reason = (err.get("errors") or [{}])[0].get("reason", "")
            raise ApiError(f"{e.code} {reason}: {err.get('message', '')}".strip()) from None
        except (ValueError, KeyError):
            raise ApiError(f"HTTP {e.code} from YouTube") from None


def video_id(text):
    """Accept a bare id or any common YouTube URL."""
    text = text.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", text)
    if not m:
        raise SystemExit(f"Can't find a video id in: {text}")
    return m.group(1)


def channel_uploads(channel, key):
    """Return (channel title, uploads playlist id) for an @handle, channel URL or UC id."""
    channel = channel.strip().rstrip("/")
    m = re.search(r"youtube\.com/(@[^/?]+|channel/(UC[\w-]+))", channel)
    if m:
        channel = m.group(2) or m.group(1)
    params = {"part": "snippet,contentDetails"}
    if channel.startswith("UC"):
        params["id"] = channel
    else:
        params["forHandle"] = channel if channel.startswith("@") else "@" + channel
    items = api_get("channels", params, key).get("items", [])
    if not items:
        raise SystemExit(f"No channel found for {channel}. Use the @handle from the channel page.")
    c = items[0]
    return c["snippet"]["title"], c["contentDetails"]["relatedPlaylists"]["uploads"]


def latest_videos(playlist, n, key):
    ids, token = [], None
    while len(ids) < n:
        params = {"part": "contentDetails", "playlistId": playlist, "maxResults": min(50, n - len(ids))}
        if token:
            params["pageToken"] = token
        data = api_get("playlistItems", params, key)
        ids += [i["contentDetails"]["videoId"] for i in data.get("items", [])]
        token = data.get("nextPageToken")
        if not token:
            break
    return ids[:n]


def video_titles(ids, key):
    titles = {}
    for start in range(0, len(ids), 50):
        data = api_get("videos", {"part": "snippet", "id": ",".join(ids[start:start + 50])}, key)
        for v in data.get("items", []):
            titles[v["id"]] = v["snippet"]["title"]
    return titles


def signal(text):
    first = text.strip().split("\n", 1)[0]
    if REQUEST.search(text):
        return "request"
    if "?" in text or QUESTION_START.match(first):
        return "question"
    return ""


def comments_for(vid, limit, order, key):
    rows, token = [], None
    while len(rows) < limit:
        params = {
            "part": "snippet",
            "videoId": vid,
            "maxResults": 100,
            "order": order,
            "textFormat": "plainText",
        }
        if token:
            params["pageToken"] = token
        data = api_get("commentThreads", params, key)
        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]
            s = top["snippet"]
            text = (s.get("textDisplay") or s.get("textOriginal") or "").strip()
            if not text:
                continue
            rows.append({
                "comment_id": top["id"],
                "video_id": vid,
                "published": s.get("publishedAt", "")[:10],
                "likes": int(s.get("likeCount", 0)),
                "replies": int(item["snippet"].get("totalReplyCount", 0)),
                "signal": signal(text),
                "text": " ".join(text.split()),
            })
        token = data.get("nextPageToken")
        if not token:
            break
    return rows[:limit]


def main():
    ap = argparse.ArgumentParser(description="Pull YouTube comments into a CSV.")
    ap.add_argument("--video", action="append", default=[], help="video URL or id (repeat for more)")
    ap.add_argument("--channel", help="@handle, channel URL or UC... id; takes its latest uploads")
    ap.add_argument("--latest", type=int, default=10, help="how many recent uploads to read (default 10)")
    ap.add_argument("--max-per-video", type=int, default=500, help="comment cap per video (default 500)")
    ap.add_argument("--order", choices=["relevance", "time"], default="relevance",
                    help="relevance = YouTube's top comments first (default); time = newest first")
    ap.add_argument("--out", default="comments.csv")
    args = ap.parse_args()

    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set YOUTUBE_API_KEY first. See the top of this file for how to get one (free).")
    if not args.video and not args.channel:
        raise SystemExit("Give at least one --video or a --channel.")

    ids = [video_id(v) for v in args.video]
    if args.channel:
        title, playlist = channel_uploads(args.channel, key)
        found = latest_videos(playlist, args.latest, key)
        print(f"Channel: {title}, reading its latest {len(found)} uploads")
        ids += found
    ids = list(dict.fromkeys(ids))
    titles = video_titles(ids, key)

    rows, skipped = [], []
    for vid in ids:
        if vid not in titles:
            skipped.append(f"{vid} (not found or private)")
            continue
        try:
            got = comments_for(vid, args.max_per_video, args.order, key)
        except ApiError as e:
            if "commentsDisabled" in str(e):
                skipped.append(f"{vid} (comments turned off)")
                continue
            if "quotaExceeded" in str(e):
                print(f"Quota ran out at video {vid}. The file holds what was read so far.", file=sys.stderr)
                skipped.append(f"{vid} and later (quota)")
                break
            raise SystemExit(f"YouTube refused the request for {vid}: {e}")
        for r in got:
            r["video_title"] = titles[vid]
        rows += got
        print(f"  {len(got):>4} comments  {titles[vid][:70]}")

    fields = ["comment_id", "video_id", "video_title", "published", "likes", "replies", "signal", "text"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    n_q = sum(r["signal"] == "question" for r in rows)
    n_r = sum(r["signal"] == "request" for r in rows)
    print(f"\nSaved {len(rows)} comments from {len(ids) - len(skipped)} videos to {args.out}")
    print(f"Marked {n_q} as questions and {n_r} as requests. The marks are rough; read the rest too.")
    if skipped:
        print("Skipped: " + "; ".join(skipped))
    if not rows:
        sys.exit(1)


if __name__ == "__main__":
    main()
