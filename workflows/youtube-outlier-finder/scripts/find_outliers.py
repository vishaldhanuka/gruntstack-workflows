#!/usr/bin/env python3
"""
Find YouTube videos that did far better than their own channel usually does.

A video with 2 million views on a channel that gets 2 million every time tells
you nothing. A video with 80,000 views on a channel that usually gets 4,000
tells you the topic or the hook hit a nerve. This script finds the second kind.

  outlier score = the video's views / the median views of the channel's
                  recent uploads

The median, not the average, so one old viral hit doesn't make every other
video look small.

Two ways to pick the videos to check:
  --query    search YouTube for recent videos on a topic (costs 100 quota units
             per search page)
  --channel  check the recent uploads of channels you name, such as your
             competitors (costs about 3 units per channel)

Needs a YouTube Data API key in YOUTUBE_API_KEY. It's free: Google Cloud console
> APIs & Services > enable "YouTube Data API v3" > Credentials > Create API key.
The free quota is 10,000 units a day, so about 80 search pages.

Usage:
    python find_outliers.py --query "google ads tutorial" --query "ppc tips" --days 90
    python find_outliers.py --channel @competitor1 --channel @competitor2 --days 180
    python find_outliers.py --query "meal prep" --days 30 --min-score 3 --out outliers.csv

Writes outliers.csv, best first. Python 3.9+ and nothing else to install.
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

API = "https://www.googleapis.com/youtube/v3/"
SHORT_SECONDS = 60
quota_used = 0


class ApiError(Exception):
    pass


def api_get(endpoint, params, key, cost=1):
    global quota_used
    quota_used += cost
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


def seconds(iso):
    """ISO 8601 duration (PT1H2M3S) to seconds."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def parse_time(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def search(query, after, pages, key, region=None, lang=None, order="viewCount"):
    ids, token = [], None
    for _ in range(pages):
        params = {"part": "id", "q": query, "type": "video", "maxResults": 50,
                  "order": order, "publishedAfter": after}
        if region:
            params["regionCode"] = region
        if lang:
            params["relevanceLanguage"] = lang
        if token:
            params["pageToken"] = token
        data = api_get("search", params, key, cost=100)
        ids += [i["id"]["videoId"] for i in data.get("items", []) if i.get("id", {}).get("videoId")]
        token = data.get("nextPageToken")
        if not token:
            break
    return ids


def resolve_channel(channel, key):
    channel = channel.strip().rstrip("/")
    m = re.search(r"youtube\.com/(@[^/?]+|channel/(UC[\w-]+))", channel)
    if m:
        channel = m.group(2) or m.group(1)
    params = {"part": "snippet,contentDetails,statistics"}
    if channel.startswith("UC"):
        params["id"] = channel
    else:
        params["forHandle"] = channel if channel.startswith("@") else "@" + channel
    items = api_get("channels", params, key).get("items", [])
    if not items:
        raise SystemExit(f"No channel found for {channel}. Use the @handle from the channel page.")
    return items[0]


def channels(ids, key):
    out = {}
    for start in range(0, len(ids), 50):
        data = api_get("channels", {"part": "snippet,contentDetails,statistics",
                                    "id": ",".join(ids[start:start + 50])}, key)
        for c in data.get("items", []):
            out[c["id"]] = c
    return out


def uploads(playlist, n, key):
    ids, token = [], None
    while len(ids) < n:
        params = {"part": "contentDetails", "playlistId": playlist, "maxResults": min(50, n - len(ids))}
        if token:
            params["pageToken"] = token
        try:
            data = api_get("playlistItems", params, key)
        except ApiError as e:
            if "playlistNotFound" in str(e):
                return ids
            raise
        ids += [i["contentDetails"]["videoId"] for i in data.get("items", [])]
        token = data.get("nextPageToken")
        if not token:
            break
    return ids[:n]


def videos(ids, key):
    out = {}
    ids = list(dict.fromkeys(ids))
    for start in range(0, len(ids), 50):
        data = api_get("videos", {"part": "snippet,statistics,contentDetails",
                                  "id": ",".join(ids[start:start + 50])}, key)
        for v in data.get("items", []):
            st = v.get("statistics", {})
            out[v["id"]] = {
                "video_id": v["id"],
                "title": v["snippet"]["title"],
                "description": " ".join((v["snippet"].get("description") or "").split())[:300],
                "channel_id": v["snippet"]["channelId"],
                "channel": v["snippet"]["channelTitle"],
                "published": v["snippet"]["publishedAt"],
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)) if "likeCount" in st else "",
                "comments": int(st.get("commentCount", 0)) if "commentCount" in st else "",
                "seconds": seconds(v["contentDetails"].get("duration")),
                "live": v["snippet"].get("liveBroadcastContent", "none") != "none",
            }
    return out


def keep(v, shorts):
    is_short = 0 < v["seconds"] <= SHORT_SECONDS
    if v["live"]:
        return False
    return {"exclude": not is_short, "only": is_short, "include": True}[shorts]


