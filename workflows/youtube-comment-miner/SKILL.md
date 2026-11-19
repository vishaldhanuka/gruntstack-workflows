---
name: youtube-comment-miner
description: >
  Turn YouTube comments into ranked themes: the questions, requests and objections people raise most, with real quotes, then into ad angles, landing page FAQs or video topics. Use when the user wants to mine comments on their own or a competitor's YouTube videos, do voice-of-customer research from YouTube, find what an audience keeps asking, or get content or ad ideas from comments. Trigger on "YouTube comments", "what are people asking", "comment research", "voice of customer", "video ideas from comments", or a YouTube channel or video link with a research ask.
---

# YouTube comment miner

People tell you in YouTube comments what they want, what confuses them and what stops them buying. This skill pulls those comments, groups them into themes, ranks the themes by how many people raised or liked them, and turns the top ones into something the user can use.

The split of work: a script pulls the comments and does every count. You read the comments and decide what they mean.

Scripts live in `${CLAUDE_SKILL_DIR}/scripts/`. If that variable isn't set in your environment, use the `scripts/` folder next to this file.

---

## Step 1: Ask what it's for, and whose videos

You need two answers. Don't ask for anything the user already gave you.

1. **Whose videos.** Their own channel, a competitor's channel, or specific videos. A channel `@handle` or a video link is enough.
2. **What they want out of it.** One of:
   - **Ad research:** angles, objections to answer, and the customer's own words for ad copy and landing pages. Best on competitor or category videos.
   - **Video topics:** the next videos to make. Best on the user's own channel and close competitors.
   - **FAQ and product gaps:** questions the website or product doesn't answer yet.

If they don't say, assume ad research for a competitor's channel and video topics for their own, and say which you assumed.

## Step 2: Pull the comments

The script needs a free YouTube Data API key in `YOUTUBE_API_KEY`. If it isn't set, tell the user how to get one: Google Cloud console, APIs & Services, enable "YouTube Data API v3", Credentials, Create API key. Then they set it (`export YOUTUBE_API_KEY=...` on Mac or Linux, `set YOUTUBE_API_KEY=...` on Windows). Never ask them to paste the key into the chat.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/fetch_comments.py --channel @handle --latest 10 --out comments.csv
python ${CLAUDE_SKILL_DIR}/scripts/fetch_comments.py --video https://youtu.be/ID --video https://youtu.be/ID2 --out comments.csv
```

Defaults are 10 recent uploads and 500 top comments per video. For a big channel, 10 videos is plenty. For a small one, raise `--latest`.

If the script skips videos (comments turned off, private, quota), tell the user which ones. Don't present the result as covering videos it didn't read.

## Step 3: Read and tag

Read `comments.csv`. The `signal` column marks likely questions and requests. Read those first, but read the rest too: objections and complaints rarely end in a question mark.

Write `tags.csv` with one row per comment you place in a theme:

```
comment_id,theme,type
UgzAbc123,Tracking phone call conversions,question
UgzDef456,Too expensive for a small shop,objection
UgzGhi789,skip,other
```

Rules for themes:
- **A theme is one specific need, not a topic.** "Tracking phone call conversions" is a theme. "Tracking" is a topic and too broad to act on. "Tracking calls from Google Business Profile" is too narrow unless lots of people ask exactly that.
- **Name it in the commenters' words**, not marketing words.
- **Aim for 8 to 25 themes.** If one theme holds more than a quarter of the tagged comments, split it.
- **type** is one of `question`, `request`, `objection`, `complaint`, `praise`, `other`.
- Use theme `skip` for spam, jokes, "first" and anything off topic. Plain praise ("great video") is usually `skip` unless it says *what* was great.
- Copy `comment_id` exactly. The script refuses ids it can't find.

With more than about 1,500 comments, tag the 1,500 with the most likes plus every comment marked question or request, and tell the user the rest weren't read.

## Step 4: Rank

```bash
python ${CLAUDE_SKILL_DIR}/scripts/rank_themes.py comments.csv tags.csv --out themes
```

It ranks themes by **votes**: comments in the theme plus the likes on them, because a like is someone saying "me too". It writes `themes.csv` and `themes.xlsx` (a Themes sheet and a Comments sheet with every tagged comment). If it reports errors, fix `tags.csv` and run it again. Quote numbers from the script's output, never your own count.

## Step 5: Turn the top themes into the deliverable

Take the top 10 themes by votes (fewer if the data is thin) and write what the user asked for.

**Ad research.** For each theme:
- the angle in one line;
- 2 or 3 headline ideas in the commenters' language (for full responsive search ads, hand them to an RSA writer);
- for objections, the answer the ad or landing page should give, and whether the user's own page gives it.

**Video topics.** For each theme: 3 title ideas, and one line on what the video must answer to satisfy the people who asked.

**FAQ and gaps.** For each question: the answer if the user's site has it (link the page), or "not answered" if it doesn't.

Always quote 1 or 2 real comments per theme, word for word from the sheet, so the user can see the evidence.

## Rules

- **Only quote comments that exist.** Every quote comes from `comments.csv`. Don't paraphrase inside quotation marks.
- **Don't invent numbers.** Votes, counts and video counts come from `rank_themes.py`.
- **Be honest about small samples.** A theme with 3 comments is an anecdote. Say so when the whole run has fewer than about 200 tagged comments.
- **Comments are not a survey.** They come from people who watch and comment, which skews towards fans, beginners and the annoyed. Say this once in the summary.
- **No commenter names** in anything you write. The script doesn't collect them, so don't look them up.

## Output

In chat: one line on what was read (videos, comments, how many tagged), the top themes with votes, then the deliverable. Then give the user `themes.xlsx` and the deliverable as a file if it's long.
