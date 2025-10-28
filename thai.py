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

sheet = client.open("タイ").sheet1

# --- 既存URL取得（重複防止） ---
existing_urls = sheet.col_values(2)
existing_urls = existing_urls[1:] if existing_urls else []

# --- RSS取得 ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)
entries = feed.entries[:20][::-1]

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "リンク"])

# --- RSS処理 ---
for entry in entries:
    title = entry.title
    url = entry.link

    if url in existing_urls:
        continue

    sheet.append_row([title, url])
    existing_urls.append(url)
    print(f"追加: {title} → {url}")

print("RSSのタイトルとリンクを書き出し完了。")
