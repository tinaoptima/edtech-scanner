# ⚡ EdTech AI Scanner — Free Daily Digest

**Automated AI education tool discovery that emails you a polished HTML digest every morning. Completely free.**

Built for OptimaEd's Emerging Technology team.

---

## What It Does

- Scours **12+ RSS feeds** from EdSurge, eSchool News, Product Hunt, Campus Technology, Hacker News, and more
- Filters for **AI + education relevance** using keyword scoring
- **Deduplicates** against all previous runs — you only see NEW discoveries
- Auto-categorizes into EdTech categories (tutoring, assessment, VR/AR, etc.)
- Detects **pricing hints** (free, freemium, paid with prices)
- Caps at **25 results max, 5 per category**
- Sends a **polished dark-themed HTML email** you can forward directly to your CTO
- Runs **daily at 7 AM Eastern** via GitHub Actions — **$0 cost**

---

## 15-Minute Setup

### Step 1: Create a GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name it `edtech-scanner` (private is fine)
3. Upload all the files from this folder maintaining the structure:

```
edtech-scanner/
├── .github/
│   └── workflows/
│       └── daily-scan.yml
├── edtech_scanner.py
├── requirements.txt
├── seen_tools.json
└── README.md
```

### Step 2: Set Up a Gmail App Password

You need an "App Password" (not your regular Gmail password):

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already on
3. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Select **Mail** → **Other** → name it "EdTech Scanner"
5. Copy the 16-character password it generates

> **Using Outlook/other?** Change SMTP_SERVER and SMTP_PORT in the secrets (see below).

### Step 3: Add GitHub Secrets

In your GitHub repo:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add these secrets (click "New repository secret" for each):

| Secret Name     | Value                                      |
|----------------|--------------------------------------------|
| `EMAIL_FROM`   | `your-gmail@gmail.com`                     |
| `EMAIL_PASSWORD` | The 16-char app password from Step 2     |
| `EMAIL_TO`     | `tina@email.com,boss@email.com`            |
| `SMTP_SERVER`  | `smtp.gmail.com`                           |
| `SMTP_PORT`    | `587`                                      |

### Step 4: (Optional) Add Google Alerts

For even better coverage, create custom Google Alerts:

1. Go to [google.com/alerts](https://google.com/alerts)
2. Create alerts for:
   - `"AI education tool" new launch`
   - `"edtech AI" product launch 2025 OR 2026`
   - `"AI tutoring" platform release`
   - `"AI grading" OR "AI assessment" tool`
3. For each alert, click **Show options** → set **Deliver to: RSS feed**
4. Copy each RSS feed URL
5. Add them to the `FEEDS` dictionary in `edtech_scanner.py`

### Step 5: Test It

1. Go to your repo → **Actions** tab
2. Click **EdTech AI Scanner - Daily Digest**
3. Click **Run workflow** → **Run workflow**
4. Watch the logs — you should get an email within 2-3 minutes

---

## How Deduplication Works

- Every tool gets a unique ID based on its title + domain
- `seen_tools.json` tracks all previously seen IDs
- Each run: the scanner skips anything already in the history
- History auto-prunes entries older than 90 days
- The file is committed back to the repo after each run, so state persists

**Day 1:** You might get 20-25 results (everything is new).
**Day 2+:** You'll only see genuinely new articles and tools.

---

## Customization

### Change the schedule
Edit `.github/workflows/daily-scan.yml`:
```yaml
schedule:
  - cron: '0 12 * * *'  # UTC time. 12 UTC = 7 AM Eastern
```
[Cron helper](https://crontab.guru/)

### Add more RSS feeds
Edit the `FEEDS` dict in `edtech_scanner.py`:
```python
"New Source Name": {
    "url": "https://example.com/feed.xml",
    "category": "Category Name",
},
```

### Adjust relevance sensitivity
- Lower `0.1` threshold in `fetch_all_feeds()` to catch more items
- Edit `AI_EDTECH_KEYWORDS` list to add domain-specific terms

### Change caps
```python
MAX_RESULTS = 25      # Total items in digest
MAX_PER_CATEGORY = 5  # Items per category
LOOKBACK_DAYS = 3     # How far back to look in feeds
```

---

## Cost Breakdown

| Component | Cost |
|-----------|------|
| GitHub Actions | Free (2,000 min/month, this uses ~3 min/day) |
| RSS feeds | Free |
| Gmail SMTP | Free |
| Python + feedparser | Free |
| **Total** | **$0/month** |

---

## Troubleshooting

**No email received?**
- Check GitHub Actions logs for errors
- Verify Gmail App Password is correct
- Check spam folder
- Make sure 2-Step Verification is enabled on Gmail

**Too few results?**
- Lower the relevance threshold from `0.1` to `0.05`
- Add more RSS feeds
- Increase `LOOKBACK_DAYS` from 3 to 7

**Too many irrelevant results?**
- Raise the relevance threshold to `0.15` or `0.2`
- Add negative keywords to filter out

**Want to add Outlook instead of Gmail?**
Set these secrets:
- `SMTP_SERVER`: `smtp.office365.com`
- `SMTP_PORT`: `587`

---

## Architecture

```
GitHub Actions (cron, daily)
    │
    ▼
edtech_scanner.py
    │
    ├── Fetch 12+ RSS feeds (feedparser)
    ├── Score relevance (keyword matching)
    ├── Classify categories
    ├── Deduplicate vs seen_tools.json
    ├── Rank and cap (25 max, 5/category)
    ├── Build HTML email
    ├── Send via SMTP
    │
    ▼
seen_tools.json (committed back to repo)
```

No APIs. No costs. No maintenance beyond adding feeds.
