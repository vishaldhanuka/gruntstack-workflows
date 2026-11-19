---
name: youtube-outlier-finder
description: >
  Find YouTube videos that got far more views than their channel usually gets, work out why, and turn the pattern into titles or ad hooks for the user. Use when the user wants to know what's working on YouTube in a niche, research video topics, find breakout videos from competitors, or get hook ideas for YouTube or video ads. Trigger on "outlier videos", "what's working on YouTube", "viral videos in my niche", "video ideas", "competitor YouTube research", "YouTube hooks".
---

# YouTube outlier finder

Raw view counts mislead: big channels get big numbers every time. What's useful is a video that beat its own channel by a wide margin, because that means the topic or the hook did the work, not the subscriber count. This skill finds those videos, works out the pattern behind them, and turns it into ideas for the user.

The split of work: a script finds the videos and does the math. You judge why they worked and write the ideas.

Scripts live in `${CLAUDE_SKILL_DIR}/scripts/`. If that variable isn't set in your environment, use the `scripts/` folder next to this file.

---

## Step 1: Pin down the search

Ask only for what's missing:

1. **Topic or channels.** Search phrases ("google ads for dentists", "meal prep for beginners"), a list of competitor channels, or both.
2. **What the ideas are for.** **Titles** for the user's own channel (the default), or **hooks** for video ads (YouTube, Demand Gen, Shorts, Reels).
3. **Time window.** Default 90 days. Use 30 for fast-moving topics, 180 to 365 for slow ones.

Write 2 to 4 search phrases the way a viewer would type them, not industry jargon. One search page costs 100 of the free 10,000 daily quota units, so 4 phrases is cheap.

## Step 2: Find the outliers

The script needs a free YouTube Data API key in `YOUTUBE_API_KEY`. If it isn't set, tell the user how to get one: Google Cloud console, APIs & Services, enable "YouTube Data API v3", Credentials, Create API key. They set it themselves (`export YOUTUBE_API_KEY=...`). Never ask for the key in chat.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/find_outliers.py --query "phrase one" --query "phrase two" --days 90 --out outliers.csv
python ${CLAUDE_SKILL_DIR}/scripts/find_outliers.py --channel @competitor1 --channel @competitor2 --days 180 --out outliers.csv
```

**score** is the video's views divided by the median views of that channel's last 30 uploads. 2 means twice its usual, 10 means ten times. Shorts (60 seconds or less) are left out by default because their view counts don't compare with long videos; use `--shorts only` to study Shorts on their own.

If fewer than 5 outliers come back, rerun with `--order relevance` (search by view count favours big channels and hides small ones), more phrases, a longer `--days`, or `--min-score 1.5`. Tell the user what you changed.

## Step 3: Work out why each one won

Read the top 10 to 15 rows. For each, look at the title, the description and the numbers, and name the **pattern** in one line. Common ones:

- a specific number or result ("I spent $10,000 on...", "in 7 days")
- a mistake or warning ("Stop doing X", "The setting that wastes your budget")
- a comparison or verdict ("X vs Y, which is better")
- a timely event (a platform change, news)
- an outsider or beginner angle ("I tried X with zero experience")
- curiosity gap (says something happened, not what)

Watch the context columns before calling something a pattern:
- **median_from** under 10 means the channel has few uploads and its median is shaky.
- **age_days** under 7 means the video is new; its score may still be climbing.
- **A timely event** can't be copied later. Say so instead of turning it into a template.

If you can, open the top 3 videos' pages to check the thumbnail and the first 30 seconds. Say if you couldn't.

## Step 4: Write the ideas

For each video you chose, write `ideas.csv`:

```
video_id,pattern,idea_1,idea_2,idea_3
dQw4w9WgXcQ,Specific dollar result in a short time,...,...,...
```

- **Borrow the pattern, never the words.** An idea that reads like the source title is rejected by the script.
- **Fit the user's audience and offer.** A pattern that worked for a beginner audience may not work for theirs. Skip it rather than force it.
- **Titles:** 70 characters or less if you can (search cuts them off after that); YouTube's hard limit is 100.
- **Hooks:** the first spoken line or on-screen text of a video ad, under about 15 words, and only claims the user can back up.

Then build the sheet:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/build_sheet.py outliers.csv ideas.csv --out outliers-and-ideas
python ${CLAUDE_SKILL_DIR}/scripts/build_sheet.py outliers.csv ideas.csv --out outliers-and-ideas --mode hooks
```

If it reports errors, fix `ideas.csv` and run it again.

## Rules

- **Numbers come from the script.** Don't recalculate or round scores yourself.
- **One video is a hint, three is a pattern.** Say when a pattern rests on a single video.
- **Views aren't sales.** An outlier shows attention, not that it sold anything. Say this once when the ideas are ad hooks.
- **Don't make up why a video won.** If the title and description don't explain it, write "unclear from the title" rather than guess.

## Output

In chat: the search you ran, how many videos were checked and how many cleared the bar, the top patterns (with how many videos show each one), then your best 5 ideas. Give the user `outliers-and-ideas.xlsx`.
