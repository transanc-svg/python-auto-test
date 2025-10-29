import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import requests

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
google_creds = os.environ["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

spreadsheet_name = "タイ"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存URLを取得して重複防止 ---
existing_urls = sheet.col_values(2)
existing_urls = existing_urls[1:] if existing_urls else []

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)
entries_to_process = feed.entries[::-1]  # 古い順に処理

print(f"📌 RSS取得件数: {len(entries_to_process)}")

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "ハッシュタグ", "説明", "画像URL"])

# --- TextRazor APIキー ---
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"
FALLBACK_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg"

def generate_hashtags(text):
    """TextRazor APIでハッシュタグ生成"""
    url = "https://api.textrazor.com/"
    payload = {"text": text, "extractors": "entities,topics,words"}
    headers = {"X-TextRazor-Key": TEXTRAZOR_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
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
        return " ".join(f"#{t}" for t in tags[:5]) if tags else "#タイ #ニュース"
    except Exception as e:
        print(f"TextRazor API error: {e}")
        return "#タイ #ニュース"

# --- RSS処理 ---
for i, entry in enumerate(entries_to_process, 1):
    title = entry.title
    url = entry.link
    description = getattr(entry, "summary", "")

    # --- 画像取得（RSS内の media:content や media:thumbnail があれば使用） ---
    image_url = None
    if 'media_content' in entry:
        media = entry.media_content
        if media and isinstance(media, list):
            image_url = media[0].get('url')
    if not image_url and 'media_thumbnail' in entry:
        media = entry.media_thumbnail
        if media and isinstance(media, list):
            image_url = media[0].get('url')
    if not image_url:
        image_url = FALLBACK_IMAGE_URL

    # --- デバッグ出力 ---
    print(f"\n[{i}] タイトル: {title}")
    print(f"    URL: {url}")
    print(f"    description: {description[:50]}...")
    print(f"    画像URL: {image_url}")
    print(f"    既存URL判定: {url in existing_urls}")

    # --- 重複チェック ---
    if url in existing_urls:
        print(f"⏭ スキップ（既存URL）")
        continue

    hashtags = generate_hashtags(title)
    print(f"    hashtags: {hashtags}")

    # --- スプレッドシート書き込み ---
    try:
        sheet.append_row([title, url, hashtags, description, image_url])
        existing_urls.append(url)
        print(f"✅ 追加成功")
    except Exception as e:
        print(f"❌ 書き込み失敗 → {e}")

print("\n🎉 デバッグ完了: RSS記事のスプレッドシート追加終了")
