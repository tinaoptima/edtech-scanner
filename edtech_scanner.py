#!/usr/bin/env python3
"""
EdTech AI Scanner — Free RSS-Based Daily Digest
================================================
Scours edtech RSS feeds and AI tool directories daily, deduplicates
against previous results, and emails a polished HTML digest.

Runs for FREE via GitHub Actions (no API keys, no costs).

Setup: See README.md for full instructions.
"""

import feedparser
import json
import re
import os
import smtplib
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

# ─── Configuration ──────────────────────────────────────────────────────────

EMAIL_FROM = os.environ.get("EMAIL_FROM", "your-email@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "your-app-password")
EMAIL_TO = os.environ.get("EMAIL_TO", "tina@example.com,boss@example.com")  # comma-separated
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# Where we store seen tools (persists between runs via GitHub Actions cache or local file)
HISTORY_FILE = os.environ.get("HISTORY_FILE", "seen_tools.json")
MAX_RESULTS = 25
MAX_PER_CATEGORY = 5
LOOKBACK_DAYS = 3  # Only include items published in the last N days

# ─── RSS Feed Sources ───────────────────────────────────────────────────────

FEEDS = {
    "EdSurge": {
        "url": "https://edsurge.com/articles_rss",
        "category": "General EdTech News",
    },
    "eSchool News - AI": {
        "url": "https://www.eschoolnews.com/ai-in-education/feed/",
        "category": "AI in Education",
    },
    "eSchool News - EdTech": {
        "url": "https://www.eschoolnews.com/ed-tech-solutions/feed/",
        "category": "EdTech Solutions",
    },
    "Campus Technology": {
        "url": "https://campustechnology.com/rss-feeds/all.aspx",
        "category": "Higher Ed Tech",
    },
    "AI Blog - Education": {
        "url": "https://www.artificial-intelligence.blog/education?format=rss",
        "category": "AI Education Research",
    },
    "EdTech Magazine": {
        "url": "https://edtechmagazine.com/k12/rss.xml",
        "category": "K-12 EdTech",
    },
    "The Journal": {
        "url": "https://thejournal.com/rss-feeds/all.aspx",
        "category": "Education Technology",
    },
    "Product Hunt - AI Education": {
        "url": "https://www.producthunt.com/feed?category=artificial-intelligence",
        "category": "New AI Tools",
    },
    "Hacker News - AI": {
        "url": "https://hnrss.org/newest?q=AI+education+tool",
        "category": "AI Tool Launches",
    },
    "Google Alerts - AI EdTech": {
        "url": "https://www.google.com/alerts/feeds/placeholder-replace-with-your-alert-id",
        "category": "AI EdTech Alerts",
    },
    "TAO Testing": {
        "url": "https://taotesting.com/feed/",
        "category": "Assessment Technology",
    },
    "TeacherCast": {
        "url": "https://teachercast.net/feed/",
        "category": "Classroom Tech",
    },
}

# ─── Keywords for filtering relevance ────────────────────────────────────────

AI_EDTECH_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "gpt", "llm",
    "chatbot", "generative ai", "adaptive learning", "personalized learning",
    "ai tutor", "ai assessment", "ai grading", "ai curriculum",
    "ai classroom", "ai teacher", "ai student", "edtech",
    "education technology", "learning platform", "ai tool",
    "copilot", "ai assistant", "vr education", "ar education",
    "ai analytics", "learning management", "ai content",
    "intelligent tutoring", "ai writing", "ai reading",
    "ai math", "ai science", "ai language", "ai special education",
    "accessibility ai", "ai quiz", "ai feedback", "ai rubric",
]

CATEGORY_LABELS = {
    "tutoring": "AI Tutoring & Personalized Learning",
    "content": "AI Content Creation for Educators",
    "assessment": "AI Assessment & Grading",
    "classroom": "AI Classroom Management & LMS",
    "curriculum": "AI Curriculum Design",
    "accessibility": "AI Special Education & Accessibility",
    "vr": "AI VR/AR Education",
    "analytics": "AI Learning Analytics",
    "language": "AI Language Learning",
    "stem": "AI STEM Education",
    "general": "General AI EdTech",
}

