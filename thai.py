import json
import os
import feedparser
import gspread
from google.oauth2.service_account import Credentials

# Google News RSS の URL
RSS_URL = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP:ja"

# スプレッドシートの設定
SPREADSHEET_ID = "1m9mYYpfonBFSILYUTLqUsF4bJEj6Srs4N3lMxPG1ZhA"  # スプレッドシートの ID を入力
SHEET_NAME = "Sheet1"  # シート名を入力

# Google Cloud のサービスアカウント認証情報を環境変数から取得
google_credentials = json.loads(os.environ["GOOGLE_CREDENTIALS"])

# 必要なスコープの設定
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 認証情報を使用して Google Sheets API にアクセス
creds = Credentials.from_service_account_info(google_credentials, scopes=SCOPES)
gc = gspread.authorize(creds)

# スプレッドシートとワークシートの取得
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.worksheet(SHEET_NAME)

# RSS フィードの解析
feed = feedparser.parse(RSS_URL)

# シートの初期化とヘッダーの追加
worksheet.clear()
worksheet.append_row(["Title", "URL", "Description"])

# 各記事をシートに書き込む
for entry in feed.entries:
    title = entry.title
    link = entry.link
    description = entry.get("description", "")
    worksheet.append_row([title, link, description])

print("✅ 完了：スプレッドシートにニュースを書き出しました！")
