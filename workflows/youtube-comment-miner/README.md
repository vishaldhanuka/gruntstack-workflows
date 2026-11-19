# YouTube comment miner

Point it at your own YouTube channel or a competitor's, and it tells you what people keep asking, requesting and objecting to, ranked by how many raised or liked it, with their own words as proof. Then it turns the top themes into ad angles, landing page FAQs or video topics.

## What's in this folder

| File | What it does |
|---|---|
| `SKILL.md` | The instructions the AI follows: pull comments, tag them into themes, rank, write the ideas. |
| `scripts/fetch_comments.py` | Pulls the comments from videos or a channel's latest uploads into `comments.csv`. Keeps no commenter names. |
| `scripts/rank_themes.py` | Counts the AI's themes, ranks them by votes (comments plus likes) and builds `themes.xlsx`. Refuses tags for comments that don't exist. |
| `evals/evals.json` | Test prompts for checking the skill still works after you change it. |

## Before you start: a YouTube API key

The scripts read public comments through the YouTube Data API. The key is free:

1. Open the [Google Cloud console](https://console.cloud.google.com/) and create a project (any name).
2. APIs & Services → Library → enable **YouTube Data API v3**.
3. APIs & Services → Credentials → Create credentials → API key.
4. Set it where you run the scripts: `export YOUTUBE_API_KEY=your-key` (Mac or Linux) or `set YOUTUBE_API_KEY=your-key` (Windows).

Reading comments costs 1 unit per 100 comments, against 10,000 free units a day.

## Use it

**Claude Code:** copy this folder to `.claude/skills/youtube-comment-miner/` in your project (or `~/.claude/skills/` to use it everywhere). Then ask: "Mine the comments on @competitor's last 10 videos for ad angles."

**Other AI agents:** give the agent `SKILL.md` as its instructions and let it run the two scripts.

The scripts need Python 3.9+ and nothing else. The `.xlsx` needs `openpyxl` (`pip install openpyxl`); without it you still get the CSV.

## Run the scripts yourself

```bash
python scripts/fetch_comments.py --channel @somechannel --latest 10 --out comments.csv
# tag the comments into themes in tags.csv (comment_id,theme,type), then:
python scripts/rank_themes.py comments.csv tags.csv --out themes
```

## Limits

- It reads public comments only, and only top-level comments, not replies.
- Comments come from people who watch and comment, which leans towards fans, beginners and the annoyed. Treat it as a strong hint, not a survey.
- A video with comments turned off is skipped, and the script says so.
- Grouping comments into themes is a judgment call. The counts are exact; what goes in which theme is the AI's reading, and you can see every comment behind every theme in the sheet.

## Found a problem?

Open an issue in this repo and tell me what you ran and what happened.
