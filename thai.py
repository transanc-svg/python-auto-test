import json
import os
import feedparser
import gspread
from google.oauth2.service_account import Credentials

# RSSフィードURL（Googleニュース）
RSS_URL = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP:ja"

# スプレッドシート情報
SPREADSHEET_ID = "1m9mYYpfonBFSILYUTLqUsF4bJEj6Srs4N3lMxPG1ZhA"
SHEET_NAME = "シート1"

# GitHub Secrets からサービスアカウントの認証情報を取得
google_credentials = json.loads(os.environ["GOOGLE_CREDENTIALS"])

# スコープの設定
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 認証
creds = Credentials.from_service_account_info(google_credentials, scopes=SCOPES)
gc = gspread.authorize(creds)

# シート取得
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.worksheet(SHEET_NAME)

# シート初期化とヘッダー追加
worksheet.clear()
worksheet.append_row(["title", "link", "description"])

# RSSフィードを解析
feed = feedparser.parse(RSS_URL)

# 全記事を書き出す
for entry in feed.entries:
    title = entry.title
    link = entry.link
    description = entry.get("description", "")
    worksheet.append_row([title, link, description])

print("✅ 完了：RSSのすべての記事を書き出しました！")