def main():
    ap = argparse.ArgumentParser(description="Find videos that beat their channel's usual views.")
    ap.add_argument("--query", action="append", default=[], help="search phrase (repeat for more)")
    ap.add_argument("--channel", action="append", default=[], help="@handle, channel URL or UC id (repeat)")
    ap.add_argument("--days", type=int, default=90, help="only videos published in the last N days (default 90)")
    ap.add_argument("--pages", type=int, default=1, help="search pages of 50 per query (default 1, 100 units each)")
    ap.add_argument("--baseline", type=int, default=30, help="recent uploads used for the channel median (default 30)")
    ap.add_argument("--min-score", type=float, default=2.0, help="keep videos at least this many times the median (default 2)")
    ap.add_argument("--min-views", type=int, default=1000, help="ignore videos under this many views (default 1000)")
    ap.add_argument("--shorts", choices=["exclude", "only", "include"], default="exclude",
                    help="Shorts (60 s or less) get very different views; kept apart by default")
    ap.add_argument("--order", choices=["viewCount", "relevance", "date"], default="viewCount",
                    help="how search ranks results; viewCount (default) favours big channels, "
                         "relevance and date surface more small ones")
    ap.add_argument("--region", help="two-letter country for search, e.g. US")
    ap.add_argument("--lang", help="two-letter language for search, e.g. en")
    ap.add_argument("--out", default="outliers.csv")
    args = ap.parse_args()

    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set YOUTUBE_API_KEY first. See the top of this file for how to get one (free).")
    if not args.query and not args.channel:
        raise SystemExit("Give at least one --query or --channel.")

    now = datetime.now(timezone.utc)
    after = now - timedelta(days=args.days)
    after_iso = after.strftime("%Y-%m-%dT%H:%M:%SZ")

    candidates = []
    try:
        for q in args.query:
            found = search(q, after_iso, args.pages, key, args.region, args.lang, args.order)
            print(f"Search '{q}': {len(found)} videos")
            candidates += found
        named = {}
        for ch in args.channel:
            c = resolve_channel(ch, key)
            named[c["id"]] = c
            found = uploads(c["contentDetails"]["relatedPlaylists"]["uploads"], 50, key)
            print(f"Channel {c['snippet']['title']}: {len(found)} recent uploads")
            candidates += found

        vids = videos(candidates, key)
        vids = {i: v for i, v in vids.items() if parse_time(v["published"]) >= after and keep(v, args.shorts)}

        chan_ids = sorted({v["channel_id"] for v in vids.values()})
        info = {**channels([c for c in chan_ids if c not in named], key), **named}
        medians, sample = {}, {}
        for cid in chan_ids:
            c = info.get(cid)
            if not c:
                continue
            recent = uploads(c["contentDetails"]["relatedPlaylists"]["uploads"], args.baseline, key)
            base = [v for v in videos(recent, key).values() if keep(v, args.shorts)]
            sample[cid] = len(base)
            if base:
                medians[cid] = statistics.median(v["views"] for v in base)
    except ApiError as e:
        if "quotaExceeded" in str(e):
            raise SystemExit("YouTube quota for today is used up. It resets at midnight Pacific time.")
        raise SystemExit(f"YouTube refused the request: {e}")

    rows = []
    for v in vids.values():
        med = medians.get(v["channel_id"])
        if not med or v["views"] < args.min_views:
            continue
        score = v["views"] / med
        if score < args.min_score:
            continue
        age = max((now - parse_time(v["published"])).total_seconds() / 86400, 0.5)
        stats = info[v["channel_id"]].get("statistics", {})
        rows.append({
            "score": round(score, 1),
            "views": v["views"],
            "channel_median": int(med),
            "median_from": sample[v["channel_id"]],
            "views_per_day": int(v["views"] / age),
            "age_days": int(age),
            "title": v["title"],
            "channel": v["channel"],
            "subscribers": "" if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0)),
            "minutes": round(v["seconds"] / 60, 1),
            "likes": v["likes"],
            "comments": v["comments"],
            "published": v["published"][:10],
            "url": f"https://www.youtube.com/watch?v={v['video_id']}",
            "video_id": v["video_id"],
            "channel_id": v["channel_id"],
            "description": v["description"],
        })
    rows.sort(key=lambda r: (r["score"], r["views"]), reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    fields = ["rank", "score", "views", "channel_median", "median_from", "views_per_day", "age_days", "title",
              "channel", "subscribers", "minutes", "likes", "comments", "published", "url", "video_id",
              "channel_id", "description"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    thin = sum(1 for r in rows if r["median_from"] < 10)
    print(f"\nChecked {len(vids)} videos from {len(chan_ids)} channels. "
          f"{len(rows)} scored {args.min_score}x or more. Quota used: about {quota_used} units.")
    for r in rows[:10]:
        print(f"  {r['score']:>6}x  {r['views']:>10,} views  {r['title'][:60]}  ({r['channel']})")
    if thin:
        print(f"{thin} of these come from channels with fewer than 10 recent uploads, so their median is shaky. "
              "See the median_from column.")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
