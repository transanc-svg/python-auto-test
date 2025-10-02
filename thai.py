import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
import json
import os
import time

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

google_creds = os.environ["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

spreadsheet_name = "thai"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存URL ---
existing_urls = sheet.col_values(2)[1:] if sheet.col_values(2) else []

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)

entries_to_process = feed.entries[:10][::-1]

# --- ヘッダーがなければ追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "C列", "D列", "画像URL(E列)"])

# --- Instagram対応拡張子 ---
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")

def get_og_image(url):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            img_url = meta["content"]
            # Instagram対応拡張子のみ
            if img_url.lower().endswith(VALID_EXTENSIONS):
                return img_url
        return None
    except Exception as e:
        print(f"OG画像取得失敗: {url} - {e}")
        return None

# --- 最新10件処理 ---
for entry in entries_to_process:
    title = entry.title
    original_url = entry.link

    if original_url in existing_urls:
        print(f"スキップ（既存）: {title}")
        continue

    image_url = get_og_image(original_url)

    if image_url:
        sheet.append_row([title, original_url, "", "", image_url])
        existing_urls.append(original_url)
        print(f"追加: {title} → {original_url} / {image_url}")
    else:
        print(f"スキップ（画像なし/非対応形式）: {title}")

print("最新10件のInstagram対応画像付きニュースを追加しました。")
