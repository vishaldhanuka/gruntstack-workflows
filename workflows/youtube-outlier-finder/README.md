# YouTube outlier finder

Finds YouTube videos that got far more views than their channel usually gets, then works out the pattern behind them and turns it into titles for your channel or hooks for your video ads.

A video with 2 million views on a channel that always gets 2 million tells you nothing. A video with 80,000 views on a channel that usually gets 4,000 tells you the topic or the hook did the work. That's what this looks for.

## What's in this folder

| File | What it does |
|---|---|
| `SKILL.md` | The instructions the AI follows: set the search, find outliers, name the pattern, write ideas. |
| `scripts/find_outliers.py` | Searches a topic or checks named channels, and scores each video against its channel's median views. Writes `outliers.csv`. |
| `scripts/build_sheet.py` | Checks the AI's ideas (title length, no copying the source title) and merges them with the outliers into one `.xlsx`. |
| `evals/evals.json` | Test prompts for checking the skill still works after you change it. |

## How the score works

**score = the video's views ÷ the median views of the channel's last 30 uploads.**

The median rather than the average, so one old viral hit doesn't make everything else look small. Shorts (60 seconds or less) are kept apart by default because their view counts don't compare with long videos.

## Before you start: a YouTube API key

The key is free:

1. Open the [Google Cloud console](https://console.cloud.google.com/) and create a project (any name).
2. APIs & Services → Library → enable **YouTube Data API v3**.
3. APIs & Services → Credentials → Create credentials → API key.
4. Set it where you run the scripts: `export YOUTUBE_API_KEY=your-key` (Mac or Linux) or `set YOUTUBE_API_KEY=your-key` (Windows).

A search page costs 100 of your 10,000 free daily units; checking a channel costs about 3. A normal run of 3 or 4 searches uses under 500.

## Use it

**Claude Code:** copy this folder to `.claude/skills/youtube-outlier-finder/` in your project (or `~/.claude/skills/` to use it everywhere). Then ask: "Find outlier videos about Google Ads for local businesses from the last 90 days and give me hooks for a YouTube ad."

**Other AI agents:** give the agent `SKILL.md` as its instructions and let it run the two scripts.

The scripts need Python 3.9+ and nothing else. The `.xlsx` needs `openpyxl` (`pip install openpyxl`); without it you still get the CSV.

## Run the scripts yourself

```bash
python scripts/find_outliers.py --query "google ads for dentists" --days 90 --out outliers.csv
python scripts/find_outliers.py --channel @competitor1 --channel @competitor2 --days 180 --out outliers.csv
# write ideas.csv (video_id,pattern,idea_1,idea_2,idea_3), then:
python scripts/build_sheet.py outliers.csv ideas.csv --out outliers-and-ideas
```

Useful flags: `--min-score` (default 2), `--min-views` (default 1,000), `--order relevance` to surface smaller channels, `--shorts only` to study Shorts.

## Limits

- Views show attention, not sales. An outlier tells you what people clicked, not what they bought.
- It reads titles, descriptions and numbers. It doesn't watch the video or read the thumbnail, so the AI says when it couldn't check them.
- A new video's score is still climbing, and a channel with few uploads has a shaky median. Both are columns in the sheet.
- YouTube search returns at most a few hundred results per phrase, so this is a sample of the niche, not all of it.

## Found a problem?

Open an issue in this repo and tell me what you ran and what happened.
