#!/usr/bin/env python3
"""
IT記事 X投稿ジェネレーター（複数ソース版）
使い方: python3 it_post_generator_rss.py
ブラウザで http://localhost:8765 を開く
"""

import os
import json
import threading
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
import html
import re
import hmac
import hashlib
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Asia/Tokyo")
except ImportError:
    from datetime import timedelta, tzinfo
    class _JST(tzinfo):
        def utcoffset(self, dt): return timedelta(hours=9)
        def tzname(self, dt): return "JST"
        def dst(self, dt): return timedelta(0)
    LOCAL_TZ = _JST()

API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
PORT       = int(os.environ.get("PORT", 8765))
RECENT_DAYS = 0
RSS_FETCH_TIMEOUT = 1.8
RSS_FETCH_FAST_BUDGET = 1.2
RSS_FETCH_MAX_BUDGET = 2.6
RSS_PER_FEED_LIMIT = 10
SPECIAL_PER_FEED_LIMIT = 5
RSS_EMPTY_RETRY_DELAY = 0.8

# Cookie認証（環境変数で設定。未設定なら認証なし）
BASIC_USER = os.environ.get("BASIC_USER", "")
BASIC_PASS = os.environ.get("BASIC_PASS", "")
COOKIE_SECRET = os.environ.get("COOKIE_SECRET", BASIC_PASS or "dev-secret")
COOKIE_NAME = "it_post_session"

def _make_token():
    """サーバー再起動後も有効な固定トークンを生成"""
    return hmac.new(COOKIE_SECRET.encode(), b"authenticated", hashlib.sha256).hexdigest()