CATEGORY_KEYWORD_MAP = {
    "tutoring": ["tutor", "personalized", "adaptive", "student-facing", "1-on-1", "homework"],
    "content": ["content creation", "lesson plan", "generate", "create content", "course design", "slide"],
    "assessment": ["assessment", "grading", "rubric", "quiz", "test", "exam", "feedback", "evaluate"],
    "classroom": ["classroom", "lms", "management", "engage", "attendance", "behavior"],
    "curriculum": ["curriculum", "standards", "alignment", "scope", "sequence", "lesson"],
    "accessibility": ["accessibility", "special education", "iep", "disability", "accommodat", "inclusion"],
    "vr": ["vr", "virtual reality", "ar", "augmented", "immersive", "3d", "metaverse"],
    "analytics": ["analytics", "dashboard", "data", "insight", "predict", "early warning", "retention"],
    "language": ["language learning", "esl", "translation", "bilingual", "vocabulary", "pronunciation"],
    "stem": ["stem", "math", "science", "coding", "programming", "engineering", "physics", "chemistry"],
}


# ─── Utility Functions ───────────────────────────────────────────────────────

def make_id(title: str, url: str) -> str:
    """Create a stable unique ID for a tool/article."""
    raw = f"{title.lower().strip()}|{urlparse(url).netloc}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_history() -> dict:
    """Load previously seen tool IDs."""
    path = Path(HISTORY_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {"seen": {}, "last_run": None}
    return {"seen": {}, "last_run": None}


def save_history(history: dict):
    """Save seen tool IDs for deduplication."""
    Path(HISTORY_FILE).write_text(json.dumps(history, indent=2))


def compute_relevance(title: str, summary: str) -> float:
    """Score 0-1 how relevant an item is to AI + Education tools."""
    text = f"{title} {summary}".lower()
    matches = sum(1 for kw in AI_EDTECH_KEYWORDS if kw in text)
    # Bonus for tool-specific language
    tool_words = ["launch", "release", "new tool", "platform", "app", "software", "free", "pricing"]
    tool_matches = sum(1 for tw in tool_words if tw in text)
    score = min(1.0, (matches * 0.12) + (tool_matches * 0.08))
    return round(score, 2)


def classify_category(title: str, summary: str) -> str:
    """Assign the best-fit category."""
    text = f"{title} {summary}".lower()
    scores = {}
    for cat_key, keywords in CATEGORY_KEYWORD_MAP.items():
        scores[cat_key] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return CATEGORY_LABELS.get(best, "General AI EdTech") if scores[best] > 0 else "General AI EdTech"


def extract_pricing_hints(text: str) -> str:
    """Try to find pricing info in the text."""
    text_lower = text.lower()
    if "free" in text_lower and "trial" not in text_lower:
        return "Free"
    if "freemium" in text_lower:
        return "Freemium"
    price_match = re.search(r'\$\d+[\d,.]*(?:\s*/?(?:mo|month|year|yr|seat|user))?', text, re.IGNORECASE)
    if price_match:
        return price_match.group(0)
    if "open source" in text_lower:
        return "Free / Open Source"
    return "Check website"


# ─── Feed Fetching ───────────────────────────────────────────────────────────

def fetch_all_feeds() -> list:
    """Fetch and parse all RSS feeds, return list of candidate items."""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    for source_name, feed_info in FEEDS.items():
        url = feed_info["url"]
        print(f"  Fetching: {source_name}...")

        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                print(f"    ⚠ Failed to parse: {source_name}")
                continue

            for entry in feed.entries[:20]:  # Cap per feed
                # Parse date
                published = None
                for date_field in ["published_parsed", "updated_parsed", "created_parsed"]:
                    dt = getattr(entry, date_field, None)
                    if dt:
                        try:
                            published = datetime(*dt[:6], tzinfo=timezone.utc)
                        except Exception:
                            pass
                        break

                # Skip old items
                if published and published < cutoff:
                    continue

                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                summary = getattr(entry, "summary", "")
                # Clean HTML from summary
                summary = re.sub(r'<[^>]+>', '', summary).strip()[:500]

                if not title or not link:
                    continue

                relevance = compute_relevance(title, summary)
                if relevance < 0.1:
                    continue

                category = classify_category(title, summary)
                pricing = extract_pricing_hints(f"{title} {summary}")

                items.append({
                    "id": make_id(title, link),
                    "title": title,
                    "url": link,
                    "summary": summary[:300],
                    "source": source_name,
                    "category": category,
                    "relevance": relevance,
                    "pricing": pricing,
                    "published": published.isoformat() if published else None,
                    "feed_category": feed_info["category"],
                })

            print(f"    ✓ {source_name}: {len(feed.entries)} entries")
        except Exception as e:
            print(f"    ✗ {source_name}: {e}")

    return items


# ─── Deduplication & Ranking ─────────────────────────────────────────────────

def filter_and_rank(items: list, history: dict) -> list:
    """Deduplicate, rank, and cap results."""
    seen = history.get("seen", {})

    # Remove previously seen
    new_items = [item for item in items if item["id"] not in seen]
    print(f"\n  {len(items)} total items → {len(new_items)} after deduplication")

    # Sort by relevance
    new_items.sort(key=lambda x: x["relevance"], reverse=True)

    # Cap per category
    category_counts = {}
    final = []
    for item in new_items:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0)
        if category_counts[cat] < MAX_PER_CATEGORY:
            final.append(item)
            category_counts[cat] += 1
        if len(final) >= MAX_RESULTS:
            break

    # Mark all as seen
    for item in final:
        seen[item["id"]] = {
            "title": item["title"],
            "first_seen": datetime.now(timezone.utc).isoformat(),
        }

    # Prune history older than 90 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    seen = {k: v for k, v in seen.items() if v.get("first_seen", "") > cutoff}

    history["seen"] = seen
    history["last_run"] = datetime.now(timezone.utc).isoformat()

    return final


