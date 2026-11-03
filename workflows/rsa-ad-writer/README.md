# Responsive search ad writer

Give it your landing page and it writes a full Google Ads responsive search ad (RSA) for each ad group: 15 headlines and 4 descriptions. A script checks every line against Google's limits, and you get a review sheet plus a file ready for Google Ads Editor.

More about it: https://gruntstack.com/workflows/rsa-ad-copy/

## What's in this folder

| File | What it does |
|---|---|
| `SKILL.md` | The instructions the AI follows: gather inputs, plan the message, write the copy, check it, save it. |
| `scripts/verify_chars.py` | Checks character limits, counts, keyword use and near-duplicate headlines. Fails if anything is wrong. |
| `scripts/build_sheet.py` | Turns the checked copy into an `.xlsx` review sheet and a Google Ads Editor `.csv`. |
| `examples/` | A full sample run for an emergency plumber in Austin, with the output files. |
| `evals/evals.json` | Test prompts for checking the skill still works after you change it. |

## Use it

**Claude Code:** copy this folder to `.claude/skills/rsa-ad-writer/` in your project (or `~/.claude/skills/` to use it everywhere). Then ask: "Write RSA copy for my ad group about emergency plumbing. Landing page: https://..."

**Claude.ai:** zip this folder and upload it under Settings → Capabilities → Skills. Then ask the same way.

**Other AI agents:** give the agent `SKILL.md` as its instructions and let it run the two scripts.

The scripts need Python 3.9+. The `.xlsx` output needs `openpyxl` (`pip install openpyxl`). Without it, you still get the CSV.

## Run the scripts yourself

```bash
python scripts/verify_chars.py output.txt --keyword "emergency plumber"
python scripts/build_sheet.py output.txt --out emergency-plumber \
  --campaign "Search - Plumbing" --ad-group "Emergency Plumber" \
  --final-url https://example.com/emergency --path1 emergency --path2 austin
```

`output.txt` uses one line per asset:

```
H1: Emergency Plumber Austin (24) - Feature [pin: 1]
D1: Burst pipe or gas leak? A plumber at your door in 60 minutes or less. Call now. (79) - Offer
```

The number in brackets and the category are optional. The scripts count the characters themselves.

## Before you import

- Check the campaign and ad group names in the CSV match Google Ads exactly, or Editor will create new ones.
- Editor column names can change between versions. If an import fails, compare the CSV headers with an export from your own Editor.
- Read the copy. The scripts check the rules, not whether the ad is any good.

## Limits

It writes from your landing page and brief. If the page is vague, the ads will be too. It won't make up claims, so if the page has no proof, the ads won't either.

## Found a problem?

Open an issue in this repo and tell me what you ran and what happened.