VALID_TOKEN = _make_token()

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ログイン</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;display:flex;align-items:center;justify-content:center;min-height:100vh}
  .card{background:#fff;border-radius:16px;padding:2.5rem 2rem;width:100%;max-width:360px;box-shadow:0 2px 20px rgba(0,0,0,.08)}
  h1{font-size:1.3rem;font-weight:700;margin-bottom:.4rem;text-align:center}
  p{font-size:.85rem;color:#888;text-align:center;margin-bottom:1.8rem}
  label{font-size:.8rem;color:#555;display:block;margin-bottom:.3rem}
  input{width:100%;padding:.7rem 1rem;border:1px solid #e5e5e5;border-radius:10px;font-size:.95rem;margin-bottom:1rem;outline:none}
  input:focus{border-color:#1a1a1a}
  button{width:100%;padding:.8rem;background:#1a1a1a;color:#fff;border:none;border-radius:10px;font-size:.95rem;font-weight:600;cursor:pointer}
  button:hover{background:#333}
  .error{background:#fff0f0;color:#c00;border:1px solid #fcc;border-radius:8px;padding:.6rem 1rem;font-size:.85rem;margin-bottom:1rem;text-align:center}
</style>
</head>
<body>
<div class="card">
  <h1>📰 IT記事ジェネレーター</h1>
  <p>ログインしてください</p>
  {error}
  <form method="POST" action="/login">
    <label>ユーザー名</label>
    <input type="text" name="username" autocomplete="username" required autofocus>
    <label>パスワード</label>
    <input type="password" name="password" autocomplete="current-password" required>
    <button type="submit">ログイン</button>
  </form>
</div>
</body>
</html>"""

RSS_FEEDS = {
    "AI・機械学習": [
        # 国内
        {"url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", "source": "ITmedia AI"},
        {"url": "https://japan.cnet.com/rss/index.rdf", "source": "CNET Japan"},
        {"url": "https://www.publickey1.jp/atom.xml", "source": "Publickey"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        {"url": "https://ainow.ai/feed/", "source": "AINOW"},
        # AI企業公式Blog
        {"url": "https://openai.com/blog/rss.xml", "source": "OpenAI Blog"},
        {"url": "https://deepmind.google/blog/rss.xml", "source": "Google DeepMind Blog"},
        {"url": "https://huggingface.co/blog/feed.xml", "source": "Hugging Face Blog"},
        {"url": "https://blog.google/technology/ai/rss/", "source": "Google AI Blog"},
        {"url": "https://engineering.fb.com/feed/", "source": "Meta Engineering Blog"},
        {"url": "https://research.google/blog/rss/", "source": "Google Research Blog"},
        # 海外メディア（AI特化）
        {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "source": "TechCrunch AI"},
        {"url": "https://venturebeat.com/category/ai/feed/", "source": "VentureBeat AI"},
        {"url": "https://www.wired.com/feed/tag/ai/latest/rss", "source": "WIRED AI"},
        {"url": "https://www.technologyreview.com/feed/", "source": "MIT Technology Review"},
        {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "source": "Ars Technica"},
        # HN（AI関連キーワード絞り込み）
        # arxiv（各2件に絞る → per_feed_limitで制御）
        {"url": "https://rss.arxiv.org/rss/cs.AI", "source": "arxiv AI"},
        {"url": "https://rss.arxiv.org/rss/cs.LG", "source": "arxiv ML"},
    ],
    "クラウド・AWS": [
        # 国内
        {"url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml", "source": "ITmedia Enterprise"},
        {"url": "https://cloud.watch.impress.co.jp/data/rss/1.0/clw/feed.rdf", "source": "クラウド Watch"},
        {"url": "https://www.publickey1.jp/atom.xml", "source": "Publickey"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://aws.amazon.com/blogs/aws/feed/", "source": "AWS Blog"},
        {"url": "https://www.zdnet.com/topic/cloud/rss.xml", "source": "ZDNet Cloud"},
        {"url": "https://thenewstack.io/feed/", "source": "The New Stack"},
        {"url": "https://news.ycombinator.com/rss", "source": "Hacker News"},
    ],
    "セキュリティ": [
        # 国内
        {"url": "https://rss.itmedia.co.jp/rss/2.0/news_security.xml", "source": "ITmedia セキュリティ"},
        {"url": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf", "source": "INTERNET Watch"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://feeds.feedburner.com/TheHackersNews", "source": "The Hacker News"},
        {"url": "https://krebsonsecurity.com/feed/", "source": "Krebs on Security"},
        {"url": "https://www.darkreading.com/rss.xml", "source": "Dark Reading"},
        {"url": "https://www.zdnet.com/topic/security/rss.xml", "source": "ZDNet Security"},
        {"url": "https://isc.sans.edu/rssfeed_full.xml", "source": "SANS Internet Storm Center"},
        {"url": "https://news.ycombinator.com/rss", "source": "Hacker News"},
    ],
    "開発": [
        # 国内
        {"url": "https://codezine.jp/rss/new/20/index.xml", "source": "CodeZine"},
        {"url": "https://www.publickey1.jp/atom.xml", "source": "Publickey"},
        {"url": "https://zenn.dev/feed", "source": "Zenn"},
        {"url": "https://qiita.com/popular-items/feed.atom", "source": "Qiita 人気記事"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://github.blog/feed/", "source": "GitHub Blog"},
        {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "source": "Ars Technica"},
        {"url": "https://stackoverflow.blog/feed/", "source": "Stack Overflow Blog"},
        {"url": "https://www.smashingmagazine.com/feed/", "source": "Smashing Magazine"},
        {"url": "https://css-tricks.com/feed/", "source": "CSS-Tricks"},
        {"url": "https://news.ycombinator.com/rss", "source": "Hacker News"},
    ],
    "スタートアップ": [
        # 国内
        {"url": "https://thebridge.jp/feed", "source": "BRIDGE"},
        {"url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "source": "ITmedia NEWS"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://techcrunch.com/category/startups/feed/", "source": "TechCrunch Startups"},
        {"url": "https://venturebeat.com/feed/", "source": "VentureBeat"},
        {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge"},
        {"url": "https://feeds.businessinsider.com/custom/all", "source": "Business Insider"},
        {"url": "https://techcrunch.com/feed/", "source": "TechCrunch"},
        {"url": "https://news.ycombinator.com/rss", "source": "Hacker News"},
    ],
    "便利ツール・Tips": [
        # 国内
        {"url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", "source": "PC Watch"},
        {"url": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf", "source": "INTERNET Watch"},
        {"url": "https://www.lifehacker.jp/feed/index.xml", "source": "Lifehacker Japan"},
        {"url": "https://zenn.dev/feed", "source": "Zenn"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://www.producthunt.com/feed", "source": "Product Hunt"},
        {"url": "https://lifehacker.com/rss", "source": "Lifehacker"},
        {"url": "https://news.ycombinator.com/rss", "source": "Hacker News"},
    ],
    "ガジェット・ハードウェア": [
        # 国内
        {"url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", "source": "PC Watch"},
        {"url": "https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf", "source": "ケータイ Watch"},
        {"url": "https://www.gizmodo.jp/index.xml", "source": "Gizmodo Japan"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://www.engadget.com/rss.xml", "source": "Engadget"},
        {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge"},
        {"url": "https://feeds.arstechnica.com/arstechnica/gadgets", "source": "Ars Technica Gadgets"},
        {"url": "https://gizmodo.com/rss", "source": "Gizmodo"},
        {"url": "https://www.tomshardware.com/feeds/all", "source": "Tom's Hardware"},
    ],
    "ビジネス・DX": [
        # 国内
        {"url": "https://rss.itmedia.co.jp/rss/2.0/business.xml", "source": "ITmedia ビジネス"},
        {"url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml", "source": "ITmedia Enterprise"},
        {"url": "https://www.publickey1.jp/atom.xml", "source": "Publickey"},
        {"url": "https://xtech.nikkei.com/rss/index.rdf", "source": "日経XTECH"},
        {"url": "https://www.forbes.com/innovation/feed2", "source": "Forbes Tech"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://techcrunch.com/category/enterprise/feed/", "source": "TechCrunch Enterprise"},
        {"url": "https://feeds.feedburner.com/fastcompany/headlines", "source": "Fast Company"},
        {"url": "https://www.zdnet.com/topic/digital-transformation/rss.xml", "source": "ZDNet DX"},
    ],
}

GITHUB_RELEASE_FEEDS = {
    "AI・機械学習": [
        {"url": "https://github.com/openai/openai-python/releases.atom", "source": "GitHub Releases: openai/openai-python"},
        {"url": "https://github.com/huggingface/transformers/releases.atom", "source": "GitHub Releases: huggingface/transformers"},
        {"url": "https://github.com/langchain-ai/langchain/releases.atom", "source": "GitHub Releases: langchain-ai/langchain"},
    ],
    "クラウド・AWS": [
        {"url": "https://github.com/aws/aws-cdk/releases.atom", "source": "GitHub Releases: aws/aws-cdk"},
        {"url": "https://github.com/aws/aws-cli/releases.atom", "source": "GitHub Releases: aws/aws-cli"},
        {"url": "https://github.com/cloudflare/workers-sdk/releases.atom", "source": "GitHub Releases: cloudflare/workers-sdk"},
    ],
    "セキュリティ": [
        {"url": "https://github.com/ossf/scorecard/releases.atom", "source": "GitHub Releases: ossf/scorecard"},
        {"url": "https://github.com/aquasecurity/trivy/releases.atom", "source": "GitHub Releases: aquasecurity/trivy"},
        {"url": "https://github.com/owasp-dep-scan/dep-scan/releases.atom", "source": "GitHub Releases: owasp-dep-scan/dep-scan"},
    ],
    "開発": [
        {"url": "https://github.com/vercel/next.js/releases.atom", "source": "GitHub Releases: vercel/next.js"},
        {"url": "https://github.com/nodejs/node/releases.atom", "source": "GitHub Releases: nodejs/node"},
        {"url": "https://github.com/microsoft/TypeScript/releases.atom", "source": "GitHub Releases: microsoft/TypeScript"},
        {"url": "https://github.com/facebook/react/releases.atom", "source": "GitHub Releases: facebook/react"},
    ],
    "スタートアップ": [
        {"url": "https://github.com/vercel/next.js/releases.atom", "source": "GitHub Releases: vercel/next.js"},
        {"url": "https://github.com/supabase/supabase/releases.atom", "source": "GitHub Releases: supabase/supabase"},
        {"url": "https://github.com/stripe/stripe-node/releases.atom", "source": "GitHub Releases: stripe/stripe-node"},
    ],
    "便利ツール・Tips": [
        {"url": "https://www.raycast.com/changelog/feed.xml", "source": "Raycast Changelog"},
        {"url": "https://github.com/obsidianmd/obsidian-releases/releases.atom", "source": "GitHub Releases: obsidianmd/obsidian-releases"},
        {"url": "https://github.com/microsoft/vscode/releases.atom", "source": "GitHub Releases: microsoft/vscode"},
    ],
    "ガジェット・ハードウェア": [
        {"url": "https://github.com/raspberrypi/firmware/releases.atom", "source": "GitHub Releases: raspberrypi/firmware"},
        {"url": "https://github.com/arduino/Arduino/releases.atom", "source": "GitHub Releases: arduino/Arduino"},
    ],
    "ビジネス・DX": [
        {"url": "https://github.com/microsoft/PowerToys/releases.atom", "source": "GitHub Releases: microsoft/PowerToys"},
        {"url": "https://github.com/n8n-io/n8n/releases.atom", "source": "GitHub Releases: n8n-io/n8n"},
    ],
}

DOCS_UPDATE_FEEDS = {
    "AI・機械学習": [
        {"url": "https://openai.com/news/rss.xml", "source": "OpenAI News / Docs"},
        {"url": "https://developers.googleblog.com/feeds/posts/default", "source": "Google Developers Blog"},
    ],
    "クラウド・AWS": [
        {"url": "https://aws.amazon.com/about-aws/whats-new/recent/feed/", "source": "AWS What's New"},
        {"url": "https://blog.cloudflare.com/rss/", "source": "Cloudflare Blog"},
        {"url": "https://cloud.google.com/feeds/gcp-release-notes.xml", "source": "Google Cloud Release Notes"},
    ],
    "セキュリティ": [
        {"url": "https://blog.cloudflare.com/tag/security/rss/", "source": "Cloudflare Security Blog"},
    ],
    "開発": [
        {"url": "https://github.blog/changelog/feed/", "source": "GitHub Changelog"},
        {"url": "https://vercel.com/changelog/rss", "source": "Vercel Changelog"},
        {"url": "https://developer.chrome.com/blog/feed.xml", "source": "Chrome Developers Blog"},
    ],
    "スタートアップ": [
        {"url": "https://www.ycombinator.com/blog/rss", "source": "Y Combinator Blog"},
        {"url": "https://stripe.com/blog/feed.rss", "source": "Stripe Blog"},
    ],
    "便利ツール・Tips": [
        {"url": "https://github.blog/changelog/feed/", "source": "GitHub Changelog"},
        {"url": "https://developer.chrome.com/blog/feed.xml", "source": "Chrome Developers Blog"},
        {"url": "https://workspaceupdates.googleblog.com/feeds/posts/default", "source": "Google Workspace Updates"},
    ],
    "ガジェット・ハードウェア": [
        {"url": "https://developer.apple.com/news/releases/rss/releases.rss", "source": "Apple Developer Releases"},
    ],
    "ビジネス・DX": [
    ],
}

OFFICIAL_X_ACCOUNTS = {
    "AI・機械学習": [
        {"handle": "OpenAI", "name": "OpenAI", "topics": "ChatGPT、OpenAI API、モデル更新、公式発表"},
        {"handle": "AnthropicAI", "name": "Anthropic", "topics": "Claude、API、研究発表、モデル更新"},
        {"handle": "GoogleDeepMind", "name": "Google DeepMind", "topics": "Gemini、AI研究、モデル発表"},
    ],
    "クラウド・AWS": [
        {"handle": "awscloud", "name": "AWS", "topics": "AWS新サービス、障害情報、イベント、アップデート"},
        {"handle": "Azure", "name": "Microsoft Azure", "topics": "Azure新機能、クラウド運用、AIサービス更新"},
        {"handle": "googlecloud", "name": "Google Cloud", "topics": "Google Cloud新機能、インフラ、AI/データ基盤"},
    ],
    "セキュリティ": [
        {"handle": "msftsecintel", "name": "Microsoft Threat Intelligence", "topics": "脅威情報、攻撃キャンペーン、注意喚起"},
        {"handle": "CISAgov", "name": "CISA", "topics": "脆弱性注意喚起、勧告、セキュリティ警報"},
        {"handle": "TheHackersNews", "name": "The Hacker News", "topics": "セキュリティ速報、脆弱性、攻撃事例"},
    ],
    "開発": [
        {"handle": "github", "name": "GitHub", "topics": "GitHub新機能、Actions、Copilot、開発者向け更新"},
        {"handle": "vercel", "name": "Vercel", "topics": "Next.js、Vercel Platform、フロントエンド開発更新"},
        {"handle": "nodejs", "name": "Node.js", "topics": "Node.jsリリース、LTS、ランタイム更新"},
    ],
    "スタートアップ": [
        {"handle": "ycombinator", "name": "Y Combinator", "topics": "スタートアップ動向、資金調達、YC企業"},
        {"handle": "stripe", "name": "Stripe", "topics": "決済API、プロダクト更新、開発者向け機能"},
        {"handle": "supabase", "name": "Supabase", "topics": "Supabase新機能、DB、Auth、Edge Functions"},
    ],
    "便利ツール・Tips": [
        {"handle": "ProductHunt", "name": "Product Hunt", "topics": "新しいWebサービス、AIツール、便利アプリ"},
        {"handle": "raycastapp", "name": "Raycast", "topics": "Mac効率化、拡張機能、ワークフロー改善"},
        {"handle": "obsdmd", "name": "Obsidian", "topics": "ノート術、知識管理、プラグイン更新"},
    ],
    "ガジェット・ハードウェア": [
        {"handle": "verge", "name": "The Verge", "topics": "ガジェット、新製品発表、ハードウェアレビュー"},
        {"handle": "engadget", "name": "Engadget", "topics": "デバイス、スマートフォン、PC新製品"},
    ],
    "ビジネス・DX": [
        {"handle": "Forbes", "name": "Forbes", "topics": "ビジネス動向、スタートアップ、DX事例"},
        {"handle": "MicrosoftTeams", "name": "Microsoft Teams", "topics": "業務効率化、コラボレーション、DXツール更新"},
    ],
}

TRUST_SCORES = {
    "github_release": 95,
    "docs_update": 95,
    "official_blog": 90,
    "official_x": 85,
    "rss_news": 70,
}

TYPE_LABELS = {
    "github_release": "GitHub Releases",
    "docs_update": "Docs更新",
    "official_blog": "公式Blog",
    "official_x": "公式X",
    "rss_news": "RSSニュース",
}

OFFICIAL_BLOG_SOURCES = {
    "AWS Blog",
    "GitHub Blog",
    "Cloudflare Blog",
    "Google Cloud Blog",
    "Stripe Blog",
    "Supabase Blog",
    "Y Combinator Blog",
    # AI企業公式Blog
    "OpenAI Blog",
    "OpenAI News / Docs",
    "Google DeepMind Blog",
    "Hugging Face Blog",
    "Google AI Blog",
    "Google Research Blog",
    "Meta Engineering Blog",
    "Microsoft AI Blog",
    "Azure Blog",
}

JP_PRIORITY_SOURCES = [
    "ITmedia",
    "ZDNET Japan",
    "CNET Japan",
    "Publickey",
    "CodeZine",
    "Zenn",
    "Qiita",
    "Watch",
    "Lifehacker Japan",
    "BRIDGE",
    "TechCrunch Japan",
    "AINOW",
    "日経",
    "Gizmodo Japan",
    "ケータイ Watch",
    "クラウド Watch",
    "はてブ",
]

def strip_tags(text):
    return re.sub(r'<[^>]+>', '', html.unescape(text or '')).strip()

def compact_text(text, limit=140):
    text = re.sub(r'\s+', ' ', strip_tags(text)).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."

def parse_date_value(date):
    if not date:
        return None
    value = strip_tags(date)
    parsers = (
        lambda v: parsedate_to_datetime(v),
        lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")),
    )
    for parser in parsers:
        try:
            dt = parser(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return None

def article_age_days(article):
    sort_time = article.get("sortTime")
    if not sort_time:
        return None
    article_date = datetime.fromtimestamp(sort_time, timezone.utc).astimezone(LOCAL_TZ).date()
    today = datetime.now(LOCAL_TZ).date()
    return max(0, (today - article_date).days)

def format_local_date(parsed_date, fallback=""):
    if not parsed_date:
        return fallback[:16] if fallback else ""
    local = parsed_date.astimezone(LOCAL_TZ)
    return local.strftime("%Y-%m-%d %H:%M")

def classify_source(source):
    if source in OFFICIAL_BLOG_SOURCES:
        return "official_blog"
    return "rss_news"

def release_repo_name(source):
    return source.replace("GitHub Releases: ", "").strip()

def normalize_title(title, source, article_type):
    if article_type == "github_release":
        repo = release_repo_name(source)
        if title and repo and repo not in title:
            return f"{repo} {title}"
    return title

def build_article(title, link, source, date, article_type=None, summary=""):
    article_type = article_type or classify_source(source)
    parsed_date = parse_date_value(date)
    sort_time = parsed_date.timestamp() if parsed_date else 0
    return {
        "title": normalize_title(title, source, article_type),
        "url": link,
        "source": source,
        "published": format_local_date(parsed_date, date),
        "sortTime": sort_time,
        "summary": compact_text(summary),
        "type": article_type,
        "typeLabel": TYPE_LABELS[article_type],
        "trustScore": TRUST_SCORES[article_type],
    }

def fetch_article_body(url, char_limit=1500):
    """記事URLから本文テキストを取得して返す"""
    try:
        import urllib.request
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en;q=0.9",
        })
        with opener.open(req, timeout=15) as res:
            raw = res.read().decode("utf-8", errors="replace")

        # <script> <style> <nav> <header> <footer> <aside> <form> を除去
        raw = re.sub(r'<(script|style|nav|header|footer|aside|form)[^>]*>.*?</\1>', ' ', raw, flags=re.S|re.I)
        # <p> <li> <h1-6> <br> の前後に改行を挿入
        raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.I)
        raw = re.sub(r'<(p|li|h[1-6])[^>]*>', '\n', raw, flags=re.I)
        # 残りのタグを除去
        text = re.sub(r'<[^>]+>', '', raw)
        # HTMLエンティティをデコード
        text = html.unescape(text)
        # 空白・改行を整理
        lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
        lines = [l for l in lines if len(l) > 10]  # 短すぎる行（メニュー等）を除去
        text = '\n'.join(lines)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        # 文字数制限
        if len(text) > char_limit:
            text = text[:char_limit] + "..."
        return text
    except Exception as e:
        print(f"[記事取得] 失敗: {e}", flush=True)
        return ""

_RSS_CACHE = {}  # {feed_url: (timestamp, items_list)}
_RSS_CACHE_TTL = 300  # 5分キャッシュ
_RSS_FAIL_CACHE = {}  # {feed_url: timestamp}
_RSS_FAIL_CACHE_TTL = 600  # 10分間、失敗したフィードをスキップ

def fetch_rss(feed_url, source, limit=5, article_type=None):
    import time as _time
    failed_at = _RSS_FAIL_CACHE.get(feed_url)
    if failed_at and _time.time() - failed_at < _RSS_FAIL_CACHE_TTL:
        return []

    # キャッシュヒット確認
    cached = _RSS_CACHE.get(feed_url)
    if cached:
        ts, cached_items = cached
        if _time.time() - ts < _RSS_CACHE_TTL:
            return cached_items[:limit]

    try:
        import urllib.request
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        req = Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=RSS_FETCH_TIMEOUT) as res:
            raw = res.read()
        root = ET.fromstring(raw)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = []

        def _local_name(elem):
            return elem.tag.rsplit('}', 1)[-1] if '}' in elem.tag else elem.tag

        def _children_by_name(elem, name):
            return [child for child in list(elem) if _local_name(child) == name]

        def _first_text(elem, *names):
            for name in names:
                for child in _children_by_name(elem, name):
                    if child.text:
                        return child.text
            return ''

        # RSS 2.0
        rss_items = [elem for elem in root.iter() if _local_name(elem) == 'item']
        for item in rss_items[:limit]:
            title = strip_tags(_first_text(item, 'title'))
            link  = strip_tags(_first_text(item, 'link'))
            date  = strip_tags(_first_text(item, 'pubDate', 'date', 'updated', 'published'))
            summary = _first_text(item, 'description', 'summary', 'content')
            if title and link:
                items.append(build_article(title, link, source, date, article_type=article_type, summary=summary))

        # Atom
        if not items:
            atom_entries = root.findall('atom:entry', ns) or [
                elem for elem in root.iter() if _local_name(elem) == 'entry'
            ]
            for entry in atom_entries[:limit]:
                title = strip_tags(entry.findtext('atom:title', '', ns) or _first_text(entry, 'title'))
                link_el = entry.find('atom:link', ns)
                if link_el is None:
                    link_el = next((child for child in _children_by_name(entry, 'link')), None)
                link = link_el.get('href', '') if link_el is not None else ''
                if not link and link_el is not None and link_el.text:
                    link = link_el.text
                date = strip_tags(
                    entry.findtext('atom:published', '', ns)
                    or entry.findtext('atom:updated', '', ns)
                    or _first_text(entry, 'published', 'updated', 'date')
                )
                summary = (
                    entry.findtext('atom:summary', '', ns)
                    or entry.findtext('atom:content', '', ns)
                    or _first_text(entry, 'summary', 'content')
                )
                if title and link:
                    items.append(build_article(title, link, source, date, article_type=article_type, summary=summary))

        # キャッシュ保存（上限なしの全件を保存してlimitはスライスで対応）
        _RSS_CACHE[feed_url] = (_time.time(), items)
        _RSS_FAIL_CACHE.pop(feed_url, None)
        return items[:limit]
    except Exception as e:
        _RSS_FAIL_CACHE[feed_url] = _time.time()
        print(f"[RSS] {source} 取得失敗: {e}", flush=True)
        return []

def fetch_feed_group(feeds_by_category, category, article_type, per_feed_limit=3):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    feeds = feeds_by_category.get(category, [])
    if not feeds:
        return []
    items = []
    with ThreadPoolExecutor(max_workers=min(len(feeds), 6)) as executor:
        futures = [executor.submit(fetch_rss, f["url"], f["source"], per_feed_limit, article_type) for f in feeds]
        for future in as_completed(futures):
            items += future.result()
    return items

def get_official_x_candidates(category, limit=2):
    candidates = []
    for account in OFFICIAL_X_ACCOUNTS.get(category, [])[:limit]:
        handle = account["handle"]
        topics = account.get("topics", "公式発表、サービス更新、速報")
        title = f"{account['name']} 公式X: {topics}の速報を確認"
        url = f"https://x.com/search?q=from%3A{handle}&src=typed_query&f=live"
        summary = f"@{handle} の最新投稿検索。{topics}など、公式発表に近い速報を確認するための候補です。"
        article = build_article(
            title,
            url,
            f"公式X: @{handle}",
            datetime.now(timezone.utc).isoformat(),
            article_type="official_x",
            summary=summary,
        )
        article["published"] = "最新"
        candidates.append(article)
    return candidates

def is_english(text):
    text = (text or "").strip()
    if not text:
        return False
    latin_count = sum(1 for c in text if ("A" <= c <= "Z") or ("a" <= c <= "z"))
    jp_count = sum(1 for c in text if "\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff")
    if jp_count >= 4 and jp_count / max(latin_count + jp_count, 1) >= 0.25:
        return False
    return latin_count >= 8 and latin_count > jp_count

def needs_translation(article):
    return (
        is_english(article.get("title", ""))
        or is_english(article.get("summary", ""))
        or article.get("type") in ("github_release", "docs_update")
    )

TRANSLATE_PROMPT_BASE = (
    "以下のIT記事候補を、ユーザーが選びやすい日本語表示にしてください。\n"
    "ルール:\n"
    "- 企業名・サービス名・製品名・人名は英語のまま残す（例: Apple, Meta, Tesla, ChatGPT, AWS）\n"
    "- 技術用語は一般的な日本語訳を使う\n"
    "- GitHub Releasesのタイトルは、リポジトリ名とバージョンを残しつつ「何のリリースか」が分かる日本語にする\n"
    "- summary_ja は80文字以内で、内容や変更点が分かる説明にする\n"
    "- JSON配列のみを返す。説明文やMarkdownは不要\n"
    '- 各要素は {"index": 数字, "title_ja": 文字列, "summary_ja": 文字列} の形にする\n\n'
)
_TRANSLATION_CACHE = {}

def _translate_batch(items_in):
    """items_in リストをAPIで翻訳し、結果リストを返す。失敗時は空リスト"""
    prompt = TRANSLATE_PROMPT_BASE + json.dumps(items_in, ensure_ascii=False)
    body = {
        "model": "claude-haiku-4-5",
        "max_tokens": 2200,
        "messages": [{"role": "user", "content": prompt}]
    }
    req = Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urlopen(req, timeout=20) as res:
        result = json.loads(res.read())
    text = result["content"][0]["text"].strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    if not text.startswith("["):
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            text = match.group(0)
    return json.loads(text)

def translate_titles(articles):
    if not API_KEY:
        return articles
    targets = [
        (i, a)
        for i, a in enumerate(articles)
        if needs_translation(a)
    ][:20]  # 返却候補20件分を日本語表示に変換
    if not targets:
        return articles

    uncached_targets = []
    for idx, article in targets:
        cache_key = (article.get("title", ""), article.get("summary", ""))
        cached = _TRANSLATION_CACHE.get(cache_key)
        if cached:
            title_ja, summary_ja = cached
            if title_ja:
                articles[idx]["title_en"] = articles[idx]["title"]
                articles[idx]["title"] = title_ja
            if summary_ja:
                articles[idx]["summary_en"] = articles[idx].get("summary", "")
                articles[idx]["summary"] = summary_ja
        else:
            uncached_targets.append((idx, article, cache_key))
    targets = [(idx, article) for idx, article, _ in uncached_targets]
    if not targets:
        print("[翻訳] キャッシュを使用", flush=True)
        return articles

    # 小さめのバッチで翻訳漏れを減らす
    from concurrent.futures import ThreadPoolExecutor as _TPE
    BATCH_SIZE = 5
    batches = [targets[i:i+BATCH_SIZE] for i in range(0, len(targets), BATCH_SIZE)]

    def _do_batch(batch_idx_items):
        batch_no, batch = batch_idx_items
        items_in = [
            {
                "index": idx,
                "title": article.get("title", ""),
                "summary": article.get("summary", ""),
                "type": article.get("typeLabel", ""),
                "source": article.get("source", ""),
            }
            for idx, article in batch
        ]
        try:
            result = _translate_batch(items_in)
            print(f"[翻訳] バッチ {batch_no+1}: {len(batch)}件完了", flush=True)
            return result
        except Exception as e:
            print(f"[翻訳] バッチ {batch_no+1} 失敗: {e}", flush=True)
            return []

    translated_all = []
    with _TPE(max_workers=len(batches)) as ex:
        for result in ex.map(_do_batch, enumerate(batches)):
            translated_all += result

    def _apply_translations(translated_items, target_pairs):
        applied = set()
        target_map = {idx: article for idx, article in target_pairs}
        for item in translated_items:
            orig_idx = item.get("index")
            if not isinstance(orig_idx, int) or orig_idx < 0 or orig_idx >= len(articles):
                continue
            title_ja = (item.get("title_ja") or "").strip()
            summary_ja = (item.get("summary_ja") or "").strip()
            if title_ja:
                articles[orig_idx]["title_en"] = articles[orig_idx]["title"]
                articles[orig_idx]["title"] = title_ja
            if summary_ja:
                articles[orig_idx]["summary_en"] = articles[orig_idx].get("summary", "")
                articles[orig_idx]["summary"] = summary_ja
            original = target_map.get(orig_idx)
            if original:
                _TRANSLATION_CACHE[(original.get("title", ""), original.get("summary", ""))] = (title_ja, summary_ja)
            applied.add(orig_idx)
        return applied

    applied = _apply_translations(translated_all, targets)
    missing_targets = [
        (idx, article)
        for idx, article in targets
        if idx not in applied and needs_translation(articles[idx])
    ]
    if missing_targets:
        print(f"[翻訳] 漏れ {len(missing_targets)}件を再試行", flush=True)
        retry_results = []
        retry_batches = [missing_targets[i:i+3] for i in range(0, len(missing_targets), 3)]
        with _TPE(max_workers=min(len(retry_batches), 3)) as ex:
            for result in ex.map(_do_batch, enumerate(retry_batches)):
                retry_results += result
        applied |= _apply_translations(retry_results, missing_targets)

    for idx, article in targets:
        if idx not in applied and article.get("type") == "github_release":
            repo = article.get("source", "").replace("GitHub Releases: ", "")
            version = article.get("title", "").replace(repo, "").strip()
            if repo and version:
                articles[idx]["title_en"] = article.get("title", "")
                articles[idx]["title"] = f"{repo} の {version} リリース"
                _TRANSLATION_CACHE[(article.get("title", ""), article.get("summary", ""))] = (
                    articles[idx]["title"],
                    article.get("summary", ""),
                )

    print(f"[翻訳] 計{len(targets)}件を日本語表示に変換完了", flush=True)
    return articles

def get_articles(category, lang, limit=10, include_x=False, recent_days=None, translate=True):
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed

    feeds = RSS_FEEDS.get(category, RSS_FEEDS["AI・機械学習"])
    jp_sources = set(JP_PRIORITY_SOURCES)

    def _is_jp_source(source):
        return any(jp in source for jp in jp_sources)

    # RSS / GitHub Releases / Docs更新 をすべて同時並列フェッチ
    def _fetch_rss(feed, article_type=None):
        lim = 3 if feed["source"].startswith("arxiv") else RSS_PER_FEED_LIMIT
        items = fetch_rss(feed["url"], feed["source"], limit=lim, article_type=article_type)
        return "jp" if _is_jp_source(feed["source"]) else "other", items

    def _fetch_group(feed, article_type, per_limit):
        items = fetch_rss(feed["url"], feed["source"], limit=per_limit, article_type=article_type)
        return "special", items

    all_tasks = (
        [(feed, None) for feed in feeds]
        + [(feed, "github_release") for feed in GITHUB_RELEASE_FEEDS.get(category, [])]
        + [(feed, "docs_update")   for feed in DOCS_UPDATE_FEEDS.get(category, [])]
    )

    jp_items, other_items, special_items = [], [], []
    days_limit = recent_days if recent_days is not None else RECENT_DAYS

    def _store_items(tag, items):
        if tag == "jp":
            jp_items.extend(items)
        elif tag == "special":
            special_items.extend(items)
        else:
            other_items.extend(items)

    def _recent_candidate_count():
        seen = set()
        count = 0
        for article in jp_items + special_items + other_items:
            url = article.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            age_days = article_age_days(article)
            if article.get("type") == "official_x" or (age_days is not None and age_days <= days_limit):
                count += 1
        return count

    executor = ThreadPoolExecutor(max_workers=12)
    futures = {}
    processed = set()
    try:
        for feed, atype in all_tasks:
            if atype in ("github_release", "docs_update"):
                futures[executor.submit(_fetch_group, feed, atype, SPECIAL_PER_FEED_LIMIT)] = atype
            else:
                futures[executor.submit(_fetch_rss, feed)] = "rss"
        started_at = _time.monotonic()
        try:
            completed_iter = as_completed(futures, timeout=RSS_FETCH_FAST_BUDGET)
            for future in completed_iter:
                tag, items = future.result()
                processed.add(future)
                _store_items(tag, items)
        except TimeoutError:
            pass

        pending = [future for future in futures if future not in processed and not future.done()]
        if pending and _recent_candidate_count() < limit:
            remaining_budget = max(0.0, RSS_FETCH_MAX_BUDGET - (_time.monotonic() - started_at))
            if remaining_budget > 0:
                try:
                    for future in as_completed(pending, timeout=remaining_budget):
                        tag, items = future.result()
                        processed.add(future)
                        _store_items(tag, items)
                except TimeoutError:
                    pass

        skipped = sum(1 for f in futures if f not in processed and not f.done())
        if skipped:
            print(f"[RSS] 取得予算超過: 未完了{skipped}件をスキップ", flush=True)
        for future in futures:
            if future.done():
                continue
            future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    # 予算内に完了したが、as_completedのタイムアウト直後にdoneになったものを拾う
    for future in futures:
        if future in processed:
            continue
        if future.done() and not future.cancelled():
            try:
                tag, items = future.result()
            except Exception:
                continue
            _store_items(tag, items)

    if include_x:
        special_items += get_official_x_candidates(category, limit=2)

    all_items = (jp_items + special_items + other_items) if lang == "jp" else (special_items + other_items + jp_items)
    seen = set()
    unique = []
    for a in all_items:
        if a["url"] not in seen:
            seen.add(a["url"])
            a["ageDays"] = article_age_days(a)
            unique.append(a)
    def _article_sort_key(a):
        return (
            0 if (a.get("type") in ("github_release", "docs_update", "official_x")) else (
                0 if (lang == "jp" and _is_jp_source(a.get("source", ""))) else
                0 if (lang != "jp" and not _is_jp_source(a.get("source", ""))) else
                1
            ),
            -a.get("sortTime", 0),
            -a.get("trustScore", 0),
        )

    unique.sort(key=_article_sort_key)
    recent = [
        a for a in unique
        if a.get("type") == "official_x" or (a.get("ageDays") is not None and a["ageDays"] <= days_limit)
    ]
    unique = recent
    unique.sort(key=_article_sort_key)
    type_caps = {
        "github_release": 3,
        "docs_update": 3,
        "official_x": 2 if include_x else 0,
        "official_blog": 8,
        "rss_news": limit,  # per_source制御で多様性を担保するためtype上限は緩める
    }
    MAX_PER_SOURCE = 2  # 同一ソースの占有を防ぐ（原則最大2件）
    type_counts = {}
    source_counts = {}
    articles = []
    selected_urls = set()

    def _add(pool, src_cap):
        """pool から src_cap 以内で記事を追加。limit に達したら終了"""
        for article in pool:
            if len(articles) >= limit:
                break
            url = article.get("url", "")
            if url in selected_urls:
                continue
            article_type = article.get("type", "rss_news")
            source = article.get("source", "")
            if type_counts.get(article_type, 0) >= type_caps.get(article_type, limit):
                continue
            if source_counts.get(source, 0) >= src_cap:
                continue
            articles.append(article)
            selected_urls.add(url)
            type_counts[article_type] = type_counts.get(article_type, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1

    fresh_pool = [
        article for article in unique
        if article.get("type") == "official_x"
        or article.get("ageDays") is None
        or article.get("ageDays") <= days_limit
    ]

    _add(fresh_pool, 1)             # 第1パス: 直近記事から各ソース1件ずつ
    if len(articles) < limit:
        _add(fresh_pool, MAX_PER_SOURCE)  # 第2パス: 直近記事の2件目まで許可
    if len(articles) < limit:
        _add(fresh_pool, MAX_PER_SOURCE + 1)  # 第3パス: 足りない時だけ3件目を許可
    if len(articles) < limit:
        _add(fresh_pool, MAX_PER_SOURCE + 2)  # 第4パス: 期間内候補で20件を優先
    if len(articles) < limit:
        _add(unique, MAX_PER_SOURCE)
    if len(articles) < min(limit, 12):
        _add(unique, limit)  # 候補不足時だけ上限を緩和
    if translate:
        articles = translate_titles(articles)
    return articles


HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IT記事 投稿ジェネレーター</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; color: #1a1a1a; min-height: 100vh; padding: 2rem 1rem; }
  .container { max-width: 680px; margin: 0 auto; }
  h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .subtitle { font-size: 13px; color: #888; margin-bottom: 1.5rem; }
  .section-label { font-size: 11px; font-weight: 600; color: #888; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 8px; margin-top: 4px; }
  .btn-group { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 1.25rem; }
  .card { background: #fff; border-radius: 12px; border: 1px solid #e5e5e5; padding: 1.25rem; margin-bottom: 1rem; }
  .gen-btn { font-size: 14px; padding: 10px 18px; border-radius: 10px; border: none; background: #1a1a1a; color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; width: 100%; font-weight: 500; transition: opacity .15s; margin-bottom: 1.25rem; }
  .gen-btn:hover { opacity: .85; }
  .gen-btn:disabled { opacity: .4; cursor: not-allowed; }
  .source-options { display: flex; flex-wrap: wrap; gap: 10px; margin: .5rem 0 .75rem; }
  .source-toggle { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; color: #555; background: #fff; border: 1px solid #e5e5e5; border-radius: 10px; padding: 8px 11px; cursor: pointer; user-select: none; }
  .source-toggle:hover { border-color: #bbb; }
  .source-toggle input { width: 14px; height: 14px; accent-color: #1a1a1a; }
  .source-hint { font-size: 11px; color: #aaa; align-self: center; }
  .divider { height: 1px; background: #e5e5e5; margin: 0 0 1.25rem; }
  .error-box { background: #fff0f0; border: 1px solid #fcc; border-radius: 8px; padding: .75rem 1rem; font-size: 13px; color: #c00; display: none; margin-bottom: 1rem; }
  .status-bar { font-size: 13px; color: #888; display: none; align-items: center; gap: 8px; margin-bottom: 1rem; }
  .spinner { width: 14px; height: 14px; border: 2px solid #ddd; border-top-color: #1a1a1a; border-radius: 50%; animation: spin .7s linear infinite; flex-shrink: 0; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .skel { background: #f0f0f0; border-radius: 4px; animation: pulse 1.4s ease-in-out infinite; height: 12px; margin-bottom: 8px; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
  .skel-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 1rem; margin-bottom: 8px; }
  .cand-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 1rem; margin-bottom: 8px; cursor: pointer; display: flex; gap: 12px; align-items: flex-start; transition: border-color .15s; }
  .cand-card:hover { border-color: #bbb; }
  .cand-card.selected { border: 2px solid #1a1a1a; }
  .cand-num { font-size: 12px; font-weight: 600; color: #aaa; flex-shrink: 0; padding-top: 2px; min-width: 16px; }
  .cand-body { flex: 1; min-width: 0; }
  .cand-title { font-size: 14px; font-weight: 500; line-height: 1.4; margin-bottom: 4px; }
  .cand-summary { font-size: 12px; line-height: 1.45; color: #666; margin: 6px 0 2px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .cand-meta { font-size: 12px; color: #aaa; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .cand-meta a { color: #2563eb; text-decoration: none; }
  .cand-meta a:hover { text-decoration: underline; }
  .trust-badge { font-size: 11px; padding: 2px 7px; border-radius: 100px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
  .article-link-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .article-link-btn { font-size: 12px; padding: 5px 10px; border-radius: 8px; border: 1px solid #ddd; background: #fff; color: #1a1a1a; text-decoration: none; line-height: 1; }
  .article-link-btn:hover { background: #f5f5f5; text-decoration: none; }
  .article-link-btn.translate { border-color: #bfdbfe; background: #eff6ff; color: #2563eb; }
  .article-link-btn.translate:hover { background: #dbeafe; }
  .cand-check { width: 18px; height: 18px; border-radius: 50%; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; margin-top: 2px; }
  .cand-card.selected .cand-check { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
  .sticky-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #fff; border-top: 1px solid #e5e5e5; padding: .75rem 1rem; display: none; z-index: 100; box-shadow: 0 -4px 16px rgba(0,0,0,.08); }
  .sticky-bar-inner { max-width: 680px; margin: 0 auto; display: flex; align-items: center; gap: 12px; }
  .sticky-article-title { font-size: 13px; color: #555; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sticky-gen-btn { font-size: 14px; padding: 10px 20px; border-radius: 10px; border: none; background: #1a1a1a; color: #fff; cursor: pointer; font-weight: 500; white-space: nowrap; flex-shrink: 0; }
  .sticky-gen-btn:hover { opacity: .85; }
  .sticky-gen-btn:disabled { opacity: .4; cursor: not-allowed; }
  body.has-sticky { padding-bottom: 72px; }
  .more-btn { font-size: 13px; padding: 8px 14px; border-radius: 10px; border: 1px solid #ddd; background: #fff; color: #1a1a1a; cursor: pointer; width: 100%; margin: 8px 0 10px; display: none; }
  .more-btn:hover { background: #f5f5f5; }
  .select-btn { font-size: 14px; padding: 9px 18px; border-radius: 10px; border: 1px solid #ddd; background: #fff; color: #1a1a1a; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; width: 100%; transition: all .15s; margin-bottom: 1.25rem; }
  .select-btn:hover { background: #f5f5f5; }
  .select-btn:disabled { opacity: .4; cursor: not-allowed; }
  .result-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 1.25rem; display: none; margin-bottom: 1rem; }
  .badge { font-size: 11px; font-weight: 500; padding: 3px 9px; border-radius: 100px; background: #f0f0f0; color: #666; display: inline-block; margin-right: 4px; margin-bottom: 10px; }
  .badge.lang { background: #eff6ff; color: #2563eb; }
  .article-meta { font-size: 12px; color: #aaa; margin-bottom: 6px; }
  .article-title { font-size: 15px; font-weight: 500; line-height: 1.4; margin-bottom: 12px; }
  .article-title a { color: inherit; text-decoration: none; }
  .article-title a:hover { text-decoration: underline; }
  .tweet-label { font-size: 11px; font-weight: 600; color: #888; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 6px; }
  .tweet-box { background: #f9f9f9; border-radius: 8px; padding: 1rem; font-size: 14px; line-height: 1.65; white-space: pre-wrap; word-break: break-all; margin-bottom: 6px; outline: none; min-height: 80px; border: 1px solid transparent; }
  .tweet-box:focus { border-color: #ddd; }
  .char-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .char-count { font-size: 12px; color: #aaa; }
  .char-count.warn { color: #f59e0b; }
  .char-count.over { color: #ef4444; }
  .shorten-btn { font-size: 12px; padding: 4px 10px; border-radius: 8px; border: 1px solid #f59e0b; color: #b45309; background: #fffbeb; cursor: pointer; display: none; align-items: center; gap: 4px; }
  .action-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .action-btn { font-size: 13px; padding: 9px 16px; border-radius: 8px; border: 1px solid #ddd; cursor: pointer; display: flex; align-items: center; gap: 6px; background: #fff; color: #1a1a1a; transition: all .15s; }
  .action-btn:hover { background: #f5f5f5; }
  .x-btn { background: #1a1a1a; color: #fff; border-color: #1a1a1a; margin-left: auto; font-weight: 500; }
  .x-btn:hover { opacity: .85; }
  .history-section { margin-top: 1.75rem; border-top: 1px solid #e5e5e5; padding-top: 1.25rem; display: none; }
  .history-item { font-size: 13px; color: #888; padding: 7px 0; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; gap: 8px; cursor: pointer; }
  .history-item:hover .hi-title { color: #1a1a1a; }
  .hi-slot { font-size: 11px; color: #bbb; flex-shrink: 0; }
  .hi-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hi-time { font-size: 11px; color: #bbb; flex-shrink: 0; }
  .rss-badge { font-size: 10px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; border-radius: 100px; padding: 2px 8px; display: inline-block; margin-left: 8px; }
</style>
</head>
<body>
<div class="container">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.2rem">
    <h1 style="margin:0">📰 IT記事 投稿ジェネレーター <span class="rss-badge">複数ソース版</span></h1>
    <a href="/logout" style="font-size:.75rem;color:#999;text-decoration:none;border:1px solid #e5e5e5;border-radius:8px;padding:4px 10px;white-space:nowrap">ログアウト</a>
  </div>
  <p class="subtitle">RSS / GitHub Releases / Docs更新から候補を取得。必要な時だけ公式Xも追加</p>

  <div class="section-label">カテゴリ</div>
  <div class="btn-group" id="catGroup"></div>

  <div class="section-label">言語</div>
  <div class="btn-group" id="langGroup"></div>

  <div class="source-options">
    <label class="source-toggle">
      <input type="checkbox" id="includeX">
      <span>公式Xも見る</span>
    </label>
    <span class="source-hint">速報チェック用。通常はオフがおすすめ</span>
    <label class="source-toggle" style="margin-left:8px">
      <span style="color:#888;font-size:12px">期間：</span>
      <select id="recentDays" style="font-size:13px;border:none;background:transparent;color:#555;cursor:pointer;outline:none">
        <option value="0" selected>今日</option>
        <option value="1">1日以内</option>
        <option value="3">3日以内</option>
        <option value="7">1週間以内</option>
      </select>
    </label>
  </div>
  <button class="gen-btn" id="generateBtn">📡 複数ソースから候補を取得</button>
  <div class="divider"></div>

  <div class="error-box" id="errorBox"></div>
  <div class="status-bar" id="statusBar"><div class="spinner"></div><span id="statusText"></span></div>
  <div id="loadingSkels" style="display:none"></div>

  <div id="opinionPanel" style="display:none;background:#fff;border:1px solid #e5e5e5;border-radius:12px;padding:1rem;margin:0 0 12px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <span class="section-label" style="margin:0">感想スタイル</span>
      <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:#555;cursor:pointer">
        <input type="checkbox" id="includeOpinion" checked style="width:14px;height:14px;accent-color:#1a1a1a">
        <span>感想を含める</span>
      </label>
    </div>
    <div id="opinionStyleRow" style="display:flex;gap:8px;flex-wrap:wrap"></div>
  </div>

  <div id="candidatesSection" style="display:none;margin-bottom:1.25rem">
    <div class="section-label">記事を選んでください</div>
    <div id="candidatesList"></div>
    <button class="more-btn" id="moreBtn">もっと見る</button>
  </div>

  <div class="sticky-bar" id="stickyBar">
    <div class="sticky-bar-inner">
      <span class="sticky-article-title" id="stickyTitle">記事を選択してください</span>
      <button class="sticky-gen-btn" id="selectBtn" disabled>✏️ 投稿文を生成</button>
    </div>
  </div>

  <div class="result-card" id="resultCard">
    <div id="resultHeader"></div>
    <div class="article-meta" id="articleMeta"></div>
    <div class="article-title" id="articleTitle"></div>
    <div class="tweet-label">投稿文（編集可）</div>
    <div class="tweet-box" id="tweetBox" contenteditable="true"></div>
    <div class="char-row">
      <span class="char-count" id="charCount">0 / 280文字</span>
      <button class="shorten-btn" id="shortenBtn">✂️ 自動短縮</button>
    </div>
    <div class="action-row">
      <button class="action-btn" id="backBtn">← 選び直す</button>
      <button class="action-btn" id="copyBtn">📋 コピー</button>
      <button class="action-btn x-btn" id="xBtn">X で投稿</button>
    </div>
  </div>

  <div class="history-section" id="historySection">
    <div class="section-label">今日の投稿履歴</div>
    <div id="historyList"></div>
  </div>
</div>

<script>
const CATS=['AI・機械学習','クラウド・AWS','セキュリティ','開発','スタートアップ','便利ツール・Tips','ガジェット・ハードウェア','ビジネス・DX'];

const OPINION_STYLES=[
  {k:'impression', l:'💬 一言感想', desc:'「個人的にここが面白い」「これは要注目」など短く添える'},
  {k:'question',   l:'🤔 問いかけ', desc:'「皆さんはどう思いますか？」など読者に投げかける'},
  {k:'practical',  l:'🔧 実務目線', desc:'「現場ではこう使えそう」「エンジニア視点だとここがポイント」'},
  {k:'concern',    l:'⚠️ 懸念・考察', desc:'「一方でこんなリスクも」「まだ課題はあるが」など深掘り'},
];
let activeOpinionStyle='impression';
let activeCat='AI・機械学習', activeLang='jp';
const INITIAL_VISIBLE_COUNT=20;
let candidates=[], selectedIdx=-1, postHistory=[], tags=[], visibleCount=INITIAL_VISIBLE_COUNT;

function el(id){return document.getElementById(id);}
function getTags(){return tags.filter(t=>t.on).map(t=>t.t).join(' ');}

function pillStyle(active){
  return active
    ?'font-size:13px;padding:7px 18px;border-radius:100px;border:none;background:#1a1a1a;color:#fff;cursor:pointer;font-weight:500;line-height:1.4'
    :'font-size:13px;padding:7px 18px;border-radius:100px;border:1px solid #ddd;background:#fff;color:#888;cursor:pointer;line-height:1.4';
}

function renderCats(){
  el('catGroup').innerHTML=CATS.map(c=>`<button onclick="setCat('${c}')" style="${pillStyle(activeCat===c)}">${c}</button>`).join('');
}
function renderLangs(){
  el('langGroup').innerHTML=[{k:'jp',l:'🇯🇵 国内優先'},{k:'en',l:'🌐 海外優先'}].map(l=>`<button onclick="setLang('${l.k}')" style="${pillStyle(activeLang===l.k)}">${l.l}</button>`).join('');
}
function renderOpinionStyles(){
  const includeOpinion=el('includeOpinion')&&el('includeOpinion').checked;
  el('opinionStyleRow').style.display=includeOpinion?'flex':'none';
  el('opinionStyleRow').innerHTML=OPINION_STYLES.map(s=>`<button onclick="setOpinionStyle('${s.k}')" title="${s.desc}" style="${pillStyle(activeOpinionStyle===s.k)}">${s.l}</button>`).join('');
}
function setOpinionStyle(k){activeOpinionStyle=k;renderOpinionStyles();}

document.addEventListener('change',e=>{if(e.target.id==='includeOpinion')renderOpinionStyles();});

function setCat(c){activeCat=c;renderCats();}
function setLang(l){activeLang=l;renderLangs();}

function setStatus(on,txt){el('statusText').textContent=txt||'';el('statusBar').style.display=on?'flex':'none';}
function showError(msg){const eb=el('errorBox');eb.textContent=msg;eb.style.display='block';setTimeout(()=>eb.style.display='none',6000);}
function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}

async function fetchCandidatesWithRetry(category, lang, includeX, days){
  const url=`/api/rss?category=${encodeURIComponent(category)}&lang=${lang}&include_x=${includeX}&days=${days}`;
  let lastError=null;
  for(let attempt=1;attempt<=3;attempt++){
    try{
      if(attempt>1)setStatus(true,`候補取得を再試行中...（${attempt}/3）`);
      const r=await fetch(url,{cache:'no-store'});
      let data=null;
      try{data=await r.json();}catch(e){throw new Error(`応答を読み取れませんでした (${r.status})`);}
      if(!r.ok||data.error)throw new Error(data.error||`HTTP ${r.status}`);
      if(data.articles&&data.articles.length)return data.articles;
      throw new Error('記事が見つかりませんでした');
    }catch(e){
      lastError=e;
      if(attempt<3)await sleep(700*attempt);
    }
  }
  throw lastError||new Error('記事が見つかりませんでした');
}

async function callProxy(messages){
  const r=await fetch('/api/claude',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({messages})
  });
  if(!r.ok){const t=await r.text();throw new Error(t);}
  return r.json();
}

function xWeightedLen(text){
  // Xの重み付き文字数カウント (twitter-text 仕様)
  // weight=1: 基本ラテン文字等 / weight=2: 日本語・CJK等
  const WEIGHT1=[
    [0x0000,0x10FF],[0x2000,0x2BFF],[0x2E00,0x2EFF],
    [0xFB50,0xFDFF],[0xFE70,0xFEFF]
  ];
  let len=0;
  for(const ch of text){
    const cp=ch.codePointAt(0);
    len+=WEIGHT1.some(([s,e])=>cp>=s&&cp<=e)?1:2;
  }
  return len;
}

function updateChar(){
  const text=el('tweetBox').innerText;
  const urlRegex=/https?:\/\/[^\s]+/g;
  const urls=text.match(urlRegex)||[];
  const textWithoutUrls=text.replace(urlRegex,'');
  const len=xWeightedLen(textWithoutUrls)+urls.length*23;
  const remaining=280-len;
  el('charCount').textContent=`${len} / 280（残り ${remaining}）※日本語2・URL=23`;
  el('charCount').className='char-count'+(len>280?' over':len>260?' warn':'');
  el('xBtn').disabled=len>280;
  el('shortenBtn').style.display=len>280?'inline-flex':'none';
}
el('tweetBox').oninput=updateChar;

function shareArticleUrl(article){
  if(!article.url)return '';
  return article.url;
}

function escapeHtml(value){
  return String(value||'').replace(/[&<>"']/g,ch=>({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  }[ch]));
}

function renderCands(){
  const visibleCandidates=candidates.slice(0, visibleCount);
  el('candidatesList').innerHTML=visibleCandidates.map((a,i)=>{
    const sel=selectedIdx===i;
    const title=escapeHtml(a.title);
    const summary=escapeHtml(a.summary);
    const source=escapeHtml(a.source);
    const published=escapeHtml(a.published);
    const typeLabel=escapeHtml(a.typeLabel||'RSSニュース');
    const url=escapeHtml(a.url);
    return `<div class="cand-card${sel?' selected':''}" onclick="selectCand(${i})">
      <div class="cand-num">${i+1}</div>
      <div class="cand-body">
        <div class="cand-title">${title}</div>
        ${summary?`<div class="cand-summary">${summary}</div>`:''}
        <div class="cand-meta">
          <span>${source}</span><span>${published}</span>
          <span class="trust-badge">${typeLabel}・信頼度${a.trustScore||70}</span>
        </div>
        ${a.url?`<div class="article-link-row">
          <a class="article-link-btn" href="${url}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">参照URLを開く</a>
        </div>`:''}
      </div>
      <div class="cand-check">${sel?'✓':''}</div>
    </div>`;
  }).join('');
  const remaining=Math.max(candidates.length-visibleCount,0);
  el('moreBtn').style.display=remaining>0?'block':'none';
  el('moreBtn').textContent=`もっと見る（残り${remaining}件）`;
}

function selectCand(i){
  selectedIdx=i;
  el('selectBtn').disabled=false;
  // スティッキーバー更新
  el('stickyBar').style.display='block';
  el('stickyTitle').textContent=candidates[i]?.title||'';
  document.body.classList.add('has-sticky');
  renderCands();
}

async function translateCandidatesInBackground(){
  if(!candidates.length)return;
  setStatus(true,'候補を日本語表示に更新中...');
  try{
    const r=await fetch('/api/translate_candidates',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({articles:candidates})
    });
    const data=await r.json();
    if(data.articles&&data.articles.length){
      const selectedUrl=selectedIdx>=0?candidates[selectedIdx]?.url:null;
      candidates=data.articles;
      if(selectedUrl){
        selectedIdx=candidates.findIndex(a=>a.url===selectedUrl);
      }
      renderCands();
    }
  }catch(e){
    console.warn('候補翻訳失敗', e);
  }finally{
    setStatus(false);
  }
}

el('moreBtn').onclick=()=>{
  visibleCount=Math.min(visibleCount+INITIAL_VISIBLE_COUNT,candidates.length);
  renderCands();
};

function setFetching(on){
  // カテゴリ・言語ボタンをすべてロック／アンロック
  el('catGroup').querySelectorAll('button').forEach(b=>{ b.disabled=on; b.style.opacity=on?'0.4':''; b.style.pointerEvents=on?'none':''; });
  el('langGroup').querySelectorAll('button').forEach(b=>{ b.disabled=on; b.style.opacity=on?'0.4':''; b.style.pointerEvents=on?'none':''; });
  el('includeX').disabled=on;
  el('recentDays').disabled=on;
}

el('generateBtn').onclick=async()=>{
  el('errorBox').style.display='none';
  el('resultCard').style.display='none';
  el('candidatesSection').style.display='none';
  el('loadingSkels').style.display='block';
  el('loadingSkels').innerHTML=Array.from({length:5}).map(()=>`<div class="skel-card"><div class="skel" style="width:60%"></div><div class="skel" style="width:95%"></div><div class="skel" style="width:80%"></div></div>`).join('');
  el('generateBtn').disabled=true;
  el('generateBtn').innerHTML='<div class="spinner"></div>取得中...';
  selectedIdx=-1;visibleCount=INITIAL_VISIBLE_COUNT;el('selectBtn').disabled=true;
  el('opinionPanel').style.display='none';
  el('stickyBar').style.display='none';
  document.body.classList.remove('has-sticky');
  setFetching(true);
  setStatus(true,'複数ソースから候補を取得中...');
  try{
    const includeX=el('includeX').checked?'1':'0';
    const days=el('recentDays').value;
    candidates=await fetchCandidatesWithRetry(activeCat,activeLang,includeX,days);
    el('loadingSkels').style.display='none';
    setStatus(false);
    setFetching(false);
    el('generateBtn').disabled=false;
    el('generateBtn').innerHTML='📡 複数ソースから候補を取得';
    el('candidatesSection').style.display='block';
    el('opinionPanel').style.display='block';
    renderOpinionStyles();
    renderCands();
    translateCandidatesInBackground();
  }catch(e){
    el('loadingSkels').style.display='none';
    setStatus(false);
    setFetching(false);
    el('generateBtn').disabled=false;
    el('generateBtn').innerHTML='📡 複数ソースから候補を取得';
    showError('取得に失敗: '+e.message);
  }
};

el('selectBtn').onclick=async()=>{
  if(selectedIdx<0)return;
  const art=candidates[selectedIdx];
  const shareUrl=shareArticleUrl(art);
  el('selectBtn').disabled=true;
  el('selectBtn').innerHTML='<div class="spinner"></div>生成中...';
  setStatus(true,'記事本文を取得中...');
  const today=new Date().toLocaleDateString('ja-JP',{year:'numeric',month:'long',day:'numeric'});
  try{
    // 記事本文を取得（失敗してもRSS要約にフォールバック）
    let articleBody = '';
    if(art.url && art.type !== 'official_x'){
      try{
        const br = await fetch(`/api/fetch_article?url=${encodeURIComponent(art.url)}`);
        const bd = await br.json();
        if(bd.body && bd.body.length > 100) articleBody = bd.body;
      }catch(e){ console.warn('記事取得失敗', e); }
    }
    const contextText = articleBody
      ? `記事本文（抜粋）:\n${articleBody}`
      : `RSS概要: ${art.summary||'概要なし'}`;

    // 記事に合ったハッシュタグを自動生成
    setStatus(true,'ハッシュタグを生成中...');
    try{
      const tagSource = articleBody || art.summary || art.title;
      const tagData = await callProxy([{role:'user',content:`以下のIT記事に最適な日本語ハッシュタグを重要度順に3つだけ提案してください。
記事タイトル: ${art.title}
内容: ${tagSource.slice(0,400)}
ルール:
- 必ず # から始める
- 日本語または一般的な英語技術用語（例: #AI #AWS #React）
- 記事の具体的な内容を最もよく表すタグを優先（汎用すぎる #テック だけにしない）
- 必ず3つ、JSON配列のみ返す。例: ["#生成AI","#LLM","#OpenAI"]`}]);
      let tagText = tagData.text.trim().replace(/^```(?:json)?\s*|\s*```$/g,'').trim();
      const newTags = JSON.parse(tagText);
      if(Array.isArray(newTags) && newTags.length){
        // 既存タグを新しいタグで置き換え（重複除去・最大3つ）
        const seen = new Set();
        tags = newTags.filter(t=>typeof t==='string'&&t.startsWith('#')).slice(0,3).map(t=>{
          const cleaned = t.trim().replace(/^#\s+/, '#').replace(/\s+/g, '');
          if(seen.has(cleaned)) return null;
          seen.add(cleaned);
          return {t:cleaned, on:true};
        }).filter(Boolean);
      }
    }catch(e){ console.warn('ハッシュタグ生成失敗', e); }

    setStatus(true,'投稿文を生成中...');
    // XはURLを常に23文字としてカウントする。本文+ハッシュタグを117文字以内に収める
    const includeOpinion=el('includeOpinion').checked;
    const opinionStyleMap={
      impression: articleBody
        ? `記事本文を読んだうえで、特に印象的な事実・数字・技術名を1つ具体的に引用し「〜が面白い」「〜は要注目」など筆者の感想として1文添える。抽象的な表現（「興味深い」「注目です」だけ）は避ける。`
        : '記事タイトルから読み取れる特徴的な点に触れ、「〜が面白い」「〜は要注目」など1文添える。',
      question: articleBody
        ? `記事本文の具体的な内容（機能名・数値・変化）を踏まえ、「〜を使ってみた方いますか？」「あなたの現場では〜はどう変わりそう？」など読者が答えやすい具体的な問いかけを1文添える。`
        : '記事テーマに関連した読者への問いかけを1文添える（「皆さんはどう思いますか？」など）。',
      practical: articleBody
        ? `記事本文から具体的な機能・変更点・数値を1つ取り上げ、「〜があれば現場で〇〇できそう」「〜はエンジニアにとって△△がポイント」など即実務に結びつく視点で1文添える。`
        : '実務・エンジニア目線で「現場ではこう使えそう」「ここが実用上のポイント」など1文添える。',
      concern: articleBody
        ? `記事本文の内容に基づき、「〜という点はまだ課題」「〜が普及するには〇〇が必要では」など根拠のある懸念・考察を1文添える。感情的・否定的にならず建設的なトーンで。`
        : '「一方でこんなリスクも」「まだ課題はあるが」など懸念や考察を1文添える。',
    };
    const opinionInstruction=includeOpinion
      ? `\n\n【感想の書き方（厳守）】\nスタイル: ${opinionStyleMap[activeOpinionStyle]||opinionStyleMap.impression}\n- 記事本文の具体的な情報を必ず1つ使うこと\n- 「興味深いです」「注目です」のような抽象的な締めだけは禁止\n- 投稿本文の末尾に自然につながるよう1文で書く` : '';
    // 本文のみ生成（ハッシュタグ・URLは後付け）
    const data=await callProxy([{role:'user',content:`以下の記事についてX投稿の本文を日本語で作成してください。

【記事情報】
タイトル: ${art.title}
ソース: ${art.source}（${art.typeLabel||'RSSニュース'}）
${contextText}

【ソース種別の書き方】
- GitHub Releases: 何が変わったか・開発者への影響を具体的に1文
- Docs更新: 仕様変更・新機能・開発者への影響を具体的に1文
- 公式X: 断定しすぎず「公式Xで確認」くらいの表現
- RSSニュース/Blog: 記事の最も重要な要点を1〜2文で紹介${opinionInstruction}

【制約】
- 「速報」という言葉は絶対に使わない
- ハッシュタグ・URLは不要
- 日本語100文字以内
- 本文のみ回答`}]);

    // 本文 + ハッシュタグ + URL を組み立て
    const calcLen=(t)=>{const u=t.match(/https?:\/\/[^\s]+/g)||[];return xWeightedLen(t.replace(/https?:\/\/[^\s]+/g,''))+u.length*23;};
    let body = data.text.trim().replace(/【速報】\s*/g,'').replace(/速報[：:]\s*/g,'').replace(/速報\s/g,'');
    const hashStr = getTags() ? ' '+getTags() : '';
    const urlStr  = shareUrl  ? '\n'+shareUrl  : '';
    let tweet = body + hashStr + urlStr;

    // Step1: オーバーならハッシュタグを後ろから1つずつ削除
    const hashTags = (hashStr.trim()).split(/\s+/).filter(t=>t.startsWith('#'));
    let usedTags = [...hashTags];
    while(calcLen(tweet)>280 && usedTags.length>0){
      usedTags.pop();
      tweet = body + (usedTags.length ? ' '+usedTags.join(' ') : '') + urlStr;
    }

    // Step2: それでもオーバーなら Claude で本文を自動短縮
    if(calcLen(tweet)>280){
      setStatus(true,'文字数オーバー。本文を自動短縮中...');
      try{
        const over=calcLen(tweet);
        const shortened=await callProxy([{role:'user',content:`以下のX投稿本文が長すぎます（現在${over}カウント）。URLとハッシュタグは変えずに本文だけを短くしてください。
文字数ルール: 日本語1文字=2カウント、英数字=1カウント、URL=23カウント固定、合計280以内。
ハッシュタグ: ${usedTags.join(' ')||'なし'}
URL: ${shareUrl}
本文のみ回答してください。\n\n${body}`}]);
        const newBody=shortened.text.trim().replace(/【速報】\s*/g,'').replace(/速報[：:]\s*/g,'').replace(/速報\s/g,'');
        tweet = newBody + (usedTags.length ? ' '+usedTags.join(' ') : '') + urlStr;
      }catch(e){ console.warn('自動短縮失敗',e); }
    }
    el('resultHeader').innerHTML=`
      <span class="badge lang">${activeLang==='en'?'🌐 海外優先':'🇯🇵 国内優先'}</span>`;
    el('articleMeta').textContent=`${art.source}　${art.published}　${art.typeLabel||'RSSニュース'}・信頼度${art.trustScore||70}`;
    el('articleTitle').innerHTML=art.url?`<a href="${escapeHtml(art.url)}" target="_blank">${escapeHtml(art.title)}</a>`:escapeHtml(art.title);
    el('tweetBox').innerText=tweet;
    updateChar();
    setStatus(false);
    el('selectBtn').disabled=false;
    el('selectBtn').textContent='✏️ 投稿文を生成';
    el('candidatesSection').style.display='none';
    el('opinionPanel').style.display='none';
    el('stickyBar').style.display='none';
    document.body.classList.remove('has-sticky');
    el('resultCard').style.display='block';
    el('xBtn').onclick=()=>{
      window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(el('tweetBox').innerText)}`,'_blank');
      markPosted(art,el('tweetBox').innerText);
    };
  }catch(e){
    setStatus(false);
    el('selectBtn').disabled=false;
    el('selectBtn').textContent='✏️ 投稿文を生成';
    showError('生成に失敗: '+e.message);
  }
};

el('shortenBtn').onclick=async()=>{
  const cur=el('tweetBox').innerText;
  const calcLen2=(t)=>{const u=t.match(/https?:\/\/[^\s]+/g)||[];return xWeightedLen(t.replace(/https?:\/\/[^\s]+/g,''))+u.length*23;};
  if(calcLen2(cur)<=280)return;
  el('shortenBtn').disabled=true;setStatus(true,'短縮中...');
  try{
    const data=await callProxy([{role:'user',content:`以下のX投稿文を文字数制限内に短縮してください。ルール: 日本語1文字=2カウント、英数字1文字=1カウント、URL=23カウント固定、合計280以内。ハッシュタグとURLは全て残し自然な日本語で。投稿文のみ回答。\n\n${cur}`}]);
    el('tweetBox').innerText=data.text.trim();updateChar();
  }catch(e){showError('短縮失敗: '+e.message);}
  finally{setStatus(false);el('shortenBtn').disabled=false;}
};

el('backBtn').onclick=()=>{
  el('resultCard').style.display='none';
  el('candidatesSection').style.display='block';
  el('opinionPanel').style.display='block';
  if(selectedIdx>=0){
    el('stickyBar').style.display='block';
    document.body.classList.add('has-sticky');
  }
};

el('copyBtn').onclick=async()=>{
  try{
    await navigator.clipboard.writeText(el('tweetBox').innerText);
    el('copyBtn').textContent='✓ コピー済';
    setTimeout(()=>el('copyBtn').textContent='📋 コピー',1500);
  }catch{showError('コピーに失敗');}
};

function markPosted(art,tweet){
  const now=new Date().toLocaleTimeString('ja-JP',{hour:'2-digit',minute:'2-digit'});
  postHistory.unshift({title:art.title,tweet,time:now});
  if(postHistory.length>9)postHistory.pop();
  el('historySection').style.display='block';
  el('historyList').innerHTML=postHistory.map((h,i)=>`
    <div class="history-item" onclick="loadHistory(${i})">
      <span class="hi-title">${h.title}</span>
      <span class="hi-time">${h.time}</span>
    </div>`).join('');
}
function loadHistory(i){
  const h=postHistory[i];el('tweetBox').innerText=h.tweet;updateChar();
  el('resultCard').style.display='block';
}

renderCats();renderLangs();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[HTTP] {args}", flush=True)

    def _get_cookie(self, name):
        cookie_header = self.headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            k, _, v = part.strip().partition("=")
            if k.strip() == name:
                return v.strip()
        return None

    def _check_auth(self):
        if not BASIC_USER or not BASIC_PASS:
            return True  # 認証設定なしはスルー
        return self._get_cookie(COOKIE_NAME) == VALID_TOKEN

    def _redirect_login(self, error=False):
        page = LOGIN_HTML.replace("{error}", '<div class="error">ユーザー名またはパスワードが違います</div>' if error else "")
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _handle_login_post(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        from urllib.parse import parse_qs
        params = parse_qs(raw)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]
        if username == BASIC_USER and password == BASIC_PASS:
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", f"{COOKIE_NAME}={VALID_TOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800")
            self.end_headers()
        else:
            self._redirect_login(error=True)

    def _handle_logout(self):
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", f"{COOKIE_NAME}=; Path=/; HttpOnly; Max-Age=0")
        self.end_headers()

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/login":
            return self._redirect_login()
        if self.path == "/logout":
            return self._handle_logout()
        if not self._check_auth():
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        if self.path == "/api/status":
            self.send_json(200, {"has_key": bool(API_KEY)})
        elif self.path.startswith("/api/fetch_article"):
            from urllib.parse import urlparse, parse_qs, unquote
            params = parse_qs(urlparse(self.path).query)
            url = unquote(params.get("url", [""])[0])
            if not url:
                self.send_json(400, {"error": "url is required"})
                return
            print(f"[記事取得] {url}", flush=True)
            body_text = fetch_article_body(url)
            self.send_json(200, {"body": body_text})
        elif self.path.startswith("/api/rss"):
            from urllib.parse import urlparse, parse_qs
            try:
                params = parse_qs(urlparse(self.path).query)
                category = params.get("category", ["AI・機械学習"])[0]
                lang = params.get("lang", ["jp"])[0]
                include_x = params.get("include_x", ["0"])[0] == "1"
                days = int(params.get("days", [str(RECENT_DAYS)])[0])
                print(f"[候補取得] category={category} lang={lang} include_x={include_x} days={days}", flush=True)
                _RSS_FAIL_CACHE.clear()
                def _load_articles(target_days):
                    return get_articles(category, lang, limit=20, include_x=include_x, recent_days=target_days, translate=False)
                try:
                    articles = _load_articles(days)
                except Exception as first_error:
                    print(f"[候補取得] 初回失敗、再試行します: {first_error}", flush=True)
                    _RSS_FAIL_CACHE.clear()
                    import time as _time
                    _time.sleep(RSS_EMPTY_RETRY_DELAY)
                    articles = _load_articles(days)
                if not articles:
                    print("[候補取得] 初回0件、失敗キャッシュをクリアして再試行します", flush=True)
                    _RSS_FAIL_CACHE.clear()
                    import time as _time
                    _time.sleep(RSS_EMPTY_RETRY_DELAY)
                    articles = _load_articles(days)
                print(f"[候補取得] 取得件数={len(articles)}", flush=True)
                self.send_json(200, {"articles": articles})
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[ERROR /api/rss] {e}", flush=True)
                self.send_json(500, {"error": f"記事取得中にエラーが発生しました: {str(e)}"})
        else:
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        if self.path == "/login":
            return self._handle_login_post()
        if not self._check_auth():
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        if self.path not in ("/api/claude", "/api/translate_candidates"):
            self.send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))

        if self.path == "/api/translate_candidates":
            articles = payload.get("articles", [])
            if not isinstance(articles, list):
                self.send_json(400, {"error": "articles must be a list"})
                return
            try:
                translated = translate_titles(articles[:20])
                self.send_json(200, {"articles": translated})
            except Exception as e:
                print(f"[ERROR /api/translate_candidates] {e}", flush=True)
                self.send_json(200, {"articles": articles[:20], "warning": str(e)})
            return

        messages = payload.get("messages", [])

        if not API_KEY:
            self.send_json(500, {"error": "ANTHROPIC_API_KEY が設定されていません"})
            return

        body = {
            "model": "claude-haiku-4-5",
            "max_tokens": 800,
            "messages": messages,
        }

        req = Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as res:
                result = json.loads(res.read())
            print(f"[API] usage={result.get('usage')}", flush=True)
            text_block = next((b for b in result.get("content", []) if b.get("type") == "text"), None)
            if not text_block:
                self.send_json(500, {"error": "テキストブロックがありません"})
                return
            self.send_json(200, {"text": text_block["text"]})
        except Exception as e:
            print(f"[ERROR] {e}", flush=True)
            self.send_json(500, {"error": str(e)})


def main():
    if not API_KEY:
        print("⚠️  ANTHROPIC_API_KEY が設定されていません")
        print("   export ANTHROPIC_API_KEY=sk-ant-... を実行してから再起動してください\n")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"✅ サーバー起動: {url}")
    print(f"   モデル: claude-haiku-4-5（複数ソース版・低コスト）")
    print("   Ctrl+C で終了\n")

    if os.environ.get("PORT") is None:  # ローカルのみブラウザ自動起動
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了しました")


if __name__ == "__main__":
    main()