# ─── HTML Email Template ─────────────────────────────────────────────────────

def build_html_email(items: list, run_date: str) -> str:
    """Build a polished, forwardable HTML email digest."""

    # Group by category
    by_category = {}
    for item in items:
        cat = item["category"]
        by_category.setdefault(cat, []).append(item)

    category_blocks = ""
    for cat, tools in sorted(by_category.items()):
        tool_rows = ""
        for t in tools:
            relevance_pct = int(t["relevance"] * 100)
            dots = "●" * min(5, int(t["relevance"] * 5) + 1) + "○" * max(0, 5 - int(t["relevance"] * 5) - 1)

            pricing_color = "#4ade80" if "free" in (t["pricing"] or "").lower() else "#facc15" if "freemium" in (t["pricing"] or "").lower() else "#a1a1aa"

            tool_rows += f"""
            <tr>
              <td style="padding: 16px 20px; border-bottom: 1px solid #1e293b;">
                <a href="{t['url']}" style="color: #60a5fa; text-decoration: none; font-weight: 600; font-size: 15px;">{t['title']}</a>
                <div style="margin-top: 4px;">
                  <span style="background: #1e293b; color: {pricing_color}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{t['pricing']}</span>
                  <span style="color: #64748b; font-size: 11px; margin-left: 8px;">via {t['source']}</span>
                  <span style="color: #f59e0b; font-size: 12px; margin-left: 8px; letter-spacing: 1px;">{dots}</span>
                </div>
                <p style="color: #94a3b8; font-size: 13px; line-height: 1.6; margin: 8px 0 0;">{t['summary']}</p>
              </td>
            </tr>"""

        category_blocks += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
          <tr>
            <td style="padding: 10px 20px; background: #1e293b; border-radius: 8px 8px 0 0;">
              <span style="color: #f1f5f9; font-weight: 700; font-size: 14px;">{cat}</span>
              <span style="color: #64748b; font-size: 12px; margin-left: 8px;">({len(tools)} tool{'s' if len(tools) != 1 else ''})</span>
            </td>
          </tr>
          {tool_rows}
        </table>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 0; background: #020617; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background: #020617;">
    <tr>
      <td align="center" style="padding: 20px;">
        <table width="640" cellpadding="0" cellspacing="0" style="background: #0f172a; border-radius: 12px; overflow: hidden; border: 1px solid #1e293b;">

          <!-- Header -->
          <tr>
            <td style="padding: 28px 24px; background: linear-gradient(135deg, #1e1b4b, #0f172a); border-bottom: 1px solid #1e293b;">
              <table width="100%">
                <tr>
                  <td>
                    <span style="font-size: 22px;">⚡</span>
                    <span style="color: #f1f5f9; font-size: 20px; font-weight: 700; margin-left: 8px;">EdTech AI Scanner</span>
                    <div style="color: #64748b; font-size: 12px; margin-top: 4px;">Daily Digest • {run_date} • OptimaEd Emerging Technology</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Summary Stats -->
          <tr>
            <td style="padding: 20px 24px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="25%" style="text-align: center; padding: 12px; background: #020617; border-radius: 8px;">
                    <div style="color: #3b82f6; font-size: 24px; font-weight: 700;">{len(items)}</div>
                    <div style="color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: 1px;">New Tools</div>
                  </td>
                  <td width="5%"></td>
                  <td width="25%" style="text-align: center; padding: 12px; background: #020617; border-radius: 8px;">
                    <div style="color: #8b5cf6; font-size: 24px; font-weight: 700;">{len(by_category)}</div>
                    <div style="color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: 1px;">Categories</div>
                  </td>
                  <td width="5%"></td>
                  <td width="25%" style="text-align: center; padding: 12px; background: #020617; border-radius: 8px;">
                    <div style="color: #4ade80; font-size: 24px; font-weight: 700;">{sum(1 for i in items if 'free' in (i['pricing'] or '').lower())}</div>
                    <div style="color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: 1px;">Free Tools</div>
                  </td>
                  <td width="5%"></td>
                  <td width="25%" style="text-align: center; padding: 12px; background: #020617; border-radius: 8px;">
                    <div style="color: #f59e0b; font-size: 24px; font-weight: 700;">{len([k for k,v in history_global.get('seen',{}).items()])}</div>
                    <div style="color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: 1px;">Total Tracked</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Tool Listings -->
          <tr>
            <td style="padding: 0 24px 24px;">
              {category_blocks}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 24px; background: #020617; border-top: 1px solid #1e293b; text-align: center;">
              <p style="color: #475569; font-size: 11px; margin: 0;">
                EdTech AI Scanner • Auto-generated {run_date}<br>
                Scanning {len(FEEDS)} RSS sources • Showing only NEW discoveries (max {MAX_RESULTS})<br>
                Powered by RSS feeds — $0 cost
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html


