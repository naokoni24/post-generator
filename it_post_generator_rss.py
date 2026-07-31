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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
import html
import re
import hmac
import hashlib
import unicodedata
import time
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

class FeedRedirectHandler(HTTPRedirectHandler):
    def http_error_307(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)

    def http_error_308(self, req, fp, code, msg, headers):
        # codeを308のまま渡すと、308を知らない古いPythonのredirect_requestが
        # HTTPErrorを送出してリダイレクトを追跡できない（例: raycast.com→www）。
        # 挙動が同等の307として処理させる。
        return self.http_error_302(req, fp, 307, msg, headers)

_APP_ICON_CACHE = None
APP_ICON_VERSION = "20260704c"

# ホーム画面アイコン(180x180 PNG・「執筆」ペンデザイン)。
# Render環境にPillow等のサードパーティ依存が無いため、事前生成したPNGをBase64で埋め込む。
_APP_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAIAAACyr5FlAAAJr0lEQVR4nO3df4wcZR3H8c/zzOzvu+5W2gLyS0rRwqUGaKiVA1H8B1ojhMRafwSigSjG/0z0D5AK+CvqHxoTkiaSEDSlgahEKNSEgNjSmEAphlB+Y4iIck3b3b3b29mdmefrH3ttoL2nt3s3szuz+3n92x/z7O07z/Ps3OyMmto6BqL56EEPgJKLcZAV4yArxkFWjIOsGAdZMQ6yYhxkxTjIinGQFeMgK8ZBVoyDrBgHWTEOsmIcZMU4yIpxkBXjICvGQVaMg6wYB1kxDrJiHGTFOMiKcZAV4yArxkFWjIOsGAdZMQ6yYhxkxTjIinGQFeMgK8bRX0pDpeZnnpqBDgOlETTFn05LH+kY5TDQrrTq7ukbc2u+Jl4dyhn0gBbmDnoAo0G70qq6Ky8tfvrXurAKJmy9+aDKlSHhoEd2Kpw54qdd8aruikvHrr5PZcakdaS44ae5C78qrVrC5w/OHDHTrsxWM2s2ljZuV2FeQg9KS9AoXv4TAK03diR5/uDMESflSKOaWbOxdPXvEObFeFAOoADp9JHw+YNxxEZp+M3s2mtKV25HI4O5Mub+LBV9MI54aA3tSNjOXvIFXTpXWnXoE1bwFPTBOGKgHfEa0qyrQrnx5x/40zud089FuwV1wt9Leh+MI2pORuq17MRnsxNXy3RNOcXpHd/1Zx/RK89Cu52uPhhHpNyM1I9mJibLt/+lfPujmYuvMI2azi6b3nFbGvtgHNFxM1I7mpmYrNy5S+WKKles3Pl45qJJM3NUZ8tp7INxROR4GXfsUsUyjIExqliu/HBXevtgHFH4YBmlMoyB1tAaxqhSivtgHEs2bxkdKe+DcSzNKcroSHMfjGMJFiyjI7V9MI7F6rKMjnT2wTgWpacyOpbUx1Zp1fp//Rjj6N0iyuhYXB/+dPFTv8x9/OviN/rcB+Po0aLL6Oi1DzFwctKcMjPv9H9lYRy9WGIZHd33ISFUHn5j5u+3+O/tUW4eYiJ9PQuNtJ8HS7dIyuhYuA81V0a+PbP31uDQAZWv9LkMMI5uRVhGxyn7EK8JlUfJb+y9NXh/v8pXYIKIXkkvY+z/IdMn8jI65u/jO37jT86ZFyDvNZ65xX/zH4MqA4Ca2jo2kAOnRkxlHGcMtJZGrXrPZv+VZ1WpjKBRuvEXrRcf9V99WpUGVgYYxwLiLqOj08dsrXr3Jv/gPjVelmYNbrb/O9ATcFmx608ZOLa+FMuVbbuzl1wj3qwqLh94GWAcVn0rY14SDrwMMI759bmM48vKXde2DjylCkWYwZcBxjGPgZTR2ZAe3KfLFYRJ+QIc4/gwxx1MGT/e7L/8rCovRziwzyYnYxwf4LjSqGcuvqJyx2ODKSPwYzxc7xjHMY4jXkMvW1H+3g5VqsCEI14GGMccxxGvqUvLK9t265XnwYTQcf4KNA1lgHEAx8uoVLbtdldfyjKOG/k4TigjDFjGcaMdx8llOHHezSZVZWCk42AZCxnVOFhGF0YyDpbRndGLg2V0bcTiYBm9GKU4WEaPRiYOltG70YiDZSzKCMTBMhZr2ONgGUsw1HGwjKUZ3jj6XUY4dx3osJSBoY1jAGU4Mlur3jM8ZWA4H6nR5zLCAI4bvPNS/bffDN54Xi0bkjIwhHEMpIy3D1TvutbUp9R4BeGQlIFhW1YGWEajqkqVRF07vnRDFMdgy8gXhqwMDE8cgy8jKd9EitBQxMEy4pH+OFhGbFIeB8uIU5rjYBkxS20cLCN+6YyDZfRFCuNgGf2Stji0Fm+WZfRHquJQCkGgx1dUtj3BMvogVXFoxzRmx27+ubv6MgRtlhG39MShFNqec+a5ufWbYQycTIzHYhkA0hSHdkzTy62/To2fBhGoE59NEhmWcUx64hCjstn8VV8B5KSH1kSHZXxASuJQGt6se95FmbWTEMR1fxWW8WEpiUNr0w7yk1+G48LE84axjJOkJI7Q12PjucktAGJ5zhnLmE8a4tCOeE13zXrn9PNjuTcoy7BIQxwKEprC526G0tHfLp5l2CU+DqXgt/XyFdn1m4Cot6Is45QSH4fW0vTyG67X5VUwYZSnN1jGQhIfhwBKcldsifi/ZRldSHYcSqM1667+ZGbiKohEthVlGd1JdhxaG8/PXf5FlS3AhIjkzCjL6Fqy4zChymdzG64HEM1ug2X0IsFxaEeajczFk+4Fl8GYCD6nsIweJTgOpcQ3+Q03RHB6Q6Rz/QfL6ElSv2WvFPyWs2JV7sotwGJPb4hADKCgNdxs8NYL1buvYxndS2wc2jSb2fWbdOWM3k+ZC4wAAu1AOQDM4f94+x6afeRXZuaoKhRZRpcSGodAHNdZvuk2Y4yGdP3PDIyB40IrANKcbr/8jPfU/f7BPeHhKV0scM7oSSLjUMoN/VrxtKPOmRdqHYbBAouKCCQENLSGo2FC/43nvGd+397/13DqLRiofEGXKzBhQp7XmhZJfJZ9KGq56z/Y+sSdb6964oHfTExcFASh655ciMy92cd2JOF7r7ee2+XtfTB4+0X4vsplkS0AgBhI19MPHZPImQPGOLmna+Ujhw5tuenbOx/Yvm5i7Yf66LzZ2ulkYapT7Rcebz2/q/3PJ029qrKOyhWRL0HCuK4MGg2JmzkEKqeCt8LKlw6eLwLPay4bH3/4D9vXTawNg8DRCkrPnRAzQfulv7X27my9+GT4v3eUA5Uvwc3AmCQ8CH4IJG7mMIKCI3taZx9u4bRMUCgU6tPTW2/61s777123bkIABYTvvuLt+2Nr38PBu69I29f5vC5XIAJjhu/eSwOUuJkDECeT2/LahS9XUXIhYox23697Z330jMfu/dGamddqu+8L/7XfNGZUxlW5IrSGCbmliEOyZg4DNaaCPTPjrzYyeeXVg0yosyud8Btrc5tXvlv42eeP+DNGKZ0v6WWVueUj5AoSl2TFISLZrPvIv8ffa8jqcmGDW73hHHxmvHqOOQwxsxnXZMsagAm5fPRBguIQIK/CN72x1/3x75/93xvPDtc6h7Pie21dg6OUowEIP330T4L2HAK4Ckd8DZGPFYLZQDxxjVIaUN2fJKXoJGjmUEAg+EjGKOCQ72oFrcRhFoOToDhwrA8ArmITg5esOBDNlYAUjQRf7EODxjjIinGQFeMgK8ZBVoyDrBgHWTEOsmIcZMU4yIpxkBXjICvGQVaMg6wYB1kxDrJiHGTFOMiKcZAV4yArxkFWjIOsGAdZMQ6yYhxkxTjIinGQFeMgK8ZBVoyDrBgHWTEOsmIcZMU4yIpxkBXjICvGQVaMg6wYB1kxDrJiHGTFOMiKcZAV4yArxkFW/wdj4GjVVjPnCAAAAABJRU5ErkJggg=="
)

def build_app_icon():
    """ホーム画面用アイコン(180x180 PNG)を返す。"""
    global _APP_ICON_CACHE
    if _APP_ICON_CACHE is None:
        icon_path = os.path.join(os.path.dirname(__file__), "apple-touch-icon.png")
        if os.path.exists(icon_path):
            with open(icon_path, "rb") as f:
                _APP_ICON_CACHE = f.read()
            return _APP_ICON_CACHE
        import base64
        _APP_ICON_CACHE = base64.b64decode(_APP_ICON_B64)
    return _APP_ICON_CACHE

WEB_MANIFEST = json.dumps({
    "name": "IT記事 投稿ジェネレーター",
    "short_name": "記事投稿",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#f5f5f5",
    "theme_color": "#ea580c",
    "icons": [
        {"src": f"/apple-touch-icon.png?v={APP_ICON_VERSION}", "sizes": "180x180", "type": "image/png"},
    ],
}, ensure_ascii=False)

API_KEY = os.environ.get("GEMINI_API_KEY", "")
# 投稿文は低コストなFlash-Liteを既定にする。環境変数で上位モデルに変更可能。
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
# 翻訳もFlash-Liteを既定にする（コストが約1/3、レート制限枠も生成用と共通で運用実績あり）。
# 品質を優先したい場合は環境変数 GEMINI_TRANSLATION_MODEL で gemini-2.5-flash 等に変更可能。
GEMINI_TRANSLATION_MODEL = os.environ.get("GEMINI_TRANSLATION_MODEL", "gemini-2.5-flash-lite")

