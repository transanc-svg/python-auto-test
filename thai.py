import json
import os
import feedparser
import gspread
from google.oauth2.service_account import Credentials

# GoogleニュースRSSのURL
RSS_URL = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP:ja"

# スプレッドシート情報
SPREADSHEET_ID = "あなたのスプレッドシートID"  # URLの /d/ 〜 /edit の部分だけ
SHEET_NAME = "シート1"

# GitHub Secrets から認証情報を取得
google_credentials = json.loads(os.environ["GOOGLE_CREDENTIALS"])

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(google_credentials, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.worksheet(SHEET_NAME)

# RSSを読み込み
feed = feedparser.parse(RSS_URL)

# シートをクリアしてヘッダー追加
worksheet.clear()
worksheet.append_row(["title", "url", "description"])

# ニュースを書き込み
for entry in feed.entries:
    title = entry.title
    link = entry.link
    desc = entry.get("description", "")
    worksheet.append_row([title, link, desc])

print("✅ 完了：スプレッドシートにニュースを書き出しました！")
