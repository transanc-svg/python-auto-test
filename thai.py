import requests
import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

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

# --- RSS取得 ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
}

try:
    res = requests.get(rss_url, headers=headers, timeout=10)
    res.raise_for_status()
    feed = feedparser.parse(res.text)
except Exception as e:
    print(f"RSS取得失敗: {e}")
    feed = feedparser.parse("")

entries_to_process = feed.entries[::-1]  # 古い順に処理
print(f"📌 RSS取得件数: {len(entries_to_process)}")

if not existing_urls:
    sheet.append_row(["タイトル", "URL", "ハッシュタグ", "description", "画像URL"])

# --- TextRazor API ---
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"
FALLBACK_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg"

def generate_hashtags(text):
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

# --- 記事処理 ---
for i, entry in enumerate(entries_to_process, 1):
    title = entry.title
    url = entry.link
    description = getattr(entry, "summary", "")

    # 画像URL取得（RSSに含まれる media:content または media:thumbnail があれば使用）
    image_url = FALLBACK_IMAGE_URL
    if 'media_content' in entry:
        media = entry.media_content
        if media and isinstance(media, list):
            image_url = media[0].get('url') or FALLBACK_IMAGE_URL
    elif 'media_thumbnail' in entry:
        media = entry.media_thumbnail
        if media and isinstance(media, list):
            image_url = media[0].get('url') or FALLBACK_IMAGE_URL

    if url in existing_urls:
        print(f"⏭ スキップ（既存URL）: {title}")
        continue

    hashtags = generate_hashtags(title)

    try:
        sheet.append_row([title, url, hashtags, description, image_url])
        existing_urls.append(url)
        print(f"✅ 追加成功: {title}")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {e}")

print("🎉 GoogleニュースRSSの記事をスプレッドシートに追加完了")
