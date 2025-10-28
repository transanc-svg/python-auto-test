import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import requests
import time

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
google_creds = os.environ["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

spreadsheet_name = "タイ"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存のURLを取得して重複防止 ---
existing_urls = sheet.col_values(2)  # B列
existing_urls = existing_urls[1:] if existing_urls else []

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
feed = feedparser.parse(rss_url, request_headers=headers)
entries_to_process = feed.entries[:20][::-1]  # 最新20件を古い順に

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "C列(ハッシュタグ)", "D列(description)", "画像URL(E列)"])

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")
EXCLUDE_DOMAINS = [
    "jp.fashionnetwork.com",
    "newscast.jp",
    "www.keidanren.or.jp",
    "ashu-aseanstatistics.com"
]

TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"

def generate_hashtags(text):
    """TextRazor APIでハッシュタグ生成"""
    url = "https://api.textrazor.com/"
    payload = {
        "text": text,
        "extractors": "entities,topics,words"
    }
    headers = {
        "X-TextRazor-Key": TEXTRAZOR_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = "&".join([f"{k}={requests.utils.quote(v)}" for k,v in payload.items()])
    try:
        res = requests.post(url, headers=headers, data=data, timeout=10)
        if res.status_code != 200:
            return "#タイ #ニュース"
        data_json = res.json()
        entities = data_json.get("response", {}).get("entities", [])
        tags = []
        for e in sorted(entities, key=lambda x: x.get("confidenceScore",0), reverse=True):
            tag = e.get("entityId") or e.get("matchedText")
            if tag:
                tag = tag.replace(" ", "")
                if tag not in tags:
                    tags.append(tag)
        if len(tags) < 5:
            for w in data_json.get("response", {}).get("words", []):
                tag = w.get("token")
                if tag:
                    tag = tag.replace(" ", "")
                    if tag not in tags:
                        tags.append(tag)
                if len(tags) >= 5:
                    break
        tags = [t for t in tags if not any(c.isdigit() for c in t)]
        if not tags:
            return "#タイ #ニュース"
        return " ".join(f"#{t}" for t in tags[:5])
    except Exception as e:
        print(f"TextRazor API error: {e}")
        return "#タイ #ニュース"

# --- RSS処理 ---
for entry in entries_to_process:
    title = entry.title
    url = entry.link

    if any(domain in url for domain in EXCLUDE_DOMAINS):
        print(f"除外スキップ: {title} → {url}")
        continue
    if url in existing_urls:
        print(f"既存スキップ: {title} → {url}")
        continue

    description = entry.get("description", "")

    # media:thumbnail または media:content から画像取得
    image_url = None
    if hasattr(entry, "media_thumbnail"):
        image_url = entry.media_thumbnail[0].get("url")
    elif hasattr(entry, "media_content"):
        image_url = entry.media_content[0].get("url")

    # Instagram対応拡張子チェック
    if image_url and not image_url.lower().endswith(VALID_EXTENSIONS):
        image_url = None

    # 画像が無ければ書き込まない
    if not image_url:
        print(f"スキップ（画像なし）: {title}")
        continue

    hashtags = generate_hashtags(title)
    sheet.append_row([title, url, hashtags, description, image_url])
    existing_urls.append(url)
    print(f"追加: {title} → {url} / {image_url} / {hashtags}")

    time.sleep(1.2)  # TextRazor APIレート制限対策

print("RSSからタイトル・description・画像・ハッシュタグをスプレッドシートに書き込み完了。")