def call_gemini(prompt_text, max_tokens=800, json_mode=False, model=None, max_retries=4):
    """Gemini APIにプロンプトを送りテキストを返す。429等は自動リトライする。"""
    selected_model = model or GEMINI_MODEL
    # 事実抽出・記事要約で表現がぶれにくいよう、創造性を控えめにする。
    generation_config = {
        "maxOutputTokens": max_tokens,
        "temperature": 0.25 if json_mode else 0.35,
        "topP": 0.9,
    }
    if json_mode:
        generation_config["responseMimeType"] = "application/json"
    # 投稿生成では短い推論枠を与えて事実照合を安定させる。翻訳用Liteは速度を優先する。
    thinking_budget = 0 if "lite" in selected_model.lower() else 512
    generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
        "generationConfig": generation_config,
    }
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{selected_model}:generateContent?{urlencode({'key': API_KEY})}"
    )
    req = Request(
        endpoint,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    result = None
    for attempt in range(max_retries):
        try:
            with urlopen(req, timeout=30) as res:
                result = json.loads(res.read())
            break
        except HTTPError as e:
            retryable = e.code == 429 or e.code >= 500
            if not retryable or attempt == max_retries - 1:
                raise
            retry_after = e.headers.get("Retry-After") if e.headers else None
            try:
                wait_seconds = float(retry_after) if retry_after else (2 ** attempt)
            except ValueError:
                wait_seconds = 2 ** attempt
            print(
                f"[Gemini] {e.code}エラー。{wait_seconds:.1f}秒待って再試行します "
                f"({attempt + 1}/{max_retries})",
                flush=True,
            )
            time.sleep(wait_seconds)
    usage = result.get("usageMetadata")
    if usage:
        print(
            f"[Gemini] tokens in={usage.get('promptTokenCount')} "
            f"out={usage.get('candidatesTokenCount')}",
            flush=True,
        )
    candidates = result.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    text = "".join(part.get("text", "") for part in parts if part.get("text"))
    if not text:
        raise RuntimeError(f"Gemini API: テキストがありません (response={result})")
    return text
PORT       = int(os.environ.get("PORT", 8765))
RECENT_DAYS = 0
RSS_FETCH_TIMEOUT = 4.0
RSS_FETCH_FAST_BUDGET = 4.0
RSS_FETCH_MAX_BUDGET = 8.0
RSS_FULL_FETCH_TIMEOUT = 5.0
RSS_FULL_FETCH_FAST_BUDGET = 6.0
RSS_FULL_FETCH_MAX_BUDGET = 12.0
RSS_PER_FEED_LIMIT = 10
TODAY_FULL_FETCH_MULTIPLIER = 10
SPECIAL_PER_FEED_LIMIT = 5
RSS_EMPTY_RETRY_DELAY = 0.8

# Cookie認証（環境変数で設定。未設定なら認証なし）
BASIC_USER = os.environ.get("BASIC_USER", "")
BASIC_PASS = os.environ.get("BASIC_PASS", "")
COOKIE_SECRET = os.environ.get("COOKIE_SECRET", BASIC_PASS or "dev-secret")
COOKIE_NAME = "it_post_session"
SESSION_IDLE_TIMEOUT_SECONDS = int(os.environ.get("SESSION_IDLE_TIMEOUT_SECONDS", "1800"))

def _sign_session(ts):
    return hmac.new(COOKIE_SECRET.encode(), f"authenticated:{ts}".encode(), hashlib.sha256).hexdigest()

def _make_token(now=None):
    """最終操作時刻を含むログインCookieトークンを生成"""
    ts = int(now if now is not None else time.time())
    return f"{ts}.{_sign_session(ts)}"

def _validate_token(token):
    """Cookieトークンが正しく、最終操作からタイムアウトしていないか確認"""
    if not token or "." not in token:
        return False
    ts_text, _, sig = token.partition(".")
    try:
        ts = int(ts_text)
    except ValueError:
        return False
    expected = _sign_session(ts)
    if not hmac.compare_digest(sig, expected):
        return False
    age = time.time() - ts
    # 端末時計・サーバー時刻の小さな揺れは許容しつつ、30分無操作なら失効
    return -60 <= age <= SESSION_IDLE_TIMEOUT_SECONDS

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>ログイン</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="記事投稿">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#ea580c">
<link rel="apple-touch-icon" href="/apple-touch-icon.png?v=20260704c">
<link rel="icon" type="image/png" href="/apple-touch-icon.png?v=20260704c">
<link rel="manifest" href="/manifest.webmanifest?v=20260704c">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:calc(1rem + env(safe-area-inset-top, 0px)) 1rem calc(1rem + env(safe-area-inset-bottom, 0px))}
  .card{background:#fff;border-radius:16px;padding:2.5rem 2rem;width:100%;max-width:360px;box-shadow:0 2px 20px rgba(0,0,0,.08)}
  h1{font-size:1.3rem;font-weight:700;margin-bottom:.4rem;text-align:center}
  p{font-size:.85rem;color:#888;text-align:center;margin-bottom:1.8rem}
  label{font-size:.8rem;color:#555;display:block;margin-bottom:.3rem}
  input{width:100%;padding:.7rem 1rem;border:1px solid #e5e5e5;border-radius:10px;font-size:16px;margin-bottom:1rem;outline:none}
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
        # AI特化ニュース（当日記事の補完）
        {"url": "https://www.marktechpost.com/feed/", "source": "MarkTechPost"},
        {"url": "https://www.infoworld.com/feed/", "source": "InfoWorld"},
        {"url": "https://thenewstack.io/feed/", "source": "The New Stack"},
        {"url": "https://the-decoder.com/feed/", "source": "The Decoder"},
        {"url": "https://news.google.com/rss/search?q=%28OpenAI+OR+Anthropic+OR+Google+DeepMind+OR+%22AI+model%22+OR+%22generative+AI%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News AI Models"},
        {"url": "https://news.google.com/rss/search?q=%28%22AI+agent%22+OR+%22AI+coding%22+OR+%22large+language+model%22+OR+LLM%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News AI Agents"},
        # 取得確認済みのAI企業公式Blog
        {"url": "https://blog.google/products/gemini/rss/", "source": "Google Gemini Blog"},
        {"url": "https://blogs.nvidia.com/feed/", "source": "NVIDIA Blog"},
        {"url": "https://www.amazon.science/index.rss", "source": "Amazon Science"},
        # Anthropicは公式RSSが無いためGoogle News経由で公式発表を優先取得する。
        # site:anthropic.com（パス指定なし）だと「Log in | Verification Portal」等の
        # ログイン・ポータルページまで拾ってしまうため、記事が置かれる/newsパスに限定する。
        # 更新頻度が低いためwhen:3dだと0件になりやすく、14dで安定した件数を確保する
        # （実際に何日以内の記事として表示するかはアプリ側のrecent_days判定に従う）。
        {"url": "https://news.google.com/rss/search?q=site:anthropic.com/news+when:14d&hl=en-US&gl=US&ceid=US:en", "source": "Anthropic Blog"},
    ],
    "クラウド・AWS": [
        # 国内
        {"url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml", "source": "ITmedia Enterprise"},
        {"url": "https://cloud.watch.impress.co.jp/data/rss/1.0/clw/feed.rdf", "source": "クラウド Watch"},
        {"url": "https://www.publickey1.jp/atom.xml", "source": "Publickey"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        {"url": "https://news.google.com/rss/search?q=%28%E3%82%AF%E3%83%A9%E3%82%A6%E3%83%89+OR+AWS+OR+Azure+OR+%22Google+Cloud%22%29+when%3A1d&hl=ja&gl=JP&ceid=JP%3Aja", "source": "Google News クラウド"},
        # 海外
        {"url": "https://aws.amazon.com/blogs/aws/feed/", "source": "AWS Blog"},
        {"url": "https://thenewstack.io/feed/", "source": "The New Stack"},
        {"url": "https://kubernetes.io/feed.xml", "source": "Kubernetes Blog"},
        {"url": "https://www.docker.com/feed/", "source": "Docker Blog"},
        {"url": "https://www.cncf.io/feed/", "source": "CNCF Blog"},
        {"url": "https://www.hashicorp.com/blog/feed.xml", "source": "HashiCorp Blog"},
        # 高頻度クラウド・DevOpsニュース
        {"url": "https://www.infoq.com/feed/", "source": "InfoQ"},
        {"url": "https://devops.com/feed/", "source": "DevOps.com"},
        {"url": "https://sdtimes.com/feed/", "source": "SD Times"},
        # 当日のクラウド更新を補う高頻度ニュース
        {"url": "https://news.google.com/rss/search?q=%28AWS+OR+%22Amazon+Web+Services%22+OR+Azure+OR+%22Google+Cloud%22+OR+%22cloud+infrastructure%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Cloud Platforms"},
        {"url": "https://news.google.com/rss/search?q=%28Kubernetes+OR+Docker+OR+Terraform+OR+DevOps+OR+%22cloud+native%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News DevOps"},
    ],
    "セキュリティ": [
        # 国内
        {"url": "https://rss.itmedia.co.jp/rss/2.0/news_security.xml", "source": "ITmedia セキュリティ"},
        {"url": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf", "source": "INTERNET Watch"},
        {"url": "https://www.security-next.com/feed", "source": "Security NEXT"},
        {"url": "https://www.jpcert.or.jp/rss/jpcert.rdf", "source": "JPCERT/CC"},
        {"url": "https://news.google.com/rss/search?q=%28%E3%82%B5%E3%82%A4%E3%83%90%E3%83%BC%E6%94%BB%E6%92%83+OR+%E8%84%86%E5%BC%B1%E6%80%A7+OR+%E3%83%A9%E3%83%B3%E3%82%B5%E3%83%A0%E3%82%A6%E3%82%A7%E3%82%A2%29+when%3A1d&hl=ja&gl=JP&ceid=JP%3Aja", "source": "Google News セキュリティ"},
        # 海外
        {"url": "https://feeds.feedburner.com/TheHackersNews", "source": "The Hacker News"},
        {"url": "https://krebsonsecurity.com/feed/", "source": "Krebs on Security"},
        {"url": "https://www.darkreading.com/rss.xml", "source": "Dark Reading"},
        {"url": "https://isc.sans.edu/rssfeed_full.xml", "source": "SANS Internet Storm Center"},
        {"url": "https://www.helpnetsecurity.com/feed/", "source": "Help Net Security"},
        {"url": "https://therecord.media/feed", "source": "The Record"},
        {"url": "https://securityaffairs.com/feed", "source": "Security Affairs"},
        # 当日の脅威・脆弱性ニュースを補う高頻度フィード
        {"url": "https://news.google.com/rss/search?q=%28cybersecurity+OR+vulnerability+OR+ransomware+OR+%22data+breach%22+OR+%22zero-day%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Security"},
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
        # 当日の開発者向けニュースを補う高頻度フィード
        {"url": "https://news.google.com/rss/search?q=%28%22software+development%22+OR+programming+OR+GitHub+OR+%22developer+tools%22+OR+%22open+source%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Development"},
    ],
    "スタートアップ": [
        # 国内
        {"url": "https://thebridge.jp/feed", "source": "BRIDGE"},
        {"url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "source": "ITmedia NEWS"},
        {"url": "https://coralcap.co/feed/", "source": "Coral Capital"},
        {"url": "https://news.google.com/rss/search?q=%28%E3%82%B9%E3%82%BF%E3%83%BC%E3%83%88%E3%82%A2%E3%83%83%E3%83%97+OR+%E8%B3%87%E9%87%91%E8%AA%BF%E9%81%94+OR+%E3%83%99%E3%83%B3%E3%83%81%E3%83%A3%E3%83%BC%29+when%3A1d&hl=ja&gl=JP&ceid=JP%3Aja", "source": "Google News スタートアップ"},
        # 海外
        {"url": "https://techcrunch.com/category/startups/feed/", "source": "TechCrunch Startups"},
        {"url": "https://venturebeat.com/feed/", "source": "VentureBeat"},
        # 当日の資金調達・スタートアップニュースを補う高頻度フィード
        {"url": "https://news.google.com/rss/search?q=%28startup+OR+funding+OR+%22venture+capital%22+OR+%22seed+round%22+OR+%22series+A%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Startups"},
        {"url": "https://techcrunch.com/feed/", "source": "TechCrunch"},
        {"url": "https://sifted.eu/feed", "source": "Sifted"},
        {"url": "https://www.eu-startups.com/feed/", "source": "EU-Startups"},
        {"url": "https://tech.eu/feed/", "source": "Tech.eu"},
    ],
    "便利ツール・Tips": [
        # 国内
        {"url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", "source": "PC Watch"},
        {"url": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf", "source": "INTERNET Watch"},
        {"url": "https://www.lifehacker.jp/feed/index.xml", "source": "Lifehacker Japan"},
        {"url": "https://zenn.dev/feed", "source": "Zenn"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        {"url": "https://forest.watch.impress.co.jp/data/rss/1.0/wf/feed.rdf", "source": "窓の杜"},
        # 海外
        {"url": "https://www.producthunt.com/feed", "source": "Product Hunt"},
        {"url": "https://lifehacker.com/rss", "source": "Lifehacker"},
        {"url": "https://www.howtogeek.com/feed/", "source": "How-To Geek"},
        {"url": "https://www.makeuseof.com/feed/", "source": "MakeUseOf"},
        # 当日のアプリ・業務効率化ニュースを補う高頻度フィード
        {"url": "https://news.google.com/rss/search?q=%28%22productivity+app%22+OR+%22software+tool%22+OR+%22developer+tool%22+OR+%22AI+tool%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Tools"},
        {"url": "https://news.google.com/rss/search?q=%28%22app+update%22+OR+%22software+update%22+OR+%22browser+extension%22+OR+%22productivity+software%22+OR+automation%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News App Updates"},
        {"url": "https://news.google.com/rss/search?q=%28%22iPhone+app%22+OR+%22Android+app%22+OR+%22Windows+app%22+OR+%22Mac+app%22+OR+%22Chrome+extension%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Apps"},
    ],
    "ガジェット・ハードウェア": [
        # 国内
        {"url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", "source": "PC Watch"},
        {"url": "https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf", "source": "ケータイ Watch"},
        {"url": "https://www.gizmodo.jp/index.xml", "source": "Gizmodo Japan"},
        {"url": "https://av.watch.impress.co.jp/data/rss/1.0/avw/feed.rdf", "source": "AV Watch"},
        {"url": "https://news.google.com/rss/search?q=%28%E3%82%AC%E3%82%B8%E3%82%A7%E3%83%83%E3%83%88+OR+%E3%82%B9%E3%83%9E%E3%83%9B+OR+%E5%AE%B6%E9%9B%BB%29+when%3A1d&hl=ja&gl=JP&ceid=JP%3Aja", "source": "Google News ガジェット"},
        # 海外
        {"url": "https://www.engadget.com/rss.xml", "source": "Engadget"},
        {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge"},
        {"url": "https://feeds.arstechnica.com/arstechnica/gadgets", "source": "Ars Technica Gadgets"},
        {"url": "https://gizmodo.com/rss", "source": "Gizmodo"},
        {"url": "https://www.tomshardware.com/feeds/all", "source": "Tom's Hardware"},
        # 当日の製品・ハードウェアニュースを補う高頻度フィード
        {"url": "https://news.google.com/rss/search?q=%28smartphone+OR+laptop+OR+gadget+OR+hardware+OR+%22consumer+technology%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Hardware"},
    ],
    "ビジネス・DX": [
        # 国内
        {"url": "https://rss.itmedia.co.jp/rss/2.0/business.xml", "source": "ITmedia ビジネス"},
        {"url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml", "source": "ITmedia Enterprise"},
        {"url": "https://www.publickey1.jp/atom.xml", "source": "Publickey"},
        {"url": "https://xtech.nikkei.com/rss/index.rdf", "source": "日経XTECH"},
        {"url": "https://b.hatena.ne.jp/hotentry/it.rss", "source": "はてブ IT"},
        # 海外
        {"url": "https://techcrunch.com/category/enterprise/feed/", "source": "TechCrunch Enterprise"},
        {"url": "https://www.cio.com/feed/", "source": "CIO"},
        {"url": "https://www.ciodive.com/feeds/news/", "source": "CIO Dive"},
        {"url": "https://www.informationweek.com/rss.xml", "source": "InformationWeek"},
        {"url": "https://venturebeat.com/category/enterprise/feed", "source": "VentureBeat Enterprise"},
        {"url": "https://www.zdnet.com/news/rss.xml", "source": "ZDNet"},
        {"url": "https://www.computerworld.com/feed/", "source": "Computerworld"},
        # 当日のDX・エンタープライズニュースを補う高頻度フィード
        {"url": "https://news.google.com/rss/search?q=%28%22digital+transformation%22+OR+%22enterprise+software%22+OR+SaaS+OR+%22business+technology%22%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen", "source": "Google News Business Tech"},
    ],
}

GITHUB_RELEASE_FEEDS = {
    "AI・機械学習": [
        {"url": "https://github.com/openai/openai-python/releases.atom", "source": "GitHub Releases: openai/openai-python"},
        {"url": "https://github.com/ollama/ollama/releases.atom", "source": "GitHub Releases: ollama/ollama"},
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
        {"url": "https://openai.com/products/release-notes/rss.xml", "source": "OpenAI Product Release Notes"},
        {
            "url": "https://support.claude.com/en/articles/12138966-release-notes",
            "source": "Claude Help Center Release Notes",
            "format": "claude_help_html",
        },
        {"url": "https://platform.claude.com/docs/en/release-notes/feed.xml", "source": "Claude Platform Release Notes"},
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
    "Google Gemini Blog",
    "NVIDIA Blog",
    "Amazon Science",
    "OpenAI Blog",
    "OpenAI News / Docs",
    "Anthropic Blog",
    "Google DeepMind Blog",
    "Hugging Face Blog",
    "Google AI Blog",
    "Google Research Blog",
    "Meta Engineering Blog",
    "Kubernetes Blog",
    "Docker Blog",
    "CNCF Blog",
    "HashiCorp Blog",
}

# AIカテゴリでは、主要公式ソースの完了を確認するまで件数による早期終了を行わない。
# 公式情報の最終枠は企業グループ単位（OpenAI / Anthropic / Google・Gemini）で確保する。
AI_PRIORITY_OFFICIAL_SOURCES = {
    "OpenAI Blog",
    "OpenAI Product Release Notes",
    "Anthropic Blog",
    "Claude Help Center Release Notes",
    "Claude Platform Release Notes",
    "Google DeepMind Blog",
    "Google AI Blog",
    "Google Gemini Blog",
}
AI_PRIORITY_OFFICIAL_GROUPS = (
    ("OpenAI", {"OpenAI Blog", "OpenAI Product Release Notes"}),
    (
        "Anthropic",
        {"Anthropic Blog", "Claude Help Center Release Notes", "Claude Platform Release Notes"},
    ),
    ("Google/Gemini", {"Google DeepMind Blog", "Google AI Blog", "Google Gemini Blog"}),
)

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
    "Security NEXT",
    "JPCERT",
    "Coral Capital",
    "窓の杜",
    "Google News セキュリティ",
    "Google News スタートアップ",
    "Google News クラウド",
    "Google News ガジェット",
]

CATEGORY_RELEVANCE_KEYWORDS = {
    "AI・機械学習": [
        "ai", "artificial intelligence", "machine learning", "deep learning", "llm",
        "chatgpt", "claude", "gemini", "openai", "anthropic", "deepmind", "model",
        "agent", "agents", "neural", "生成ai", "人工知能", "機械学習", "深層学習",
        "大規模言語モデル", "言語モデル", "チャットgpt", "チャットボット", "モデル",
        "エージェント", "推論", "学習", "ai",
    ],
    "クラウド・AWS": [
        "aws", "amazon web services", "ec2", "s3", "lambda", "rds", "lightsail",
        "cloud", "cloudflare", "google cloud", "gcp", "azure", "kubernetes", "k8s",
        "container", "docker", "serverless", "terraform", "infrastructure", "cdn",
        "networking", "vpc", "observability", "logs", "incident", "クラウド", "aws", "アマゾン",
        "サーバーレス", "コンテナ", "インフラ", "ネットワーク", "データセンター",
        "運用", "監視", "障害", "セキュリティ基盤",
    ],
    "セキュリティ": [
        "security", "cyber", "vulnerability", "cve", "malware", "ransomware",
        "phishing", "breach", "attack", "threat", "exploit", "zero-day", "0-day",
        "patch", "authentication", "encryption", "privacy", "セキュリティ", "脆弱性",
        "サイバー", "マルウェア", "ランサムウェア", "フィッシング", "攻撃", "不正",
        "漏えい", "漏洩", "認証", "暗号", "パッチ", "警告", "注意喚起", "リスク",
    ],
    "開発": [
        "developer", "development", "programming", "code", "coding", "software",
        "javascript", "typescript", "python", "node", "react", "next.js", "css",
        "html", "api", "github", "git", "cli", "framework", "database", "debug",
        "test", "testing", "webassembly", "wasm", "開発", "プログラミング", "コード",
        "実装", "設計", "エンジニア", "api", "フレームワーク", "ライブラリ", "デバッグ",
        "テスト", "web", "javascript", "typescript", "python", "github", "git",
    ],
    "スタートアップ": [
        "startup", "startups", "founder", "funding", "ipo", "venture", "vc",
        "y combinator", "yc", "stripe", "supabase", "saas", "acquisition",
        "launch", "product", "growth", "revenue", "スタートアップ", "起業", "創業",
        "資金調達", "上場", "ipo", "投資", "買収", "vc", "ベンチャー", "新興企業",
        "saas", "プロダクト", "成長", "売上",
    ],
    "便利ツール・Tips": [
        "tool", "tools", "app", "apps", "productivity", "workflow", "automation",
        "extension", "chrome", "browser", "workspace", "notion", "obsidian", "raycast",
        "vscode", "visual studio code", "linear", "github", "ai", "mac", "iphone",
        "android", "便利", "ツール", "アプリ", "効率化", "自動化", "拡張機能",
        "ブラウザ", "ワークフロー", "ショートカット", "デスク", "仕事術", "作業",
        "ノート", "chrome", "github", "vscode", "mac", "iphone", "android",
    ],
    "ガジェット・ハードウェア": [
        "gadget", "hardware", "device", "smartphone", "phone", "iphone", "android",
        "pc", "laptop", "tablet", "gpu", "cpu", "chip", "semiconductor", "camera",
        "console", "xbox", "playstation", "switch", "kindle", "router", "wi-fi",
        "wifi", "display", "monitor", "battery", "wearable", "ガジェット", "ハードウェア",
        "スマホ", "スマートフォン", "iphone", "android", "pc", "パソコン", "gpu", "cpu",
        "半導体", "カメラ", "ルーター", "wi-fi", "wifi", "ディスプレイ", "モニター",
        "バッテリー", "ゲーム機", "タブレット", "ウェアラブル", "端末",
    ],
    "ビジネス・DX": [
        "dx", "digital transformation", "enterprise", "business", "saas", "workflow",
        "automation", "ai", "data", "analytics", "cloud", "security", "productivity",
        "management", "sales", "customer", "crm", "erp", "it", "tech", "startup",
        "企業", "ビジネス", "dx", "デジタル", "変革", "業務", "効率化", "自動化",
        "ai", "データ", "クラウド", "セキュリティ", "経営", "営業", "顧客", "it",
        "システム", "saas", "生産性", "事例", "導入", "市場", "調査",
    ],
}

CATEGORY_RELEVANCE_FILTER_SOURCES = {
    # 広めのフィードはカテゴリ外の記事を多く含むため、カテゴリ検索時だけ本文メタで絞る
    "AI・機械学習": {
        "Publickey",
        "はてブ IT",
        "CNET Japan",
        "Ars Technica",
        "MIT Technology Review",
        "InfoWorld",
        "The New Stack",
    },
    "クラウド・AWS": {
        "Hacker News",
        "はてブ IT",
        "Publickey",
        "ITmedia Enterprise",
        "The New Stack",
        "InfoQ",
        "SD Times",
    },
    "セキュリティ": {
        "Hacker News",
        "ZDNet Security",
        "INTERNET Watch",
        "はてブ IT",
        "ITmedia セキュリティ",
    },
    "開発": {
        "Hacker News",
        "はてブ IT",
        "Ars Technica",
    },
    "スタートアップ": {
        "Hacker News",
        "The Verge",
        "Business Insider",
        "TechCrunch",
        "VentureBeat",
        "ITmedia NEWS",
        "はてブ IT",
    },
    "便利ツール・Tips": {
        "Hacker News",
        "Lifehacker",
        "Lifehacker Japan",
        "INTERNET Watch",
        "PC Watch",
        "はてブ IT",
        "How-To Geek",
        "MakeUseOf",
    },
    "ガジェット・ハードウェア": {
        "The Verge",
        "Gizmodo",
        "Engadget",
        "Gizmodo Japan",
        "ケータイ Watch",
        "はてブ IT",
    },
    "ビジネス・DX": {
        "Forbes Tech",
        "ZDNet DX",
        "Fast Company",
        "ITmedia ビジネス",
        "ITmedia Enterprise",
        "Publickey",
        "日経XTECH",
        "はてブ IT",
        "ZDNet",
        "Computerworld",
    },
}

def is_category_relevant(article, category):
    keywords = CATEGORY_RELEVANCE_KEYWORDS.get(category)
    noisy_sources = CATEGORY_RELEVANCE_FILTER_SOURCES.get(category, set())
    if not keywords or article.get("source", "") not in noisy_sources:
        return True
    haystack = " ".join(str(article.get(k, "")) for k in ("title", "summary")).lower()
    return any(keyword.lower() in haystack for keyword in keywords)

def strip_invisible_chars(text):
    """ゼロ幅文字等の不可視Unicode文字を除去する（プロンプトインジェクション対策）。"""
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")

def strip_tags(text):
    cleaned = re.sub(r'<[^>]+>', '', html.unescape(text or '')).strip()
    return strip_invisible_chars(cleaned)

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
    return (today - article_date).days

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

def article_identity_keys(article):
    """同一記事のURL違い・同一タイトル配信を判定するためのキーを返す。"""
    keys = []
    url = (article.get("url") or "").strip()
    if url:
        try:
            parts = urlsplit(url)
            # utm等の計測パラメータやフラグメントは記事の同一性に含めない。
            query = urlencode([
                (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                if not key.lower().startswith(("utm_", "fbclid", "gclid"))
            ], doseq=True)
            url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
        except ValueError:
            pass
        keys.append(("url", url))

    title = unicodedata.normalize("NFKC", strip_tags(article.get("title", ""))).lower()
    title = re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", "", title)
    # 短い定型見出し（例: "速報"）だけでは重複扱いにしない。
    if len(title) >= 12:
        keys.append(("title", title))
    return keys

_STORY_STOP_WORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on",
    "or", "the", "to", "with", "after", "before", "over", "new", "says", "will",
}

def articles_describe_same_story(first, second):
    """異なるソースで配信された同一ニュースを検出する。"""
    if not (first.get("type") == "rss_news" and second.get("type") == "rss_news"):
        return False

    def _title_tokens(article):
        title = article.get("title_en") or article.get("title", "")
        words = re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", title).lower())
        return [word for word in words if len(word) >= 3 and word not in _STORY_STOP_WORDS]

    first_tokens = _title_tokens(first)
    second_tokens = _title_tokens(second)
    if not first_tokens or not second_tokens:
        return False
    shared = set(first_tokens) & set(second_tokens)
    overlap = len(shared) / min(len(set(first_tokens)), len(set(second_tokens)))
    first_bigrams = set(zip(first_tokens, first_tokens[1:]))
    second_bigrams = set(zip(second_tokens, second_tokens[1:]))

    first_is_gnews = first.get("source", "").startswith("Google News ")
    second_is_gnews = second.get("source", "").startswith("Google News ")

    if first_is_gnews and second_is_gnews:
        # Google News同士: 同一ニュースを複数媒体が異なる見出しで配信するため積極的に統合
        return (
            len(shared) >= 3 and overlap >= 0.4
        ) or (
            len(shared) >= 2 and overlap >= 0.35 and bool(first_bigrams & second_bigrams)
        )
    else:
        # 異なるRSSソース間: トークンの高一致率で同一記事と判定
        return (
            len(shared) >= 5 and overlap >= 0.7
        ) or (
            len(shared) >= 4 and overlap >= 0.6 and bool(first_bigrams & second_bigrams)
        )

# 本文コンテナとして一般的なclass/id名。主要RSSソース31サイトの実HTML調査に基づく。
# - [-_]? はハイフン/アンダースコア/連結の揺れを吸収（entry-content, entrybody, c-article_content, articleBody等）
# - 属性はシングルクォートのサイトもある（The Hacker News等）ため ["\'] で両対応
# - markdown-bodyはGitHubリリースページのリリースノート本体（ページ内に1箇所のみ）
_CONTENT_CLASS_PATTERN = re.compile(
    r'<(?:article|div|section|main)\b[^>]*(?:class|id)=["\'][^"\']*(?:'
    r'entry[-_]?content|entry[-_]?body|article[-_]?body|article[-_]?content|'
    r'post[-_]?content|post[-_]?body|main[-_]?content|markdown[-_]?body'
    r')[^"\']*["\'][^>]*>',
    re.I,
)
# 本文とみなす領域の開始位置から、この文字数ぶんのHTMLだけを対象にする。
# 実サイトのHTMLは閉じタグの対応が崩れていることが多く、深さを数えて正確な終了位置を
# 求めるのは信頼できないため、本文が収まる程度の固定windowで打ち切る簡易的な方法にする。
# 20kだとThe Hacker News等のマークアップが重いサイトで本文後半が切れ、40kだと関連記事
# ノイズが増えるため30kにしている。
_CONTENT_WINDOW_CHARS = 30000
# 候補ブロックを本文とみなす最低テキスト量。実測では正しい本文はほぼ全サイトで500字を
# 超え、誤マッチ（関連記事カード等）は数十〜300字程度だった。
_CONTENT_MIN_TEXT = 500
# クラス/IDパターンの探索は先頭数箇所まで（巨大ページでの無駄な走査を防ぐ）
_CONTENT_PATTERN_MAX_TRIES = 8

def _content_text_len(block):
    """HTMLブロック中の可視テキスト量の概算。"""
    return len(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', block)))

def _extract_main_content_block(raw):
    """本文とみなせる領域を優先順位順に探して返す。見つからなければNone。

    優先順位（主要31ソースの実HTML調査で決定）:
    1. <article>タグの最長ブロック（十分なテキストがある場合。最も精度が高い）
    2. entry-content等の本文系クラス/IDを持つブロック（<article>を使わないWordPress系等）
       ただし<main>と比べてテキストが半分未満しかない場合は誤マッチとみなしスキップ
       （例: GitHub Blogは post-content 系クラスが目次にだけ付いている）
    3. <main>タグ（ページ全体よりはヘッダ・ナビを除外できる）
    """
    article_blocks = re.findall(r'<article[^>]*>.*?</article>', raw, flags=re.S|re.I)
    if article_blocks:
        longest = max(article_blocks, key=len)
        if _content_text_len(longest) >= _CONTENT_MIN_TEXT:
            return longest

    main_match = re.search(r'<main[^>]*>.*?</main>', raw, flags=re.S|re.I)
    main_block = main_match.group(0) if main_match else None
    main_len = _content_text_len(main_block) if main_block else 0

    # 同名クラスが複数箇所にある場合（導入ボックスと本文が別divのCodeZine等）や、
    # 最初のマッチが隠しテンプレートの場合があるため、複数試してテキスト最長のwindowを使う。
    best_window = None
    best_len = 0
    for i, match in enumerate(_CONTENT_CLASS_PATTERN.finditer(raw)):
        if i >= _CONTENT_PATTERN_MAX_TRIES:
            break
        window = raw[match.start():match.start() + _CONTENT_WINDOW_CHARS]
        # windowの終端がタグの途中で切れていると、閉じられていない"<div..."のような
        # 断片がタグ除去処理をすり抜けて本文に混入するため、最後の完全なタグ境界で切り直す。
        last_tag_end = window.rfind(">")
        if last_tag_end != -1:
            window = window[:last_tag_end + 1]
        window_len = _content_text_len(window)
        if window_len > best_len:
            best_window, best_len = window, window_len
    if (
        best_window is not None
        and best_len >= _CONTENT_MIN_TEXT
        and (not main_block or best_len >= main_len * 0.5)
    ):
        return best_window

    if main_block and main_len >= _CONTENT_MIN_TEXT:
        return main_block

    return None

def fetch_article_body(url, char_limit=6000, timeout=15):
    """記事URLから本文テキストを取得して返す"""
    cache_key = (url, char_limit)
    cached = _ARTICLE_BODY_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < _ARTICLE_BODY_CACHE_TTL:
        return cached[1]
    try:
        import urllib.request
        opener = urllib.request.build_opener(FeedRedirectHandler())
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en;q=0.9",
        })
        with opener.open(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8", errors="replace")

        # <script> <style> <nav> <header> <footer> <aside> <form> を除去
        raw = re.sub(r'<(script|style|nav|header|footer|aside|form)[^>]*>.*?</\1>', ' ', raw, flags=re.S|re.I)

        # 本文とみなせる領域があれば、そこだけを対象にする（ナビ・関連記事・広告・執筆者紹介などの
        # ノイズを除外し、文字数上限を本文そのものに使えるため）。<article>タグ→本文系クラス/ID→
        # <main>タグの順に探し、見つからない/短すぎる場合はページ全体にフォールバックする。
        content_block = _extract_main_content_block(raw)
        if content_block:
            raw = content_block

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
        _ARTICLE_BODY_CACHE[cache_key] = (time.monotonic(), text)
        return text
    except Exception as e:
        print(f"[記事取得] 失敗: {e}", flush=True)
        return ""

_RSS_CACHE = {}  # {feed_url: (timestamp, items_list)}
_RSS_CACHE_TTL = 300  # 5分キャッシュ
_RSS_FAIL_CACHE = {}  # {feed_url: timestamp}
_RSS_FAIL_CACHE_TTL = 600  # 10分間、失敗したフィードをスキップ
_ARTICLE_BODY_CACHE = {}  # {(url, char_limit): (timestamp, article_body)}
_ARTICLE_BODY_CACHE_TTL = 1800  # 本文確認済みURLを30分間再利用
_CANCEL_EVENTS = {}
_CANCEL_LOCK = threading.Lock()

class FetchCancelled(Exception):
    pass

def create_cancel_event(request_id):
    if not request_id:
        return None
    event = threading.Event()
    with _CANCEL_LOCK:
        _CANCEL_EVENTS[request_id] = event
    return event

def cancel_request(request_id):
    with _CANCEL_LOCK:
        event = _CANCEL_EVENTS.get(request_id)
    if not event:
        return False
    event.set()
    return True

def clear_cancel_event(request_id):
    if not request_id:
        return
    with _CANCEL_LOCK:
        _CANCEL_EVENTS.pop(request_id, None)

def ensure_not_cancelled(cancel_event):
    if cancel_event and cancel_event.is_set():
        raise FetchCancelled("取得をキャンセルしました")

def shutdown_executor(executor):
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        executor.shutdown(wait=False)

def filter_candidates_with_article_body(candidates, limit, cancel_event=None):
    """本文を取得できない候補を候補一覧から除外する。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 最初に選ばれた候補を優先しつつ、本文取得不可の穴を補う予備候補も確認する。
    # 本文取得に失敗する候補が多いカテゴリでもlimit件を確保しやすいよう余裕を持たせる。
    check_limit = min(len(candidates), max(limit * 3, limit))
    check_items = candidates[:check_limit]
    if not check_items:
        return []

    def _check(article):
        url = article.get("url", "")
        if article.get("type") == "official_x":
            return article, False
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            return article, False
        if article.get("type") in ("official_blog", "github_release", "docs_update"):
            # 公式ソースはリンク切れがまず無く、ボットブロックで本文が取れない場合でも
            # （OpenAI Blogの403、HashiCorp Blogの429、AppleのJSページ等）RSS概要で
            # 投稿文生成できるため、本文の有無では除外しない。
            return article, True
        if parts.netloc.endswith("news.google.com") or article.get("source", "").startswith("Google News"):
            # Google NewsのURLはJSリダイレクト用のシェルページで、実記事の本文を
            # 取得できない。実際の記事自体は存在するためRSS概要を使う前提で通す。
            # ソース名がGoogle Newsでないフィード（例: Google News検索を使うAnthropic Blog）
            # もあるため、URLのホスト名でも判定する。
            return article, True
        # 本文の有無だけを確認する。本文は同じURLの投稿文生成時にキャッシュから再利用される。
        body = fetch_article_body(url, char_limit=6000, timeout=6)
        return article, len(body.strip()) >= 180

    valid_urls = set()
    # I/Oバウンドな本文取得なのでワーカー数を増やしても安全。6並列では
    # 検証対象が多い時に時間がかかりすぎ、有効な候補が集まりにくかった。
    with ThreadPoolExecutor(max_workers=min(len(check_items), 20)) as executor:
        futures = [executor.submit(_check, article) for article in check_items]
        for future in as_completed(futures):
            ensure_not_cancelled(cancel_event)
            try:
                article, is_valid = future.result()
            except Exception as e:
                print(f"[本文確認] 失敗: {e}", flush=True)
                continue
            if is_valid:
                valid_urls.add(article.get("url", ""))

    valid = [article for article in check_items if article.get("url", "") in valid_urls][:limit]
    excluded = len(check_items) - len(valid_urls)
    if excluded:
        print(f"[本文確認] 本文を取得できない候補を{excluded}件除外（有効{len(valid)}件）", flush=True)
    return valid

def sort_articles_newest_first(articles):
    # 日付順を常に守る。公式系の優先は、公開日時が同じ場合だけのタイブレークにする。
    # 先に種別を並べると、数日前の公式記事が今日のニュースより上に表示されてしまう。
    OFFICIAL_TYPES = ("official_blog", "github_release", "docs_update", "official_x")
    return sorted(
        articles,
        key=lambda article: (
            article.get("sortTime", 0) or 0,
            1 if article.get("type") in OFFICIAL_TYPES else 0,
            article.get("trustScore", 0) or 0,
        ),
        reverse=True,
    )

def reserve_ai_official_articles(articles, limit, official_candidates=None):
    """期間外も含む公式母集団から3社の最新を各1件、選定プールの先頭に確保する。"""
    official_candidates = sort_articles_newest_first(official_candidates or articles)
    reserved = []
    reserved_urls = set()
    missing_groups = []
    for group_name, sources in AI_PRIORITY_OFFICIAL_GROUPS:
        article = next((item for item in official_candidates if item.get("source") in sources), None)
        if article is None:
            missing_groups.append(group_name)
            continue
        article = dict(article)
        article["isPriorityOfficialLatest"] = True
        article["officialGroup"] = group_name
        url = article.get("url", "")
        reserved.append(article)
        if url:
            reserved_urls.add(url)

    if missing_groups:
        print(
            f"[公式最新] 候補を取得できません: {missing_groups}",
            flush=True,
        )
    if reserved:
        print(
            f"[公式最新] {len(reserved)}件確保: "
            f"{[(item.get('officialGroup'), item.get('source')) for item in reserved]}",
            flush=True,
        )

    # 本文確認の前に先頭へ置くことで、後続の新着記事が多くても公式枠を落とさない。
    # 本文確認後には改めて新着順へ戻すため、画面上の通常の時系列表示は維持される。
    remaining = [item for item in articles if item.get("url", "") not in reserved_urls]
    return (reserved + remaining)[:max(limit * 3, limit)]

def fetch_rss(feed_url, source, limit=5, article_type=None, timeout=RSS_FETCH_TIMEOUT):
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
        opener = urllib.request.build_opener(FeedRedirectHandler())
        req = Request(feed_url, headers={
            # 単純な"Mozilla/5.0"だとBot判定で接続を切るサイトがあるため、実ブラウザ相当のUAにする。
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        })
        with opener.open(req, timeout=timeout) as res:
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
        for item in rss_items:
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
            for entry in atom_entries:
                title = strip_tags(entry.findtext('atom:title', '', ns) or _first_text(entry, 'title'))
                # Blogger等はrel="replies"（コメントフィード）のlinkが先頭に来るため、
                # 単純に最初のlinkを取ると記事URLではなくコメントURLを拾ってしまう。
                # rel="alternate"またはrel無しのlinkを優先し、無ければ先頭にフォールバック。
                link_els = entry.findall('atom:link', ns) or list(_children_by_name(entry, 'link'))
                link_el = next(
                    (el for el in link_els if el.get('rel') in (None, '', 'alternate')),
                    link_els[0] if link_els else None,
                )
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
    except HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            location = e.headers.get("Location")
            if location:
                redirected_url = urljoin(feed_url, location)
                return fetch_rss(redirected_url, source, limit=limit, article_type=article_type, timeout=timeout)
        _RSS_FAIL_CACHE[feed_url] = _time.time()
        print(f"[RSS] {source} 取得失敗: {e}", flush=True)
        return []
    except Exception as e:
        _RSS_FAIL_CACHE[feed_url] = _time.time()
        print(f"[RSS] {source} 取得失敗: {e}", flush=True)
        return []

def fetch_claude_help_release_notes(page_url, source, limit=10, timeout=RSS_FETCH_TIMEOUT):
    """Claude Help Centerの単一HTMLページから日付・更新見出し・概要を抽出する。"""
    import time as _time
    failed_at = _RSS_FAIL_CACHE.get(page_url)
    if failed_at and _time.time() - failed_at < _RSS_FAIL_CACHE_TTL:
        return []

    cached = _RSS_CACHE.get(page_url)
    if cached:
        ts, cached_items = cached
        if _time.time() - ts < _RSS_CACHE_TTL:
            return cached_items[:limit]

    try:
        import urllib.request
        opener = urllib.request.build_opener(FeedRedirectHandler())
        req = Request(
            page_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with opener.open(req, timeout=timeout) as res:
            document = res.read().decode("utf-8", errors="replace")

        body_match = re.search(r'<div[^>]*class=["\'][^"\']*\barticle_body\b[^"\']*["\'][^>]*>', document, re.I)
        if not body_match:
            raise ValueError("article_bodyが見つかりません")
        article_end = document.find("</article>", body_match.end())
        body_html = document[body_match.end():article_end if article_end >= 0 else None]

        tokens = re.finditer(
            r'<h3\b(?P<h3_attrs>[^>]*)>(?P<h3>.*?)</h3>|<p\b[^>]*>(?P<p>.*?)</p>',
            body_html,
            re.I | re.S,
        )
        items = []
        current_date = ""
        current_anchor = ""
        current_title = ""
        summary_parts = []

        def _commit_entry():
            if not current_date or not current_title:
                return
            try:
                published = datetime.strptime(current_date, "%B %d, %Y").replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                return
            entry_id = hashlib.sha1(current_title.encode("utf-8")).hexdigest()[:12]
            link = f"{page_url}?{urlencode({'entry': entry_id})}"
            if current_anchor:
                link += f"#{current_anchor}"
            items.append(build_article(
                current_title,
                link,
                source,
                published,
                article_type="docs_update",
                summary=" ".join(summary_parts),
            ))

        for token in tokens:
            if token.group("h3") is not None:
                _commit_entry()
                current_date = strip_tags(token.group("h3"))
                anchor_match = re.search(r'\bid=["\']([^"\']+)', token.group("h3_attrs") or "", re.I)
                current_anchor = anchor_match.group(1) if anchor_match else ""
                current_title = ""
                summary_parts = []
                continue

            paragraph_html = token.group("p") or ""
            paragraph_text = strip_tags(paragraph_html)
            if not paragraph_text:
                continue
            title_match = re.match(
                r'\s*<(?:b|strong)\b[^>]*>(.*?)</(?:b|strong)>\s*$',
                paragraph_html,
                re.I | re.S,
            )
            if current_date and title_match:
                _commit_entry()
                current_title = strip_tags(title_match.group(1))
                summary_parts = []
            elif current_title:
                summary_parts.append(paragraph_text)
        _commit_entry()

        _RSS_CACHE[page_url] = (_time.time(), items)
        _RSS_FAIL_CACHE.pop(page_url, None)
        return items[:limit]
    except Exception as e:
        _RSS_FAIL_CACHE[page_url] = _time.time()
        print(f"[HTML更新] {source} 取得失敗: {e}", flush=True)
        return []

def fetch_configured_source(feed, limit, article_type=None, timeout=RSS_FETCH_TIMEOUT):
    if feed.get("format") == "claude_help_html":
        return fetch_claude_help_release_notes(
            feed["url"], feed["source"], limit=limit, timeout=timeout
        )
    return fetch_rss(
        feed["url"], feed["source"], limit=limit, article_type=article_type, timeout=timeout
    )

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

def needs_translation(article):
    def has_latin_text(value):
        # 英日混在の見出し（例: 「AWS launches 新機能」）も対象にする。
        # 固有名詞だけの場合もGemini側のルールで英語のまま保持される。
        return len(re.findall(r"[A-Za-z]{4,}", value or "")) > 0

    return (
        has_latin_text(article.get("title", ""))
        or has_latin_text(article.get("summary", ""))
        or article.get("type") in ("github_release", "docs_update")
    )

TRANSLATE_PROMPT_BASE = (
    "あなたは日本のITニュース編集者です。以下の候補を、正確で自然な日本語の見出しと概要に編集してください。\n"
    "翻訳・編集ルール（必ず守る）:\n"
    "- 入力にない事実・数値・評価を足さない。推測で補わない\n"
    "- 逐語訳や不自然なカタカナ語を避け、日本のITニュース見出しとして簡潔で読みやすく書く\n"
    "- Apple、AWS、OpenAI、ChatGPT、Claude、Gemini、GitHub、製品名、正式な人名、リポジトリ名、バージョン番号は原則として英語のまま残す\n"
    "- 一般的な技術用語は自然な日本語にする（例: release→リリース、security vulnerability→脆弱性、deployment→デプロイ）\n"
    "- タイトルは内容が一読で分かる自然な日本語。原文の情報量を不必要に削らない\n"
    "- GitHub Releasesは、リポジトリ名とバージョンを残し、「何のリリースか」が分かる表現にする\n"
    "- summary_ja は80文字以内。記事本文を読まなくても更新点・要点が分かる一文にする\n"
    "- 原文が既に十分自然な日本語なら、意味を変えずにそのまま返す\n"
    "- JSON配列のみを返す。説明文やMarkdownは不要\n"
    '- 各要素は {"index": 数字, "title_ja": 文字列, "summary_ja": 文字列} の形にする\n\n'
)
TRANSLATION_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_cache.json")
TRANSLATION_CACHE_MAX = 3000
TRANSLATION_CACHE_VERSION = "gemini-flash-lite-editor-v3"

def _load_translation_cache():
    try:
        with open(TRANSLATION_CACHE_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return {
            (e[1], e[2]): (e[3], e[4])
            for e in entries
            # e[3](title_ja)が空のエントリは、過去のバグでtitle_ja空文字が
            # 永続保存されてしまったものである可能性があるため読み込み時に除外し、
            # 次回アクセス時に再翻訳を試みられるようにする（自己修復）。
            if len(e) == 5 and e[0] == TRANSLATION_CACHE_VERSION and e[3]
        }
    except Exception:
        return {}

def _save_translation_cache():
    try:
        entries = [
            [TRANSLATION_CACHE_VERSION, k[0], k[1], v[0], v[1]]
            for k, v in _TRANSLATION_CACHE.items()
        ]
        with open(TRANSLATION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
    except Exception as e:
        print(f"[翻訳キャッシュ] 保存失敗: {e}", flush=True)

_TRANSLATION_CACHE = _load_translation_cache()

def _cache_set_translation(key, value):
    _TRANSLATION_CACHE[key] = value
    if len(_TRANSLATION_CACHE) > TRANSLATION_CACHE_MAX:
        del _TRANSLATION_CACHE[next(iter(_TRANSLATION_CACHE))]

def _translate_batch(items_in):
    """items_in リストをAPIで翻訳し、結果リストを返す。失敗時は空リスト"""
    prompt = TRANSLATE_PROMPT_BASE + json.dumps(items_in, ensure_ascii=False)
    text = call_gemini(
        prompt,
        max_tokens=6000,
        json_mode=True,
        model=GEMINI_TRANSLATION_MODEL,
    )
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    if not text.startswith("["):
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            text = match.group(0)
    return json.loads(text)

def translate_titles(articles, max_items=None):
    if not API_KEY:
        return articles
    targets_all = [
        (i, a)
        for i, a in enumerate(articles)
        if needs_translation(a)
    ]
    # Noneなら返却する候補をすべて翻訳する。検索時の大きな事前プールだけは
    # 呼び出し元がmax_itemsを指定して上限を設ける。
    targets = targets_all if max_items is None else targets_all[:max_items]
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

    # バッチをまとめてAPI呼び出し回数を抑える（呼び出し過多によるレート制限429を避けるため）
    from concurrent.futures import ThreadPoolExecutor as _TPE
    BATCH_SIZE = 20
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
    # 同時リクエストがレート制限(429)を誘発しやすいため、直列実行にする。
    with _TPE(max_workers=1) as ex:
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
            if not title_ja:
                # title_jaが空はGemini側の処理漏れ（レート制限・出力形式の乱れ等）とみなす。
                # ここでapplied扱いにすると再試行対象から外れ、さらに下でキャッシュに
                # 空文字が永続保存されると、同じ見出しの記事が以後ずっと未翻訳のまま
                # （英語表示）になり二度と再翻訳されなくなるため、何もせずスキップして
                # missing_targetsでの再試行に回す。
                continue
            articles[orig_idx]["title_en"] = articles[orig_idx]["title"]
            articles[orig_idx]["title"] = title_ja
            if summary_ja:
                articles[orig_idx]["summary_en"] = articles[orig_idx].get("summary", "")
                articles[orig_idx]["summary"] = summary_ja
            original = target_map.get(orig_idx)
            if original:
                _cache_set_translation((original.get("title", ""), original.get("summary", "")), (title_ja, summary_ja))
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
        retry_batches = [missing_targets[i:i+BATCH_SIZE] for i in range(0, len(missing_targets), BATCH_SIZE)]
        with _TPE(max_workers=1) as ex:
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
                _cache_set_translation(
                    (article.get("title", ""), article.get("summary", "")),
                    (articles[idx]["title"], article.get("summary", "")),
                )

    _save_translation_cache()
    print(f"[翻訳] 計{len(targets)}件を日本語表示に変換完了", flush=True)
    return articles

def get_articles(
    category,
    lang,
    limit=10,
    include_x=False,
    recent_days=None,
    translate=True,
    fetch_timeout=RSS_FETCH_TIMEOUT,
    fast_budget=RSS_FETCH_FAST_BUDGET,
    max_budget=RSS_FETCH_MAX_BUDGET,
    keyword=None,
    cancel_event=None,
):
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed

    ensure_not_cancelled(cancel_event)
    if keyword and not category:
        # キーワード検索 + カテゴリ未選択: 全カテゴリのフィードを対象にする
        seen_feed_urls = set()
        feeds = []
        for cat_feeds in RSS_FEEDS.values():
            for feed in cat_feeds:
                if feed["url"] not in seen_feed_urls:
                    seen_feed_urls.add(feed["url"])
                    feeds.append(feed)
    else:
        feeds = RSS_FEEDS.get(category, RSS_FEEDS["AI・機械学習"])
    jp_sources = set(JP_PRIORITY_SOURCES)

    def _is_jp_source(source):
        return any(jp in source for jp in jp_sources)

    # RSS / GitHub Releases / Docs更新 をすべて同時並列フェッチ
    def _fetch_rss(feed, article_type=None):
        base_lim = 3 if feed["source"].startswith("arxiv") else RSS_PER_FEED_LIMIT
        if keyword:
            # キーワード検索時は検索対象プールを広げる。カテゴリ指定時はフィード数が少ない分さらに広げる
            lim = base_lim * (8 if category else 12)
        elif fetch_timeout >= RSS_FULL_FETCH_TIMEOUT:
            # カテゴリ補完時は過去数日分まで候補プールを広げる
            multiplier = TODAY_FULL_FETCH_MULTIPLIER if days_limit == 0 else 4
            lim = base_lim * multiplier
        else:
            lim = base_lim
        items = fetch_configured_source(
            feed, limit=lim, article_type=article_type, timeout=fetch_timeout
        )
        return "jp" if _is_jp_source(feed["source"]) else "other", items

    def _fetch_group(feed, article_type, per_limit):
        if keyword and not category:
            lim = per_limit * 8
        elif keyword or fetch_timeout >= RSS_FULL_FETCH_TIMEOUT:
            multiplier = TODAY_FULL_FETCH_MULTIPLIER if (not keyword and days_limit == 0) else 4
            lim = per_limit * multiplier
        else:
            lim = per_limit
        items = fetch_configured_source(
            feed, limit=lim, article_type=article_type, timeout=fetch_timeout
        )
        if keyword and not category:
            return "jp" if _is_jp_source(feed["source"]) else "other", items
        return "special", items

    if keyword and not category:
        seen_special_urls = set()
        github_feeds = []
        docs_feeds = []
        for cat_feeds in GITHUB_RELEASE_FEEDS.values():
            for feed in cat_feeds:
                if feed["url"] not in seen_special_urls:
                    seen_special_urls.add(feed["url"])
                    github_feeds.append(feed)
        for cat_feeds in DOCS_UPDATE_FEEDS.values():
            for feed in cat_feeds:
                if feed["url"] not in seen_special_urls:
                    seen_special_urls.add(feed["url"])
                    docs_feeds.append(feed)
    else:
        github_feeds = GITHUB_RELEASE_FEEDS.get(category, [])
        docs_feeds = DOCS_UPDATE_FEEDS.get(category, [])

    all_tasks = (
        [(feed, None) for feed in feeds]
        + [(feed, "github_release") for feed in github_feeds]
        + [(feed, "docs_update")   for feed in docs_feeds]
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
        # 早期終了の判定では「最終的に候補として残りうる記事」だけを数える。
        # 取得済み全件で数えると、言語フィルタ・カテゴリ関連度フィルタで後から除外される
        # 記事でカウントが埋まり、必要なフィードの到着を待たずに打ち切ってしまう。
        # 例: 海外検索で応答の速い国内フィードだけが先に返るとその時点で打ち切られ、
        # 海外フィードが全てキャンセルされて言語フィルタ後の候補がほぼ0件になる。
        if lang == "jp":
            pool = jp_items + special_items
        else:
            pool = special_items + other_items
        seen = set()
        count = 0
        for article in pool:
            url = article.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            if category and not keyword and not is_category_relevant(article, category):
                continue
            age_days = article_age_days(article)
            if article.get("type") == "official_x" or (age_days is not None and 0 <= age_days <= days_limit):
                count += 1
        return count

    # カテゴリ別フィード数が増え続けており(最多のAI・機械学習で30件超)、
    # max_workers=12では全フィードを同時実行できずタイムアウトが多発していた。
    # I/Oバウンドな取得なのでワーカー数を増やしても安全なため、タスク数に合わせて拡大する。
    executor = ThreadPoolExecutor(max_workers=max(30, len(all_tasks)))
    futures = {}  # future -> (tag_or_atype, source_name)
    processed = set()
    required_official_futures = set()
    try:
        for feed, atype in all_tasks:
            ensure_not_cancelled(cancel_event)
            if atype in ("github_release", "docs_update"):
                f = executor.submit(_fetch_group, feed, atype, SPECIAL_PER_FEED_LIMIT)
                futures[f] = (atype, feed["source"])
            else:
                f = executor.submit(_fetch_rss, feed)
                futures[f] = ("rss", feed["source"])
            if feed["source"] in AI_PRIORITY_OFFICIAL_SOURCES:
                required_official_futures.add(f)
        started_at = _time.monotonic()

        def _required_officials_processed():
            return required_official_futures.issubset(processed)

        try:
            completed_iter = as_completed(futures, timeout=fast_budget)
            for future in completed_iter:
                ensure_not_cancelled(cancel_event)
                tag, items = future.result()
                processed.add(future)
                _store_items(tag, items)
                # 十分な件数が集まっても、AI優先公式ソースの完了前には打ち切らない。
                if _recent_candidate_count() >= limit and _required_officials_processed():
                    break
        except TimeoutError:
            pass

        ensure_not_cancelled(cancel_event)
        # fast_budget内に終わらなかった公式ソースは、各取得処理自身のタイムアウトまで
        # 必ず待つ。これにより高頻度メディア1件だけでlimitに達しても公式を取りこぼさない。
        required_pending = [f for f in required_official_futures if f not in processed]
        for future in as_completed(required_pending):
            ensure_not_cancelled(cancel_event)
            tag, items = future.result()
            processed.add(future)
            _store_items(tag, items)

        pending = [future for future in futures if future not in processed and not future.done()]
        if pending and _recent_candidate_count() < limit:
            remaining_budget = max(0.0, max_budget - (_time.monotonic() - started_at))
            if remaining_budget > 0:
                try:
                    for future in as_completed(pending, timeout=remaining_budget):
                        ensure_not_cancelled(cancel_event)
                        tag, items = future.result()
                        processed.add(future)
                        _store_items(tag, items)
                        if _recent_candidate_count() >= limit and _required_officials_processed():
                            break
                except TimeoutError:
                    pass

        timed_out = [futures[f][1] for f in futures if f not in processed and not f.done()]
        if timed_out:
            print(f"[RSS] タイムアウト({len(timed_out)}件): {timed_out}", flush=True)
        for future in futures:
            if future.done():
                continue
            future.cancel()
    finally:
        if cancel_event and cancel_event.is_set():
            for future in futures:
                future.cancel()
        shutdown_executor(executor)

    ensure_not_cancelled(cancel_event)
    # 予算内に完了したが、as_completedのタイムアウト直後にdoneになったものを拾う
    for future in futures:
        ensure_not_cancelled(cancel_event)
        if future in processed:
            continue
        if future.done() and not future.cancelled():
            try:
                tag, items = future.result()
            except Exception:
                continue
            _store_items(tag, items)

    # どのフィードから何件（うち今日何件）取得できたかをログ出力
    import time as _log_time
    _today_jst = __import__('datetime').datetime.now(__import__('datetime').timezone(__import__('datetime').timedelta(hours=9))).date()
    _source_summary = {}
    for a in jp_items + other_items + special_items:
        src = a.get("source", "?")
        age = article_age_days(a)
        entry = _source_summary.setdefault(src, [0, 0])
        entry[0] += 1
        if age == 0:
            entry[1] += 1
    today_total = sum(v[1] for v in _source_summary.values())
    today_sources = {k: v for k, v in _source_summary.items() if v[1] > 0}
    print(f"[RSS取得結果] 合計{sum(v[0] for v in _source_summary.values())}件 今日{today_total}件 / ソース数{len(_source_summary)} 今日あり={list(today_sources.keys())}", flush=True)

    if include_x:
        ensure_not_cancelled(cancel_event)
        special_items += get_official_x_candidates(category, limit=2)

    if lang == "jp":
        # 国内: 海外ソースは候補に含めない
        all_items = jp_items + special_items
        if category == "AI・機械学習":
            # AI重要3社の公式情報だけは国内モードでも例外的に含める。
            all_items += [
                a for a in other_items
                if a.get("source") in AI_PRIORITY_OFFICIAL_SOURCES
            ]
    else:
        # 海外: 国内ソースは候補に含めない
        all_items = special_items + other_items
    unique = []
    for a in all_items:
        a["ageDays"] = article_age_days(a)
        unique.append(a)
    if category and not keyword:
        before_filter = len(unique)
        unique = [a for a in unique if is_category_relevant(a, category)]
        removed = before_filter - len(unique)
        if removed:
            print(f"[カテゴリ絞り込み] {category}: 関連度の低い候補を{removed}件除外", flush=True)
    def _article_sort_key(a):
        # official_blogもgithub_release/docs_update/official_xと同じく常に
        # 優先扱いにする。以前はここに含まれておらず、同一ニュースの重複統合時に
        # rss_newsの見出しが代表記事として残りやすくなっていた。
        return (
            0 if (a.get("type") in ("official_blog", "github_release", "docs_update", "official_x")) else (
                0 if (lang == "jp" and _is_jp_source(a.get("source", ""))) else
                0 if (lang != "jp" and not _is_jp_source(a.get("source", ""))) else
                1
            ),
            -a.get("sortTime", 0),
            -a.get("trustScore", 0),
        )

    unique.sort(key=_article_sort_key)
    seen = set()
    deduplicated = []
    for article in unique:
        identity_keys = article_identity_keys(article)
        if not identity_keys:
            continue
        match = None
        if any(key in seen for key in identity_keys):
            match = next(
                (e for e in deduplicated if set(article_identity_keys(e)) & set(identity_keys)),
                None,
            )
        if match is None:
            match = next(
                (e for e in deduplicated if articles_describe_same_story(article, e)),
                None,
            )
        if match is not None:
            # 他媒体でも同一ニュースが報道されている件数（自分自身を含む）を記録。
            # ⑥類似確認（他媒体での既出度合い）のためのシグナルとしてクライアントに渡す。
            match["coverageCount"] = match.get("coverageCount", 1) + 1
            continue
        seen.update(identity_keys)
        article["coverageCount"] = 1
        deduplicated.append(article)
    duplicate_count = len(unique) - len(deduplicated)
    if duplicate_count:
        print(f"[重複除外] 同一記事の候補を{duplicate_count}件除外", flush=True)
    unique = deduplicated

    if keyword:
        kw = keyword.strip().lower()
        # 「今日」指定ではキーワード検索でも当日公開の記事だけに限定する。
        # 通常のキーワード検索は従来どおり広めの期間から一致記事を探す。
        keyword_max_age_days = 0 if days_limit == 0 else (90 if not category else 30)
        pool = [
            a for a in unique
            if (
                a.get("type") == "official_x" and days_limit != 0
            ) or (
                a.get("ageDays") is not None
                and 0 <= a["ageDays"] <= keyword_max_age_days
            )
        ]
        # 英語タイトルのまま日本語キーワードに一致しない記事も拾えるよう、
        # 候補プールを先に翻訳してからキーワード一致を判定する
        if translate:
            translate_pool_size = 160 if not category else 80
            pool = translate_titles(pool[:translate_pool_size], max_items=translate_pool_size) + pool[translate_pool_size:]

        def _match(a):
            haystack = " ".join(str(a.get(k, "")) for k in ("title", "summary", "title_en", "summary_en", "source")).lower()
            return kw in haystack

        matched = [a for a in pool if _match(a)]
        matched.sort(key=lambda a: -a.get("sortTime", 0))
        matched = matched[:limit]
        matched = filter_candidates_with_article_body(matched, limit, cancel_event)
        if translate:
            matched = translate_titles(matched)
        return matched

    recent = [
        a for a in unique
        if (
            a.get("type") == "official_x" and days_limit != 0
        ) or (
            a.get("ageDays") is not None and 0 <= a["ageDays"] <= days_limit
        )
    ]
    # 取得できた候補を全て新しい順に並べ、上から limit 件を採用する
    # （ソース・種別ごとの上限は設けない。本文が取得できない候補は
    # filter_candidates_with_article_body が内部で予備を含めて補う）。
    recent = sort_articles_newest_first(recent)
    candidate_pool = recent
    if category == "AI・機械学習":
        official_candidates = [
            a for a in unique
            if (
                a.get("source") in AI_PRIORITY_OFFICIAL_SOURCES
                and a.get("ageDays") is not None
                and a.get("ageDays") >= 0
            )
        ]
        candidate_pool = reserve_ai_official_articles(
            recent, limit, official_candidates=official_candidates
        )
    articles = filter_candidates_with_article_body(candidate_pool, limit, cancel_event)
    # 公式枠を本文確認の先頭に置いた影響を表示順には残さず、通常の新着順へ戻す。
    articles = sort_articles_newest_first(articles)
    if translate:
        articles = translate_titles(articles)
    return articles


HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>IT記事 投稿ジェネレーター</title>
<!-- iPhone ホーム画面追加（PWA）用 -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="記事投稿">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#ea580c">
<link rel="apple-touch-icon" href="/apple-touch-icon.png?v=20260704c">
<link rel="icon" type="image/png" href="/apple-touch-icon.png?v=20260704c">
<link rel="manifest" href="/manifest.webmanifest?v=20260704c">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; color: #1a1a1a; min-height: 100vh; padding: calc(2rem + env(safe-area-inset-top, 0px)) max(1rem, env(safe-area-inset-right, 0px)) calc(2rem + env(safe-area-inset-bottom, 0px)) max(1rem, env(safe-area-inset-left, 0px)); }
  .container { max-width: 680px; margin: 0 auto; }
  h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .app-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: .45rem; }
  .app-title { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; min-width: 0; margin: 0; line-height: 1.25; }
  .logout-link { flex-shrink: 0; font-size: .75rem; color: #999; text-decoration: none; border: 1px solid #e5e5e5; border-radius: 8px; padding: 4px 10px; white-space: nowrap; margin-top: 2px; }
  .logout-link:hover { background: #fff; color: #555; }
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
  .cancel-fetch-btn { margin-left: auto; font-size: 12px; padding: 5px 10px; border-radius: 8px; border: 1px solid #ef4444; color: #b91c1c; background: #fff5f5; cursor: pointer; display: none; }
  .cancel-fetch-btn:hover { background: #fee2e2; }
  .fetch-info { font-size: 12px; color: #888; margin: -2px 0 10px; }
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
  .coverage-badge { font-size: 11px; padding: 2px 7px; border-radius: 100px; background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }
  .article-link-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .article-link-btn { font-size: 12px; padding: 5px 10px; border-radius: 8px; border: 1px solid #ddd; background: #fff; color: #1a1a1a; text-decoration: none; line-height: 1; }
  .article-link-btn:hover { background: #f5f5f5; text-decoration: none; }
  .article-link-btn.translate { border-color: #bfdbfe; background: #eff6ff; color: #2563eb; }
  .article-link-btn.translate:hover { background: #dbeafe; }
  .cand-check { width: 18px; height: 18px; border-radius: 50%; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; margin-top: 2px; }
  .cand-card.selected .cand-check { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
  .sticky-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #fff; border-top: 1px solid #e5e5e5; padding: .75rem 1rem; display: none; z-index: 100; box-shadow: 0 -4px 16px rgba(0,0,0,.08); }
  .sticky-bar-inner { max-width: 680px; margin: 0 auto; display: flex; flex-direction: column; align-items: stretch; gap: 8px; }
  .sticky-article-title { font-size: 13px; color: #555; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #selectedOpinionSlot:empty { display: none; }
  #selectedOpinionSlot #opinionPanel { background: transparent !important; border: none !important; padding: 0 !important; margin: 0 !important; }
  .sticky-gen-btn { font-size: 14px; padding: 10px 20px; border-radius: 10px; border: none; background: #1a1a1a; color: #fff; cursor: pointer; font-weight: 500; width: 100%; }
  .sticky-gen-btn:hover { opacity: .85; }
  .sticky-gen-btn:disabled { opacity: .4; cursor: not-allowed; }
  body.has-sticky { padding-bottom: calc(210px + env(safe-area-inset-bottom, 0px)); }
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
  .angle-outline-box { background: #f5f8ff; border: 1px solid #dbe6ff; border-radius: 8px; padding: .7rem .9rem; margin-bottom: 12px; font-size: 12.5px; color: #334; }
  .angle-outline-box .angle-line { font-weight: 500; margin-bottom: 4px; }
  .angle-outline-box .outline-list { margin: 0; padding-left: 1.1rem; color: #556; }
  .angle-outline-box .outline-list li { margin-bottom: 2px; }
  .article-title a { color: inherit; text-decoration: none; }
  .article-title a:hover { text-decoration: underline; }
  .tweet-label { font-size: 11px; font-weight: 600; color: #888; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 6px; }
  .tweet-box { background: #f9f9f9; border-radius: 8px; padding: 1rem; font-size: 16px; line-height: 1.65; white-space: pre-wrap; word-break: break-all; margin-bottom: 6px; outline: none; min-height: 80px; border: 1px solid transparent; }
  .tweet-box:focus { border-color: #ddd; }
  .char-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .char-count { font-size: 12px; color: #aaa; }
  .char-count.warn { color: #f59e0b; }
  .char-count.over { color: #ef4444; }
  .shorten-btn { font-size: 12px; padding: 4px 10px; border-radius: 8px; border: 1px solid #f59e0b; color: #b45309; background: #fffbeb; cursor: pointer; display: none; align-items: center; gap: 4px; }
  .action-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .action-btn { font-size: 13px; padding: 9px 16px; border-radius: 8px; border: 1px solid #ddd; cursor: pointer; display: flex; align-items: center; gap: 6px; background: #fff; color: #1a1a1a; transition: all .15s; }
  .action-btn:hover { background: #f5f5f5; }
  .img-prompt-section { margin-top: 14px; padding-top: 14px; border-top: 1px solid #eee; }
  .img-prompt-btn { font-size: 12px; padding: 7px 12px; border-radius: 8px; border: 1px solid #bfdbfe; color: #2563eb; background: #eff6ff; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
  .img-prompt-btn:hover { background: #dbeafe; }
  .img-prompt-box { display: none; background: #f9f9f9; border-radius: 8px; padding: .75rem; font-size: 12.5px; line-height: 1.6; margin-top: 8px; color: #444; word-break: break-word; }
  .img-prompt-copy { font-size: 11px; padding: 3px 9px; border-radius: 6px; border: 1px solid #ddd; background: #fff; cursor: pointer; margin-top: 6px; }
  .x-btn { background: #1a1a1a; color: #fff; border-color: #1a1a1a; margin-left: auto; font-weight: 500; }
  .x-btn:hover { opacity: .85; }
  .history-section { margin-top: 1.75rem; border-top: 1px solid #e5e5e5; padding-top: 1.25rem; display: none; }
  .history-item { font-size: 13px; color: #888; padding: 7px 0; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; gap: 8px; cursor: pointer; }
  .history-item:hover .hi-title { color: #1a1a1a; }
  .hi-slot { font-size: 11px; color: #bbb; flex-shrink: 0; }
  .hi-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hi-time { font-size: 11px; color: #bbb; flex-shrink: 0; }
  .rss-badge { font-size: 10px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; border-radius: 100px; padding: 2px 8px; display: inline-block; line-height: 1.35; }
  @media (max-width: 420px) {
    h1 { font-size: 19px; }
    .app-header { align-items: flex-start; }
    .logout-link { padding: 5px 10px; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="app-header">
    <h1 class="app-title"><span>📰 IT記事 投稿ジェネレーター</span><span class="rss-badge">複数ソース版</span></h1>
    <a href="/logout" class="logout-link">ログアウト</a>
  </div>
  <p class="subtitle">AIの最新情報を選び、投稿文と画像プロンプトを作成</p>

  <div style="padding:1rem;margin-bottom:1rem;background:#fff7ed;border:1px solid #fed7aa;border-radius:12px">
    <div class="section-label" style="margin:0 0 5px">✍️ キーワードから新規記事を作る</div>
    <p style="margin:0 0 10px;color:#7c4a03;font-size:13px;line-height:1.5">検索結果を使わず、キーワードと指示だけから記事の下書きを作成します。</p>
    <input type="text" id="articleKeyword" maxlength="160" placeholder="例：中小企業におけるAIエージェントの活用" style="width:100%;box-sizing:border-box;padding:0.6rem 0.8rem;border:1px solid #fdba74;border-radius:8px;font-size:16px">
    <div style="display:flex;gap:8px;margin-top:9px;flex-wrap:wrap">
      <select id="articleAudience" style="flex:1;min-width:150px;padding:8px;border:1px solid #fed7aa;border-radius:8px;background:#fff;font:inherit;font-size:13px">
        <option value="AIに詳しくないビジネス担当者">ビジネス担当者向け</option>
        <option value="中小企業の経営者">中小企業の経営者向け</option>
        <option value="開発者・IT実務担当者">開発・IT担当者向け</option>
        <option value="AIに興味を持ち始めた一般読者">はじめての人向け</option>
      </select>
      <select id="articleLength" style="padding:8px;border:1px solid #fed7aa;border-radius:8px;background:#fff;font:inherit;font-size:13px">
        <option value="800">約800字</option>
        <option value="1500" selected>約1,500字</option>
        <option value="2500">約2,500字</option>
      </select>
    </div>
    <textarea id="articleInstruction" maxlength="800" placeholder="記事に入れたい内容・口調（任意）\n例：導入のメリットだけでなく、最初に確認すべき注意点も入れる。" style="width:100%;min-height:66px;margin-top:9px;padding:9px 10px;border:1px solid #fed7aa;border-radius:8px;resize:vertical;font:inherit;font-size:13px;line-height:1.5"></textarea>
    <button class="gen-btn" id="articleGenerateBtn" style="margin-top:10px;background:#ea580c">✍️ 記事の下書きを生成</button>
  </div>

  <input type="text" id="keywordBox" placeholder="🔍 キーワードで記事を検索" style="width:100%;box-sizing:border-box;padding:0.6rem 0.8rem;margin-bottom:1rem;border:1px solid #e5e5e5;border-radius:8px;font-size:16px">

  <div class="section-label">カテゴリ</div>
  <div class="btn-group" id="catGroup"></div>

  <div class="section-label">取得先</div>
  <div class="btn-group" id="langGroup"></div>

  <div class="source-options">
    <label class="source-toggle">
      <input type="checkbox" id="officialFirst">
      <span>公式優先</span>
    </label>
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
  <div class="status-bar" id="statusBar"><div class="spinner"></div><span id="statusText"></span><button class="cancel-fetch-btn" id="cancelFetchBtn">キャンセル</button></div>
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
    <div class="fetch-info" id="candidateInfo"></div>
    <div id="candidatesList"></div>
    <button class="more-btn" id="moreBtn">もっと見る</button>
  </div>

  <div class="sticky-bar" id="stickyBar">
    <div class="sticky-bar-inner">
      <span class="sticky-article-title" id="stickyTitle">記事を選択してください</span>
      <div id="selectedOpinionSlot"></div>
      <button class="sticky-gen-btn" id="selectBtn" disabled>✏️ 投稿文を生成</button>
    </div>
  </div>

  <div class="result-card" id="resultCard">
    <div id="resultHeader"></div>
    <div class="article-meta" id="articleMeta"></div>
    <div class="article-title" id="articleTitle"></div>
    <div class="angle-outline-box" id="angleOutlineBox" style="display:none"></div>
    <div class="tweet-label">投稿文（編集可）</div>
    <div class="tweet-box" id="tweetBox" contenteditable="true"></div>
    <div class="char-row">
      <span class="char-count" id="charCount">0 / 4000文字</span>
      <button class="shorten-btn" id="shortenBtn">✂️ 自動短縮</button>
    </div>
    <div class="action-row">
      <button class="action-btn" id="backBtn">← 選び直す</button>
      <button class="action-btn" id="copyBtn">📋 コピー</button>
      <button class="action-btn x-btn" id="xBtn">X で投稿</button>
    </div>
    <div class="img-prompt-section">
      <button class="img-prompt-btn" id="imgPromptBtn">🎨 画像生成プロンプトを作成</button>
      <button class="img-prompt-copy" id="imgPromptCopyBtn" style="display:none">📋 プロンプトをコピー</button>
      <div class="img-prompt-box" id="imgPromptBox"></div>
    </div>
  </div>

  <div class="result-card" id="articleDraftCard">
    <div class="tweet-label">新規記事の下書き（編集可）</div>
    <div class="article-draft-note">キーワードから生成した下書きです。最新ニュースや固有の数値を扱う場合は、公開前に一次情報で確認してください。</div>
    <div class="tweet-box" id="articleDraftBox" contenteditable="true" style="min-height:260px;white-space:pre-wrap"></div>
    <div class="action-row" style="margin-top:12px">
      <button class="action-btn" id="articleDraftCopyBtn">📋 記事をコピー</button>
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
let activeOpinionStyle='practical';
let activeCat='AI・機械学習', activeLang='en';
const INITIAL_VISIBLE_COUNT=20;
let candidates=[], selectedIdx=-1, postHistory=[], visibleCount=INITIAL_VISIBLE_COUNT;
let lastFetchInfo=null;
let currentFetchRequestId=null;
let currentFetchController=null;
let fetchCancelled=false;
let lastArticle=null, lastArticleBody='';

function el(id){return document.getElementById(id);}

function pillStyle(active){
  return active
    ?'font-size:13px;padding:7px 18px;border-radius:100px;border:none;background:#1a1a1a;color:#fff;cursor:pointer;font-weight:500;line-height:1.4'
    :'font-size:13px;padding:7px 18px;border-radius:100px;border:1px solid #ddd;background:#fff;color:#888;cursor:pointer;line-height:1.4';
}

function renderCats(){
  el('catGroup').innerHTML=CATS.map(c=>`<button onclick="setCat('${c}')" style="${pillStyle(activeCat===c)}">${c}</button>`).join('');
  el('catGroup').style.opacity=activeCat===null?'0.4':'1';
}
function renderLangs(){
  el('langGroup').innerHTML=[{k:'jp',l:'🇯🇵 国内'},{k:'en',l:'🌐 海外'}].map(l=>`<button onclick="setLang('${l.k}')" style="${pillStyle(activeLang===l.k)}">${l.l}</button>`).join('');
}
function renderAiKeywords(){
  el('aiKeywordRow').innerHTML=AI_KEYWORDS.map(keyword=>`<button onclick="setAiKeyword('${keyword}')" style="font-size:12px;padding:5px 9px;border:1px solid #cbd5e1;border-radius:999px;background:#fff;color:#475569;cursor:pointer">${keyword}</button>`).join('');
}
function setAiKeyword(keyword){
  el('keywordBox').value=keyword;
  activeCat='AI・機械学習';
  renderCats();
  el('keywordBox').focus();
}

el('articleGenerateBtn').onclick=async()=>{
  const keyword=el('articleKeyword').value.trim();
  if(!keyword){
    showError('記事にしたいキーワードを入力してください');
    el('articleKeyword').focus();
    return;
  }
  const audience=el('articleAudience').value;
  const length=Number(el('articleLength').value)||1500;
  const instruction=el('articleInstruction').value.trim().slice(0,800);
  const button=el('articleGenerateBtn');
  button.disabled=true;
  button.innerHTML='<div class="spinner"></div>記事を生成中...';
  setStatus(true,'キーワードから記事の構成と本文を作成中...');
  try{
    const data=await callProxy([{role:'user',content:`あなたは日本語のAI・IT分野に詳しい編集者です。以下の指定だけを使い、公開前に編集できる記事の下書きをMarkdownで作成してください。

【テーマ】
${keyword}

【想定読者】
${audience}

【目安の長さ】
約${length}字

【追加指示】
${instruction||'なし'}

【構成】
- 最初に、内容を端的に表す記事タイトルをMarkdownのH1（# ）で1つ書く
- 導入、H2見出し2〜4個、まとめの順にする
- 読者が「何を理解し、次に何をすればよいか」が分かる実用的な内容にする

【正確さのルール】
- この依頼には検索結果や一次情報が渡されていない。直近の発表、現在の製品仕様、価格、利用者数、調査結果、日付、固有の数値を事実として書かない
- 「最新」「現在」「先日発表」など、鮮度を示す表現を使わない
- 一般的に説明できる内容に限定し、不確かな内容は「確認が必要」「場合がある」と明示する
- 存在しない機能・事例・引用・出典を作らない
- ハッシュタグ、URL、前置き、生成に関する説明は不要。完成した記事本文のみ返す`}]);
    const draft=data.text.trim();
    if(!draft)throw new Error('記事本文を作成できませんでした');
    el('articleDraftBox').innerText=draft;
    el('articleDraftCard').style.display='block';
    el('articleDraftCard').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){
    showError('記事生成に失敗: '+e.message);
  }finally{
    setStatus(false);
    button.disabled=false;
    button.textContent='✍️ 記事の下書きを生成';
  }
};
function renderOpinionStyles(){
  const includeOpinion=el('includeOpinion')&&el('includeOpinion').checked;
  el('opinionStyleRow').style.display=includeOpinion?'flex':'none';
  el('opinionStyleRow').innerHTML=OPINION_STYLES.map(s=>`<button onclick="setOpinionStyle('${s.k}')" title="${s.desc}" style="${pillStyle(activeOpinionStyle===s.k)}">${s.l}</button>`).join('');
}
function setOpinionStyle(k){activeOpinionStyle=k;renderOpinionStyles();}

document.addEventListener('change',e=>{if(e.target.id==='includeOpinion')renderOpinionStyles();});

function setCat(c){
  if(el('keywordBox').value.trim()){
    // 検索ワードがある時はクリックでON/OFF切替（カテゴリ未選択=全カテゴリ検索）
    activeCat=(activeCat===c)?null:c;
  }else{
    activeCat=c;
  }
  renderCats();
}

el('keywordBox').oninput=(e)=>{
  if(!e.target.value.trim()&&activeCat===null){
    activeCat='AI・機械学習';
  }
  renderCats();
};
function setLang(l){activeLang=l;renderLangs();}

function setStatus(on,txt){el('statusText').textContent=txt||'';el('statusBar').style.display=on?'flex':'none';}
function setFetchCancelVisible(on){el('cancelFetchBtn').style.display=on?'inline-flex':'none';}
function showError(msg){const eb=el('errorBox');eb.textContent=msg;eb.style.display='block';setTimeout(()=>eb.style.display='none',6000);}
function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}

const CLIENT_IDLE_TIMEOUT_MS=30*60*1000;
let lastClientActivity=Date.now();
let lastSessionCheckAt=0;

function rememberClientActivity(){lastClientActivity=Date.now();}
['click','keydown','touchstart','pointerdown'].forEach(evt=>{
  document.addEventListener(evt,rememberClientActivity,{passive:true});
});

async function checkSessionOnResume(force=false){
  const now=Date.now();
  if(!force && now-lastSessionCheckAt<60000)return;
  lastSessionCheckAt=now;
  if(now-lastClientActivity>CLIENT_IDLE_TIMEOUT_MS){
    window.location.href='/login';
    return;
  }
  try{
    const r=await fetch(`/api/status?_=${now}`,{
      cache:'no-store',
      credentials:'same-origin',
      redirect:'follow'
    });
    const contentType=r.headers.get('content-type')||'';
    if(r.redirected || r.url.includes('/login') || !contentType.includes('application/json')){
      window.location.href='/login';
      return;
    }
    await r.json();
  }catch(e){
    console.warn('セッション確認失敗',e);
  }
}

window.addEventListener('pageshow',()=>checkSessionOnResume(true));
window.addEventListener('focus',()=>checkSessionOnResume(false));
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible')checkSessionOnResume(false);
});

function newRequestId(){
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function requestFetchCancel(){
  fetchCancelled=true;
  const requestId=currentFetchRequestId;
  if(currentFetchController)currentFetchController.abort();
  if(requestId){
    try{
      await fetch(`/api/cancel?request_id=${encodeURIComponent(requestId)}&_=${Date.now()}`,{cache:'no-store'});
    }catch(e){
      console.warn('キャンセル通知失敗', e);
    }
  }
}

el('cancelFetchBtn').onclick=()=>{
  if(!currentFetchRequestId)return;
  setStatus(true,'候補取得をキャンセル中...');
  requestFetchCancel();
};

async function fetchCandidatesWithRetry(category, lang, includeX, days, keyword, requestId, controller){
  let url=`/api/rss?category=${encodeURIComponent(category)}&lang=${lang}&include_x=${includeX}&days=${days}&request_id=${encodeURIComponent(requestId)}&_=${Date.now()}`;
  if(keyword)url+=`&keyword=${encodeURIComponent(keyword)}`;
  let lastError=null;
  for(let attempt=1;attempt<=3;attempt++){
    try{
      if(fetchCancelled)throw new Error('取得をキャンセルしました');
      if(attempt>1)setStatus(true,`候補取得を再試行中...（${attempt}/3）`);
      const r=await fetch(url,{cache:'no-store',signal:controller.signal});
      let data=null;
      try{data=await r.json();}catch(e){throw new Error(`応答を読み取れませんでした (${r.status})`);}
      if(data.cancelled)throw new Error('取得をキャンセルしました');
      if(!r.ok||data.error)throw new Error(data.error||`HTTP ${r.status}`);
      if(data.articles&&data.articles.length){
        lastFetchInfo={count:data.count||data.articles.length, todayCount:data.today_count??null, officialLatestCount:data.official_latest_count??0, category:data.category, lang:data.lang, days:data.days, expandedDays:data.expanded_days, includeX:data.include_x, usedFullFetch:data.used_full_fetch, keyword:data.keyword};
        console.log('[候補取得]', lastFetchInfo);
        return data.articles;
      }
      throw new Error(keyword?'該当する記事が見つかりませんでした':'記事が見つかりませんでした');
    }catch(e){
      if(e.name==='AbortError'||fetchCancelled)throw new Error('取得をキャンセルしました');
      lastError=e;
      if(attempt<3)await sleep(700*attempt);
    }
  }
  throw lastError||new Error('記事が見つかりませんでした');
}

async function callProxy(messages, jsonMode){
  const r=await fetch('/api/claude',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(jsonMode ? {messages, json_mode:true} : {messages})
  });
  const raw=await r.text();
  let data;
  try{ data=JSON.parse(raw); }catch(e){ data={error:raw}; }
  const contentType=(r.headers.get('content-type')||'').toLowerCase();
  if(r.redirected && (r.url.includes('/login') || !contentType.includes('application/json'))){
    window.location.href='/login';
    throw new Error('ログインの有効期限が切れました。再ログインしてください');
  }
  if(!r.ok){
    throw new Error(data.error||`APIエラー（${r.status}）`);
  }
  return data;
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

const POST_CHAR_LIMIT=4000; // X Premium会員の投稿上限

function updateChar(){
  const text=el('tweetBox').innerText;
  const urlRegex=/https?:\/\/[^\s]+/g;
  const urls=text.match(urlRegex)||[];
  const textWithoutUrls=text.replace(urlRegex,'');
  const len=xWeightedLen(textWithoutUrls)+urls.length*23;
  const remaining=POST_CHAR_LIMIT-len;
  el('charCount').textContent=`${len} / ${POST_CHAR_LIMIT}（残り ${remaining}）※日本語2・URL=23`;
  el('charCount').className='char-count'+(len>POST_CHAR_LIMIT?' over':len>POST_CHAR_LIMIT*0.9?' warn':'');
  el('xBtn').disabled=len>POST_CHAR_LIMIT;
  el('shortenBtn').style.display=len>POST_CHAR_LIMIT?'inline-flex':'none';
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
  if(lastFetchInfo){
    const mode=lastFetchInfo.lang==='en'?'海外':'国内';
    const period=String(lastFetchInfo.days)==='0'?'今日':`${lastFetchInfo.days}日以内`;
    const isExpanded=lastFetchInfo.expandedDays&&String(lastFetchInfo.expandedDays)!==String(lastFetchInfo.days);
    const expanded=isExpanded?` / ${lastFetchInfo.expandedDays}日以内で補完`:'';
    const retry='';
    const kw=lastFetchInfo.keyword?` / 検索:「${lastFetchInfo.keyword}」`:'';
    const catLabel=lastFetchInfo.category||'全カテゴリ';
    const officialNote=lastFetchInfo.officialLatestCount
      ?` / 3社の公式最新${lastFetchInfo.officialLatestCount}件を含む`:'';
    const todayNote=(lastFetchInfo.todayCount!=null&&lastFetchInfo.todayCount<lastFetchInfo.count)
      ?`（今日${lastFetchInfo.todayCount}件）`:'';
    el('candidateInfo').textContent=`${lastFetchInfo.count}件取得${todayNote} / ${catLabel} / ${mode} / ${period}${expanded}${officialNote}${retry}${kw}`;
  }else{
    el('candidateInfo').textContent='';
  }
  const OFFICIAL_TYPES=new Set(['official_blog','github_release','docs_update']);
  const officialFirst=el('officialFirst')&&el('officialFirst').checked;
  // origIdxは常にcandidates配列上の元のインデックス（selectCand/candidates[i]参照に使う）。
  // 「公式優先」で表示順を並べ替えても、選択対象は表示位置ではなく元のインデックスで
  // 追跡しないと、並べ替え後に別の記事が選択されてしまう。
  let displayCandidates=candidates.map((a,origIdx)=>({a,origIdx}));
  if(officialFirst){
    displayCandidates.sort((x,y)=>{
      // 日付順を崩さず、同じ公開日時の候補だけ公式を優先する。
      const timeDiff=(Number(y.a.sortTime)||0)-(Number(x.a.sortTime)||0);
      if(timeDiff)return timeDiff;
      const xOff=OFFICIAL_TYPES.has(x.a.type)?1:0;
      const yOff=OFFICIAL_TYPES.has(y.a.type)?1:0;
      return yOff-xOff;
    });
  }
  const visibleCandidates=displayCandidates.slice(0, visibleCount);
  if(!displayCandidates.length){
    el('candidatesList').innerHTML='';
  }else{
    el('candidatesList').innerHTML=visibleCandidates.map(({a,origIdx},pos)=>{
    const sel=selectedIdx===origIdx;
    const title=escapeHtml(a.title);
    const summary=escapeHtml(a.summary);
    const source=escapeHtml(a.source);
    const published=escapeHtml(a.published);
    const typeLabel=escapeHtml(a.typeLabel||'RSSニュース');
    const officialGroup=escapeHtml(a.officialGroup||'');
    const url=escapeHtml(a.url);
    const checkLabel=sel?'✓':'';
    return `<div class="cand-card${sel?' selected':''}" onclick="selectCand(${origIdx})">
      <div class="cand-num">${pos+1}</div>
      <div class="cand-body">
        <div class="cand-title">${title}</div>
        ${summary?`<div class="cand-summary">${summary}</div>`:''}
        <div class="cand-meta">
          <span>${source}</span><span>${published}</span>
          ${a.isPriorityOfficialLatest?`<span class="trust-badge">${officialGroup} 公式最新</span>`:''}
          <span class="trust-badge">${typeLabel}・信頼度${a.trustScore||70}</span>
          ${a.coverageCount>1?`<span class="coverage-badge">他${a.coverageCount-1}媒体でも報道</span>`:''}
        </div>
        ${a.url?`<div class="article-link-row">
          <a class="article-link-btn" href="${url}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">参照URLを開く</a>
        </div>`:''}
      </div>
      <div class="cand-check">${checkLabel}</div>
    </div>`;
    }).join('');
  }
  // 記事選択後は、感想スタイルを投稿文生成ボタンの直上に表示
  const opPanel=el('opinionPanel');
  if(selectedIdx>=0){
    el('selectedOpinionSlot').appendChild(opPanel);
    opPanel.style.display='block';
  }else{
    opPanel.style.display='none';
  }
  const remaining=Math.max(displayCandidates.length-visibleCount,0);
  el('moreBtn').style.display=remaining>0?'block':'none';
  el('moreBtn').textContent=`もっと見る（残り${remaining}件）`;
}

function selectCand(i){
  selectedIdx=selectedIdx===i?-1:i;
  updateStickyBar();
  renderCands();
}

function updateStickyBar(){
  if(selectedIdx<0){
    el('selectBtn').disabled=true;
    el('stickyBar').style.display='none';
    document.body.classList.remove('has-sticky');
    return;
  }
  el('selectBtn').disabled=false;
  el('stickyBar').style.display='block';
  document.body.classList.add('has-sticky');
  el('stickyTitle').textContent=candidates[selectedIdx]?.title||'';
  el('selectBtn').textContent='✏️ 投稿文を生成';
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
    if(data.warning){
      console.warn('候補翻訳の一部に失敗:',data.warning);
      showError('一部の記事を翻訳できませんでした。少し待ってから候補を再取得してください。');
    }
    if(data.articles&&data.articles.length){
      const selectedArticle=selectedIdx>=0?candidates[selectedIdx]:null;
      candidates=data.articles;
      selectedIdx=selectedArticle?candidates.findIndex(a=>
        selectedArticle.url
          ? a.url===selectedArticle.url
          : a.title===selectedArticle.title&&a.source===selectedArticle.source
      ):-1;
      // 翻訳後の候補置き換えで選択記事が見つからなかった場合(selectedIdx=-1)に、
      // 古いタイトルのままのスティッキーバーが残らないよう表示も更新する
      updateStickyBar();
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
  el('recentDays').disabled=on;
  el('officialFirst').disabled=on;
}

el('officialFirst').onchange=()=>renderCands();

el('generateBtn').onclick=async()=>{
  el('errorBox').style.display='none';
  el('resultCard').style.display='none';
  el('candidatesSection').style.display='none';
  el('loadingSkels').style.display='block';
  el('loadingSkels').innerHTML=Array.from({length:5}).map(()=>`<div class="skel-card"><div class="skel" style="width:60%"></div><div class="skel" style="width:95%"></div><div class="skel" style="width:80%"></div></div>`).join('');
  el('generateBtn').disabled=true;
  el('generateBtn').innerHTML='<div class="spinner"></div>取得中...';
  fetchCancelled=false;
  currentFetchRequestId=newRequestId();
  currentFetchController=new AbortController();
  selectedIdx=-1;visibleCount=INITIAL_VISIBLE_COUNT;el('selectBtn').disabled=true;
  el('opinionPanel').style.display='none';
  el('stickyBar').style.display='none';
  document.body.classList.remove('has-sticky');
  setFetching(true);
  setStatus(true,'複数ソースから候補を取得中...');
  setFetchCancelVisible(true);
  try{
    const includeX='0';
    const days=el('recentDays').value;
    const keyword=el('keywordBox').value.trim();
    candidates=await fetchCandidatesWithRetry(activeCat||'',activeLang,includeX,days,keyword,currentFetchRequestId,currentFetchController);
    el('loadingSkels').style.display='none';
    setStatus(false);
    setFetchCancelVisible(false);
    setFetching(false);
    el('generateBtn').disabled=false;
    el('generateBtn').innerHTML='📡 複数ソースから候補を取得';
    currentFetchRequestId=null;
    currentFetchController=null;
    el('candidatesSection').style.display='block';
    el('opinionPanel').style.display='none';
    renderOpinionStyles();
    renderCands();
    translateCandidatesInBackground();
  }catch(e){
    el('loadingSkels').style.display='none';
    setStatus(false);
    setFetchCancelVisible(false);
    setFetching(false);
    el('generateBtn').disabled=false;
    el('generateBtn').innerHTML='📡 複数ソースから候補を取得';
    currentFetchRequestId=null;
    currentFetchController=null;
    if(e.message==='取得をキャンセルしました'){
      candidates=[];
      el('candidateInfo').textContent='';
      showError('候補取得をキャンセルしました');
    }else{
      showError('取得に失敗: '+e.message);
    }
  }
};

el('selectBtn').onclick=async()=>{
  if(selectedIdx<0)return;
  const article=candidates[selectedIdx];
  if(!article)return;
  const shareUrl=shareArticleUrl(article);
  const genBtnLabel='✏️ 投稿文を生成';
  el('selectBtn').disabled=true;
  el('selectBtn').innerHTML='<div class="spinner"></div>生成中...';
  setStatus(true,'記事本文を取得中...');
  try{
    // 記事本文を取得（失敗してもRSS概要にフォールバック）
    let articleBody='';
    if(article.url && article.type !== 'official_x'){
      try{
        const br=await fetch(`/api/fetch_article?url=${encodeURIComponent(article.url)}`);
        const bd=await br.json();
        if(bd.body && bd.body.length>100)articleBody=bd.body;
      }catch(e){ console.warn('記事取得失敗',e); }
    }
    const contextText=articleBody
      ? `記事本文（抜粋）:\n${articleBody}`
      : `RSS概要: ${article.summary||'概要なし'}`;

    // 他媒体での既出度合い（⑥類似確認）: 候補取得時に記録したcoverageCountを使う
    const coverageCount=article.coverageCount||1;
    const coverageNote=coverageCount>1
      ? `\n\n【他媒体での報道状況】\n「${article.title}」は他${coverageCount-1}媒体でも同様のニュースが確認できた（既出度が高い話題）。\n単純な事実紹介だけに終わらない独自性のある切り口を選ぶこと。`
      : '';

    // 最初に根拠となる事実を構造化する。以後の生成ではこの要点を制約として使い、
    // タイトルからの推測や、数値・固有名詞の取り違えを抑える。
    setStatus(true,'記事の事実と構成を整理中...');
    let angle='記事の具体的な変化と、それが利用者・実務に与える影響';
    let outline=[];
    let verifiedFacts=[];
    let termExplanations=[];
    try{
      const angleOutlineData=await callProxy([{role:'user',content:`以下の記事を読み、SNS投稿を書く前の事実整理と構成設計をしてください。

${contextText}${coverageNote}

【事実整理のルール】
- factsには本文またはRSS概要で明示されている事実だけを、重要な順に最大6件入れる
- 各factのevidenceには、その根拠となる原文中の短い連続した表現を一字も変えずに入れる
- 数字・日付・製品名・企業名・機能名・比較対象は原文どおり正確に保つ
- 記事にない因果関係、効果、将来予測、評価を補わない
- RSS概要しかない場合は、確認できる件数が少なくてもよい。推測で埋めない
- termsには、一般読者には難しい用語と、記事の文脈を変えない平易な説明を最大4件入れる

【切り口のルール】
- 単なる事実の要約ではなく、読者の興味を引く視点・観点を1つ選ぶ
- 記事に実際に書かれている情報に基づくこと（推測や記事にない一般論で切り口を作らない）
- 切り口は日本語1文（30〜60文字程度）

【構成のルール】
- 決定した切り口をもとに、投稿がどう展開するかを表す2〜4個の見出し（各10〜20文字程度）を考える

出力はJSON形式のみで回答する。説明や前置き、Markdownのコードブロックは一切不要。
形式: {"facts": [{"claim": "確認できる事実", "evidence": "原文からそのまま抜き出した根拠表現"}], "terms": [{"term": "用語", "plain": "平易な説明"}], "angle": "切り口の文", "outline": ["見出し1", "見出し2", ...]}`}], true);
      const parsed=JSON.parse(angleOutlineData.text.trim().replace(/^```(?:json)?\s*|\s*```$/g,''));
      const generatedAngle=(parsed.angle||'').trim();
      if(generatedAngle)angle=generatedAngle;
      if(Array.isArray(parsed.outline))outline=parsed.outline;
      if(Array.isArray(parsed.facts)){
        verifiedFacts=parsed.facts.filter(f=>
          f&&typeof f.claim==='string'&&f.claim.trim()&&
          typeof f.evidence==='string'&&f.evidence.trim().length>=4&&
          contextText.includes(f.evidence.trim())
        ).slice(0,6);
      }
      if(Array.isArray(parsed.terms))termExplanations=parsed.terms.filter(t=>t&&typeof t.term==='string'&&typeof t.plain==='string').slice(0,4);
    }catch(e){
      console.warn('事実整理・構成の生成に失敗。記事本文を直接使って続行します。',e);
    }
    const factInstruction=verifiedFacts.length
      ? `\n\n【原文の根拠を確認できた要点】\n${verifiedFacts.map((f,i)=>`${i+1}. ${f.claim}（根拠:「${f.evidence.trim()}」）`).join('\n')}`
      : '';
    const termInstruction=termExplanations.length
      ? `\n\n【用語の平易な説明】\n${termExplanations.map(t=>`- ${t.term}: ${t.plain}`).join('\n')}`
      : '';
    const angleOutlineInstruction=`\n\n【決定済みの切り口・構成（必ず反映する）】\n切り口: ${angle}${outline.length?`\n構成:\n${outline.map((o,i)=>`${i+1}. ${o}`).join('\n')}`:''}`;
    setStatus(true,'投稿文を生成中...');
    // XはURLを常に23文字としてカウントする。本文はURL込みでPOST_CHAR_LIMIT以内に収める
    const includeOpinion=el('includeOpinion').checked;
    const opinionStyleMap={
      impression: articleBody
        ? `記事本文を読んだうえで、特に印象的な事実・数字・技術名を1つ具体的に引用し「〜が面白い」「〜は要注目」など筆者の感想として1〜2文添える。抽象的な表現（「興味深い」「注目です」だけ）は避ける。`
        : 'RSS概要で確認できる特徴的な点にだけ触れ、断定を広げず1〜2文の感想を添える。',
      question: articleBody
        ? `記事本文の具体的な内容（機能名・数値・変化）を踏まえ、「〜を使ってみた方いますか？」「あなたの現場では〜はどう変わりそう？」など読者が答えやすい具体的な問いかけを1〜2文添える。`
        : '記事テーマに関連した読者への問いかけを1〜2文添える（「皆さんはどう思いますか？」など）。',
      practical: articleBody
        ? `記事本文から具体的な機能・変更点・数値を1〜2個取り上げ、それが実際の業務・開発現場でどう活きるか（何ができるようになるか、何が楽になるか、導入時に注意すべき点は何か）を2〜3文で具体的に書く。「〜があれば現場で〇〇できそう」で終わらせず、なぜそう言えるかまで踏み込む。`
        : 'RSS概要で確認できる範囲だけを使い、実務上のポイントを断定せず簡潔に1〜2文書く。',
      concern: articleBody
        ? `記事本文の内容に基づき、「〜という点はまだ課題」「〜が普及するには〇〇が必要では」など根拠のある懸念・考察を1〜2文添える。感情的・否定的にならず建設的なトーンで。`
        : 'RSS概要に課題や制約の記載がある場合だけ、それを根拠に建設的な考察を1〜2文添える。記載がなければ新しい懸念を作らない。',
    };
    const opinionInstruction=includeOpinion
      ? `\n\n【構成（厳守）】\n投稿は必ず2部構成にする。\n1. 前半: 記事の具体的な内容（事実・数値・固有名詞）を客観的に説明する\n2. 後半: 前半の内容を踏まえて視点を切り替え、下記スタイルの内容を書く\nスタイル: ${opinionStyleMap[activeOpinionStyle]||opinionStyleMap.practical}\n- 前半と後半が地続きにならないよう、視点の切り替わりが読者にわかる書き方にする\n- 「実務目線では、」「〇〇目線では、」のような定型ラベル表現は本文に書かない。文章の内容・トーンの変化だけで視点の転換を示すこと\n- 「興味深いです」「注目です」のような抽象的な締めだけは禁止` : '';
    const targetLenText='日本語350〜500文字程度';
    const shortMinChars=150;
    // 本文のみ生成（ハッシュタグ・URLは後付け）
    const mainPrompt=`以下の記事についてX投稿の本文を日本語で作成してください。

【記事情報】
タイトル: ${article.title}
ソース: ${article.source}（${article.typeLabel||'RSSニュース'}）
${contextText}
${factInstruction}${termInstruction}

【最重要: 記事内容を具体的・正確に反映する】
- 上記の記事本文（またはRSS概要）に実際に書かれている情報だけを根拠にする。タイトルからの推測や一般論で埋めない
- 「記事から確認済みの要点」がある場合はそこから重要なものを優先して使い、元の意味を変えない
- 記事中の具体的な事実を2〜3個（固有名詞・数値・機能名・日付など）選ぶ。ただしRSS概要に十分な情報がなければ件数を無理に満たさない
- 数字・日付・固有名詞は書き換えない。根拠のない効果・因果関係・将来予測を事実として断定しない
- 専門用語・略語が出てきたら、一般読者にも伝わるよう簡潔に噛み砕いて説明する（例: 「RAG（生成AIが外部情報を参照して回答する仕組み）」のように）
- 「〜が発表された」「〜が話題」のような曖昧な言い回しだけで終わらせず、「何が」「どう変わった/どうすごいのか」を具体的に書く
- 記事本文が取得できずRSS概要のみの場合は、憶測で詳細を作り込まず、分かる範囲を正確に書く

【ソース種別ごとの前半（記事内容説明）の書き方】
- GitHub Releases: 何が変わったかを具体的に2〜3文
- Docs更新: 仕様変更・新機能を具体的に2〜3文
- 公式X: 断定しすぎず「公式Xで確認」くらいの表現
- RSSニュース/Blog: 背景・具体的な数値や固有名詞を交えて2〜3文で紹介${opinionInstruction}

【文体（読みやすさ・惹きつけ方）】
- 書き出しの1文で読者の目を引く（意外な数値・変化・対比・問いかけなど）。「〜が発表されました」のような単調な書き出しは避ける
- 一文は40字前後を目安に区切り、長すぎる一文をだらだら続けない。文の長さや語尾に変化をつけ、単調なリズムにしない
- 「〜である」「〜となっている」のような硬い報告文調ではなく、語りかけるような自然な日本語にする
- 難しい概念は必要に応じて身近なたとえで説明する。ただし、たとえを記事中の事実のように書かない
- 1〜2文ごとに改行を入れ、スマホ画面でも読みやすい見た目にする

【文字数（X Premiumアカウントのため長文投稿可）】
- ${targetLenText}を目安にする
- 文字数を埋めるための水増しはせず、記事本文にある具体的な情報で自然に厚みを持たせる
- 短すぎる投稿（${shortMinChars}文字未満）は禁止
- 本文のみ回答

【その他の制約】
- 「速報」という言葉は絶対に使わない
- ハッシュタグ・URLは不要${angleOutlineInstruction}`;
    const data=await callProxy([{role:'user',content:mainPrompt}]);

    // 本文 + URL を組み立て（ハッシュタグなし）
    const calcLen=(t)=>{const u=t.match(/https?:\/\/[^\s]+/g)||[];return xWeightedLen(t.replace(/https?:\/\/[^\s]+/g,''))+u.length*23;};
    let body = data.text.trim().replace(/【速報】\s*/g,'').replace(/速報[：:]\s*/g,'').replace(/速報\s/g,'');
    const urls=shareUrl?[shareUrl]:[];
    const urlStr=shareUrl?'\n'+shareUrl:'';
    let tweet = body + urlStr;

    // 短すぎる場合は、上限に収まる範囲で本文だけを一度だけ膨らませる
    const expandThreshold=600;
    const bodyLen = calcLen(body);
    if(bodyLen < expandThreshold){
      setStatus(true,'投稿文を少し詳しく調整中...');
      try{
        const expanded=await callProxy([{role:'user',content:`以下のX投稿本文は短すぎます。下記の記事内容に実際に書かれている具体的な要点・背景・数値や固有名詞を補い、${targetLenText}の3〜5文にしてください。
${includeOpinion?`前半で記事内容を具体的に説明し、後半は視点を切り替えて${opinionStyleMap[activeOpinionStyle]||opinionStyleMap.practical}という内容を書く、2部構成にすること。「実務目線では、」「〇〇目線では、」のような定型ラベル表現は本文に書かないこと。`:''}
記事に無い情報を推測で足さないこと。専門用語は簡潔に噛み砕いて説明すること。
書き出しの1文で読者の目を引くこと。一文は40字前後で区切り、語りかけるような自然な日本語にすること（硬い報告文調は避ける）。1〜2文ごとに改行を入れること。
URLとハッシュタグは不要。本文のみ回答。
「速報」という言葉は使わない。

${contextText}

現在の本文:
${body}`}]);
        const expandedBody=expanded.text.trim().replace(/【速報】\s*/g,'').replace(/速報[：:]\s*/g,'').replace(/速報\s/g,'');
        if(expandedBody && calcLen(expandedBody + urlStr) <= POST_CHAR_LIMIT){
          body = expandedBody;
          tweet = body + urlStr;
        }
      }catch(e){ console.warn('本文拡張失敗',e); }
    }

    // 最終稿を記事と突き合わせて校正する。新しい内容を足す工程ではなく、
    // 根拠のない断定・数字の誤り・分かりにくい表現を除去するためのチェック。
    setStatus(true,'内容の正確さと読みやすさを確認中...');
    try{
      const reviewed=await callProxy([{role:'user',content:`以下のX投稿本文を、記事の根拠と一文ずつ照合して最終校正してください。

【校正ルール】
- 記事本文またはRSS概要で確認できない情報、因果関係、効果、将来予測は削除するか、感想・可能性だと明確にする
- 数字・日付・企業名・製品名・機能名を記事と照合し、違っていれば直す
- 記事にない具体例を新しく追加しない
- 正確さを保ったまま、専門用語を短く噛み砕き、一文を40字前後に整える
- 主語と「何が変わったか」を明確にし、重複や抽象的な言い回しを削る
- 1〜2文ごとに改行し、自然で読みやすい日本語にする
- 元の切り口と2部構成は保つ。ただし根拠のない部分は構成より正確さを優先して削る
- 「速報」、ハッシュタグ、URL、前置き、校正コメントは不要。完成した本文だけを返す
- 新しい事実を足さず、現在の本文と記事情報の範囲だけで直す

【記事情報】
タイトル: ${article.title}
${contextText}${factInstruction}${termInstruction}

【現在の本文】
      ${body}`}]);
      const reviewedBody=reviewed.text.trim().replace(/【速報】\s*/g,'').replace(/速報[：:]\s*/g,'').replace(/速報\s/g,'');
      if(reviewedBody && reviewedBody.length>=shortMinChars && calcLen(reviewedBody+urlStr)<=POST_CHAR_LIMIT){
        body=reviewedBody;
        tweet=body+urlStr;
      }
    }catch(e){ console.warn('最終校正に失敗。校正前の本文を使用します。',e); }

    // それでもオーバーならGeminiで本文を自動短縮
    if(calcLen(tweet)>POST_CHAR_LIMIT){
      setStatus(true,'文字数オーバー。本文を自動短縮中...');
      try{
        const over=calcLen(tweet);
        const shortened=await callProxy([{role:'user',content:`以下のX投稿本文が長すぎます（現在${over}カウント）。URLは変えずに本文だけを短くしてください。
文字数ルール: 日本語1文字=2カウント、英数字=1カウント、URL=23カウント固定、合計${POST_CHAR_LIMIT}以内。
URL: ${urls.join(', ')||'なし'}
本文のみ回答してください。\n\n${body}`}]);
        const newBody=shortened.text.trim().replace(/【速報】\s*/g,'').replace(/速報[：:]\s*/g,'').replace(/速報\s/g,'');
        tweet = newBody + urlStr;
      }catch(e){ console.warn('自動短縮失敗',e); }
    }
    lastArticle=article;
    lastArticleBody=articleBody;
    el('imgPromptBox').style.display='none';
    el('imgPromptBox').textContent='';
    el('imgPromptCopyBtn').style.display='none';
    el('resultHeader').innerHTML=`
      <span class="badge lang">${activeLang==='en'?'🌐 海外':'🇯🇵 国内'}</span>`;
    el('articleMeta').textContent=`${article.source}　${article.published}　${article.typeLabel||'RSSニュース'}・信頼度${article.trustScore||70}`;
    el('articleTitle').innerHTML=article.url?`<a href="${escapeHtml(article.url)}" target="_blank">${escapeHtml(article.title)}</a>`:escapeHtml(article.title);
    el('angleOutlineBox').innerHTML=`<div class="angle-line">🎯 ${escapeHtml(angle)}</div>${outline.length?`<ul class="outline-list">${outline.map(o=>`<li>${escapeHtml(o)}</li>`).join('')}</ul>`:''}`;
    el('angleOutlineBox').style.display='block';
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
      markPosted(article,el('tweetBox').innerText);
    };
  }catch(e){
    setStatus(false);
    el('selectBtn').disabled=false;
    el('selectBtn').textContent=genBtnLabel;
    showError('生成に失敗: '+e.message);
  }
};

el('shortenBtn').onclick=async()=>{
  const cur=el('tweetBox').innerText;
  const calcLen2=(t)=>{const u=t.match(/https?:\/\/[^\s]+/g)||[];return xWeightedLen(t.replace(/https?:\/\/[^\s]+/g,''))+u.length*23;};
  if(calcLen2(cur)<=POST_CHAR_LIMIT)return;
  el('shortenBtn').disabled=true;setStatus(true,'短縮中...');
  try{
    const data=await callProxy([{role:'user',content:`以下のX投稿文を文字数制限内に短縮してください。ルール: 日本語1文字=2カウント、英数字1文字=1カウント、URL=23カウント固定、合計${POST_CHAR_LIMIT}以内。URLは全て残し自然な日本語で。投稿文のみ回答。\n\n${cur}`}]);
    el('tweetBox').innerText=data.text.trim();updateChar();
  }catch(e){showError('短縮失敗: '+e.message);}
  finally{setStatus(false);el('shortenBtn').disabled=false;}
};

el('backBtn').onclick=()=>{
  el('resultCard').style.display='none';
  el('candidatesSection').style.display='block';
  el('opinionPanel').style.display='block';
  updateStickyBar();
};

el('imgPromptBtn').onclick=async()=>{
  if(!lastArticle)return;
  el('imgPromptBtn').disabled=true;
  el('imgPromptBtn').textContent='生成中...';
  try{
    // 投稿文生成と同じくfetch_article_body側で既に上限（6,000文字）を掛けているため、
    // ここでは追加でスライスしない。以前は先頭2,500文字に切り詰めていたため、
    // 記事後半にある「変化・結論」を見落とし、typicalなBefore/After構成しか
    // 作れないことがあった。
    const source=lastArticleBody || lastArticle.summary || lastArticle.title;
    const data=await callProxy([{role:'user',content:`以下のIT記事を、日本語の解説インフォグラフィック画像にするための構成要素を考えてください。SNSでよく見る「わかりやすい図解」投稿のような、見出し＋複数ステップ＋マスコットキャラクターのイラストを想定します。

記事タイトル: ${lastArticle.title}
内容: ${source}

【最重要: 記事内容を正確に反映する】
- title_ja・sectionsはすべて上記の記事本文（またはRSS概要）に実際に書かれている内容を根拠にする。タイトルからの推測や、記事に書かれていない一般的なAI/IT論で埋めない
- sectionsは記事中の具体的な流れ・変化・比較を反映すること（例: 記事に書かれている「Before→After」「旧方式→新方式」「課題→解決策」など、実際の内容に沿った展開にする。テンプレート的な「今までのAI→新しいAI」のような使い回しにしない）
- label_jaには記事中の固有名詞・製品名・数値などを可能な範囲で使う

出力ルール:
- JSON形式のみで回答する。説明や前置き、Markdownのコードブロックは一切不要
- 形式: {"title_ja": "文字列", "sections": [{"label_ja": "文字列", "visual_en": "文字列"}, ...]}
- title_ja: 画像上部に大きく表示する見出し。記事の要点を興味を引く一言でまとめた日本語（15〜25文字程度。例: "フィジカルAIってなに？「頭脳」から「身体」をもつ進化！"）
- sections: 記事の内容を2〜4個の流れ・比較・要素に分解したもの。それぞれ:
  - label_ja: そのステップ・要素を表す短い日本語ラベル（4〜10文字。例: "今までのAI"）
  - visual_en: そのステップを視覚的に表すイラスト要素の英語説明（アイコンやマスコットロボットの動作など、具体的に）
- 全体として左から右へ読み進められる構成にする（記事の実際の展開に沿ったBefore/After・比較・変化のステップなど）`}], true);
    let parsed;
    try{ parsed = JSON.parse(data.text.trim().replace(/^```(?:json)?\s*|\s*```$/g,'')); }
    catch(e){ throw new Error('プロンプトの解析に失敗しました'); }
    const sections=(parsed.sections||[]);
    const sectionDesc=sections.map((s,i)=>`section ${i+1} showing ${s.visual_en}, with a Japanese text label reading "${s.label_ja}"`).join(', then connected by a simple arrow to ');
    const finalPrompt = `Create a 16:9 horizontal image optimized for an X/Twitter single-image attachment, 1200x675 composition. Keep important elements inside a central safe area with generous margins. Use large simple icons and a clear visual hierarchy. A cute, colorful flat-illustration infographic in a hand-drawn Japanese explainer style, with a cheerful mascot robot character. Large bold Japanese title text overlay at the top reading "${parsed.title_ja}". The image is divided into ${sections.length} horizontal sections read left to right: ${sectionDesc}. Bright color palette, sparkle and star decorations, clean vector-style icons, educational social-media infographic aesthetic, clean sans-serif Japanese typography. No photorealistic humans, celebrities, or brand logos.`;
    el('imgPromptBox').textContent=finalPrompt;
    el('imgPromptBox').style.display='block';
    el('imgPromptCopyBtn').style.display='inline-block';
  }catch(e){
    showError('画像プロンプト生成に失敗: '+e.message);
  }finally{
    el('imgPromptBtn').disabled=false;
    el('imgPromptBtn').textContent='🎨 画像生成プロンプトを作成';
  }
};

el('imgPromptCopyBtn').onclick=async()=>{
  try{
    await navigator.clipboard.writeText(el('imgPromptBox').textContent);
    const orig=el('imgPromptCopyBtn').textContent;
    el('imgPromptCopyBtn').textContent='✅ コピーしました';
    setTimeout(()=>{el('imgPromptCopyBtn').textContent=orig;},1500);
  }catch(e){showError('コピーに失敗しました');}
};

el('copyBtn').onclick=async()=>{
  try{
    await navigator.clipboard.writeText(el('tweetBox').innerText);
    el('copyBtn').textContent='✓ コピー済';
    setTimeout(()=>el('copyBtn').textContent='📋 コピー',1500);
  }catch{showError('コピーに失敗');}
};

el('articleDraftCopyBtn').onclick=async()=>{
  try{
    await navigator.clipboard.writeText(el('articleDraftBox').innerText);
    el('articleDraftCopyBtn').textContent='✓ コピー済';
    setTimeout(()=>el('articleDraftCopyBtn').textContent='📋 記事をコピー',1500);
  }catch(e){showError('コピーに失敗しました');}
};

const POST_HISTORY_KEY='it_post_history_v1';
function todayKeyJST(){
  // サーバー側の「今日」判定と同じくJSTの日付で揃える
  return new Date(Date.now()+9*60*60*1000).toISOString().slice(0,10);
}
function renderHistoryList(){
  el('historySection').style.display=postHistory.length?'block':'none';
  el('historyList').innerHTML=postHistory.map((h,i)=>`
    <div class="history-item" onclick="loadHistory(${i})">
      <span class="hi-title">${h.title}</span>
      <span class="hi-time">${h.time}</span>
    </div>`).join('');
}
function markPosted(art,tweet){
  const now=new Date().toLocaleTimeString('ja-JP',{hour:'2-digit',minute:'2-digit'});
  postHistory.unshift({title:art.title,tweet,time:now});
  if(postHistory.length>9)postHistory.pop();
  renderHistoryList();
  try{
    localStorage.setItem(POST_HISTORY_KEY,JSON.stringify({date:todayKeyJST(),items:postHistory}));
  }catch(e){ console.warn('投稿履歴の保存に失敗',e); }
}
function loadPostHistory(){
  // 「今日の投稿履歴」というラベルの通り、日付（JST）が変わっていたら破棄する
  try{
    const raw=localStorage.getItem(POST_HISTORY_KEY);
    if(!raw)return;
    const data=JSON.parse(raw);
    if(data.date!==todayKeyJST()||!Array.isArray(data.items))return;
    postHistory=data.items;
    renderHistoryList();
  }catch(e){ console.warn('投稿履歴の読み込みに失敗',e); }
}
function loadHistory(i){
  const h=postHistory[i];el('tweetBox').innerText=h.tweet;updateChar();
  el('resultCard').style.display='block';
}

renderCats();renderLangs();loadPostHistory();
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
        return _validate_token(self._get_cookie(COOKIE_NAME))

    def _auth_cookie_header(self):
        return f"{COOKIE_NAME}={_make_token()}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_IDLE_TIMEOUT_SECONDS}"

    def _clear_auth_cookie_header(self):
        return f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    def _refresh_auth_cookie_if_needed(self):
        if BASIC_USER and BASIC_PASS:
            self.send_header("Set-Cookie", self._auth_cookie_header())

    def _redirect_login_expired(self):
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", self._clear_auth_cookie_header())
        self.end_headers()

    def _redirect_login(self, error=False):
        page = LOGIN_HTML.replace("{error}", '<div class="error">ユーザー名またはパスワードが違います</div>' if error else "")
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
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
            self.send_header("Set-Cookie", self._auth_cookie_header())
            self.end_headers()
        else:
            self._redirect_login(error=True)

    def _handle_logout(self):
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", self._clear_auth_cookie_header())
        self.end_headers()

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self._refresh_auth_cookie_if_needed()
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
        # アイコン・マニフェストはOSが認証クッキー無しで取得するため認証前に配信
        if self.path == "/apple-touch-icon.png" or self.path.startswith("/apple-touch-icon"):
            icon = build_app_icon()
            if not icon:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", len(icon))
            self.end_headers()
            self.wfile.write(icon)
            return
        if self.path.split("?", 1)[0] == "/manifest.webmanifest":
            body = WEB_MANIFEST.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self._check_auth():
            return self._redirect_login_expired()
        if self.path.split("?", 1)[0] == "/api/status":
            self.send_json(200, {"has_key": bool(API_KEY)})
        elif self.path.startswith("/api/cancel"):
            from urllib.parse import urlparse, parse_qs
            params = parse_qs(urlparse(self.path).query)
            request_id = params.get("request_id", [""])[0]
            cancelled = cancel_request(request_id)
            self.send_json(200, {"cancelled": cancelled})
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
                category = params.get("category", [""])[0]
                lang = params.get("lang", ["jp"])[0]
                include_x = params.get("include_x", ["0"])[0] == "1"
                days = int(params.get("days", [str(RECENT_DAYS)])[0])
                keyword = params.get("keyword", [""])[0].strip() or None
                request_id = params.get("request_id", [""])[0]
                cancel_event = create_cancel_event(request_id)
                print(f"[候補取得] category={category} lang={lang} include_x={include_x} days={days} keyword={keyword} request_id={request_id}", flush=True)
                _RSS_FAIL_CACHE.clear()
                def _load_articles(target_days, full=False):
                    ensure_not_cancelled(cancel_event)
                    if keyword:
                        full = True  # キーワード検索は全カテゴリ対象で件数が多いため、最初からフル予算で取得
                    if not full:
                        return get_articles(category, lang, limit=20, include_x=include_x, recent_days=target_days, translate=bool(keyword), keyword=keyword, cancel_event=cancel_event)
                    return get_articles(
                        category,
                        lang,
                        limit=20,
                        include_x=include_x,
                        recent_days=target_days,
                        translate=bool(keyword),
                        fetch_timeout=RSS_FULL_FETCH_TIMEOUT,
                        fast_budget=RSS_FULL_FETCH_FAST_BUDGET,
                        max_budget=RSS_FULL_FETCH_MAX_BUDGET * 2 if keyword else RSS_FULL_FETCH_MAX_BUDGET,
                        keyword=keyword,
                        cancel_event=cancel_event,
                    )
                try:
                    articles = _load_articles(days)
                except Exception as first_error:
                    print(f"[候補取得] 初回失敗、再試行します: {first_error}", flush=True)
                    import time as _time
                    _time.sleep(RSS_EMPTY_RETRY_DELAY)
                    ensure_not_cancelled(cancel_event)
                    articles = _load_articles(days)
                used_full_fetch = False
                expanded_days = days
                auto_expand_max_days = 3 if lang == "en" else 7
                # 同一リクエスト内の再取得では失敗キャッシュをクリアしない。
                # 403やコネクション切断など確実に失敗するフィードを毎回律儀に
                # 再試行すると、その分だけ後続の取得予算を浪費してしまうため。
                if len(articles) < 20:
                    print(f"[候補取得] {len(articles)}件のため追加取得します", flush=True)
                    used_full_fetch = True
                    articles = _load_articles(days, full=True)
                # 「今日」は当日の記事だけを返す。件数不足でも過去記事への
                # 自動補完は行わず、同じ当日条件での追加取得だけに留める。
                if not keyword and category and days > 0 and len(articles) < 20 and days < 3:
                    expanded_days = 3
                    print(f"[候補取得] {len(articles)}件のため3日以内で補完します", flush=True)
                    used_full_fetch = True
                    articles = _load_articles(expanded_days, full=True)
                if not keyword and category and days > 0 and len(articles) < 20 and expanded_days < auto_expand_max_days:
                    expanded_days = auto_expand_max_days
                    print(f"[候補取得] {len(articles)}件のため{auto_expand_max_days}日以内で補完します", flush=True)
                    used_full_fetch = True
                    articles = _load_articles(expanded_days, full=True)
                if not articles:
                    print("[候補取得] 初回0件、失敗キャッシュをクリアして再試行します", flush=True)
                    _RSS_FAIL_CACHE.clear()
                    import time as _time
                    _time.sleep(RSS_EMPTY_RETRY_DELAY)
                    ensure_not_cancelled(cancel_event)
                    used_full_fetch = True
                    articles = _load_articles(days, full=True)
                # 防御的に最終レスポンスでも「今日」の条件を適用する。
                # ただしAIカテゴリの3社公式最新は、最新動向を把握できるよう期間外でも残す。
                if days == 0:
                    before_today_filter = len(articles)
                    articles = [
                        a for a in articles
                        if a.get("ageDays") == 0 or a.get("isPriorityOfficialLatest")
                    ]
                    if len(articles) != before_today_filter:
                        print(f"[候補取得] 今日以外の記事を{before_today_filter - len(articles)}件除外", flush=True)
                today_count = sum(
                    1 for a in articles
                    if a.get("type") == "official_x" or a.get("ageDays") == 0
                )
                official_latest_count = sum(
                    1 for a in articles if a.get("isPriorityOfficialLatest")
                )
                print(
                    f"[候補取得] 取得件数={len(articles)} うち今日={today_count} "
                    f"3社公式最新={official_latest_count}",
                    flush=True,
                )
                self.send_json(200, {
                    "articles": articles,
                    "count": len(articles),
                    "today_count": today_count,
                    "official_latest_count": official_latest_count,
                    "category": category,
                    "lang": lang,
                    "days": days,
                    "expanded_days": expanded_days,
                    "include_x": include_x,
                    "used_full_fetch": used_full_fetch,
                    "keyword": keyword,
                })
                clear_cancel_event(request_id)
            except FetchCancelled as e:
                print(f"[候補取得] キャンセル: {e}", flush=True)
                clear_cancel_event(locals().get("request_id", ""))
                self.send_json(499, {"error": "取得をキャンセルしました", "cancelled": True})
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[ERROR /api/rss] {e}", flush=True)
                clear_cancel_event(locals().get("request_id", ""))
                self.send_json(500, {"error": f"記事取得中にエラーが発生しました: {str(e)}"})
        else:
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self._refresh_auth_cookie_if_needed()
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        if self.path == "/login":
            return self._handle_login_post()
        if not self._check_auth():
            return self._redirect_login_expired()
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
            needing_translation_before = sum(1 for a in articles if needs_translation(a))
            try:
                if needing_translation_before > 0 and not API_KEY:
                    self.send_json(200, {
                        "articles": articles,
                        "warning": "GEMINI_API_KEY が設定されていないため翻訳できません",
                    })
                    return
                translated = translate_titles(articles)
                still_untranslated = sum(1 for a in translated if needs_translation(a))
                if needing_translation_before > 0 and still_untranslated >= needing_translation_before:
                    # バッチ翻訳がすべて失敗した場合、call_gemini側は例外を握りつぶすため
                    # ここまで来ても気づかれない。明示的に警告を返す。
                    self.send_json(200, {
                        "articles": translated,
                        "warning": "翻訳に失敗しました（サーバーログの[翻訳]バッチ失敗を確認してください）",
                    })
                else:
                    self.send_json(200, {"articles": translated})
            except Exception as e:
                print(f"[ERROR /api/translate_candidates] {e}", flush=True)
                self.send_json(200, {"articles": articles, "warning": str(e)})
            return

        messages = payload.get("messages", [])

        if not API_KEY:
            self.send_json(500, {"error": "GEMINI_API_KEY が設定されていません"})
            return

        prompt_text = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        json_mode = bool(payload.get("json_mode"))
        try:
            text = call_gemini(prompt_text, max_tokens=2000, json_mode=json_mode)
            self.send_json(200, {"text": text})
        except Exception as e:
            print(f"[ERROR] {e}", flush=True)
            self.send_json(500, {"error": str(e)})


DEFAULT_WARMUP_CATEGORY = "AI・機械学習"

def warm_up_default_category():
    """起動直後（Renderのスリープ復帰時など）の最初の検索が、フィードが
    軒並み未キャッシュのために遅く・不安定（早期終了で母集団が小さくなる）に
    ならないよう、デフォルトカテゴリのRSSキャッシュを事前に温めておく。
    article_typeはget_articles()が実際に使う値と揃える必要がある
    （_RSS_CACHEはfeed_url単位のキーでarticle_typeを区別しないため、
    ここで誤った型を渡すとキャッシュ経由で本番の取得結果まで誤分類される）。
    """
    try:
        from concurrent.futures import ThreadPoolExecutor
        tasks = (
            [(f, None) for f in RSS_FEEDS.get(DEFAULT_WARMUP_CATEGORY, [])]
            + [(f, "github_release") for f in GITHUB_RELEASE_FEEDS.get(DEFAULT_WARMUP_CATEGORY, [])]
            + [(f, "docs_update") for f in DOCS_UPDATE_FEEDS.get(DEFAULT_WARMUP_CATEGORY, [])]
        )
        with ThreadPoolExecutor(max_workers=max(10, len(tasks))) as executor:
            list(executor.map(
                lambda t: fetch_configured_source(
                    t[0], limit=RSS_PER_FEED_LIMIT, article_type=t[1], timeout=RSS_FETCH_TIMEOUT
                ),
                tasks,
            ))
        print(f"[起動時ウォームアップ] {DEFAULT_WARMUP_CATEGORY}のフィード{len(tasks)}件を事前取得しました", flush=True)
    except Exception as e:
        print(f"[起動時ウォームアップ] 失敗: {e}", flush=True)

def main():
    if not API_KEY:
        print("⚠️  GEMINI_API_KEY が設定されていません")
        print("   export GEMINI_API_KEY=... を実行してから再起動してください\n")

    if BASIC_USER and BASIC_PASS and not os.environ.get("COOKIE_SECRET"):
        print("⚠️  COOKIE_SECRET が未設定のため、ログインパスワード(BASIC_PASS)を")
        print("   Cookie署名鍵として代用しています。ログイン用パスワードとは")
        print("   別の値を COOKIE_SECRET に設定することを推奨します。\n")

    threading.Thread(target=warm_up_default_category, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"✅ サーバー起動: {url}")
    print(f"   モデル: {GEMINI_MODEL}（複数ソース版・精度重視）")
    print("   Ctrl+C で終了\n")

    if os.environ.get("PORT") is None:  # ローカルのみブラウザ自動起動
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了しました")


if __name__ == "__main__":
    main()