# ─── Email Sending ────────────────────────────────────────────────────────────

def send_email(html: str, item_count: int, run_date: str):
    """Send the HTML digest via SMTP."""
    recipients = [e.strip() for e in EMAIL_TO.split(",") if e.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⚡ EdTech AI Scanner — {item_count} New Tools ({run_date})"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(recipients)

    # Plain text fallback
    plain = f"EdTech AI Scanner found {item_count} new AI education tools on {run_date}. View the HTML version of this email for the full digest."
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, recipients, msg.as_string())
        print(f"✅ Email sent to: {', '.join(recipients)}")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        # Save HTML locally as fallback
        fallback_path = f"digest_{run_date}.html"
        Path(fallback_path).write_text(html)
        print(f"  → Saved HTML to {fallback_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

history_global = {}

def main():
    global history_global
    run_date = datetime.now().strftime("%Y-%m-%d")
    print(f"{'='*60}")
    print(f"  EdTech AI Scanner — {run_date}")
    print(f"{'='*60}")

    # Load history
    history = load_history()
    history_global = history
    prev_count = len(history.get("seen", {}))
    print(f"\n📚 History: {prev_count} tools previously seen")
    print(f"📡 Fetching from {len(FEEDS)} RSS sources...\n")

    # Fetch
    items = fetch_all_feeds()
    print(f"\n📊 Fetched {len(items)} relevant items")

    # Filter and rank
    final = filter_and_rank(items, history)
    print(f"📋 Final digest: {len(final)} new tools")

    if len(final) == 0:
        print("\n😴 No new tools found today. Skipping email.")
        save_history(history)
        return

    # Build email
    html = build_html_email(final, run_date)

    # Send
    print(f"\n📧 Sending digest...")
    send_email(html, len(final), run_date)

    # Save history
    save_history(history)
    new_count = len(history.get("seen", {}))
    print(f"\n💾 History updated: {prev_count} → {new_count} tools tracked")
    print(f"{'='*60}")
    print(f"  Done! Next scan in ~24 hours.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
