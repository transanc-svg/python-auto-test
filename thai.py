import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

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
existing_urls = sheet.col_values(2)
existing_urls = existing_urls[1:] if existing_urls else []

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
feed = feedparser.parse(rss_url, request_headers=headers)

entries_to_process = feed.entries[:20][::-1]  # 最新20件を古い順に

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "画像URL(E列)"])

EXCLUDE_DOMAINS = [
    "jp.fashionnetwork.com",
    "newscast.jp",
    "www.keidanren.or.jp",
    "ashu-aseanstatistics.com"
]

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")

# --- RSS処理 ---
for entry in entries_to_process:
    title = entry.title
    url = entry.link

    # 除外ドメイン
    if any(domain in url for domain in EXCLUDE_DOMAINS):
        print(f"除外スキップ: {title} → {url}")
        continue

    # 重複チェック
    if url in existing_urls:
        print(f"既存スキップ: {title} → {url}")
        continue

    # 画像URL取得
    image_url = None
    if hasattr(entry, "media_thumbnail"):
        image_url = entry.media_thumbnail[0].get("url")
    elif hasattr(entry, "media_content"):
        image_url = entry.media_content[0].get("url")

    # Instagram対応拡張子チェック
    if not image_url or not image_url.lower().endswith(VALID_EXTENSIONS):
        print(f"スキップ（画像なし）: {title}")
        continue

    # スプレッドシートに書き込み
    sheet.append_row([title, url, image_url])
    existing_urls.append(url)
    print(f"追加: {title} → {url} / {image_url}")

print("RSSから画像URL付き記事をスプレッドシートに書き込み完了。")
