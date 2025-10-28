import feedparser
import gspread
from google.oauth2.service_account import Credentials

# === Google Sheets設定 ===
SPREADSHEET_ID = "1m9mYYpfonBFSILYUTLqUsF4bJEj6Srs4N3lMxPG1ZhA"
SHEET_NAME = "シート1"

# === RSS URL ===
RSS_URL = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja"

# === 認証設定 ===
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(creds)

# === シート取得 ===
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.worksheet(SHEET_NAME)

# === RSSを取得 ===
feed = feedparser.parse(RSS_URL)

# === シートをクリアして見出し追加 ===
worksheet.clear()
worksheet.append_row(["タイトル", "URL", "説明文"])

# === 各ニュースを追加 ===
for entry in feed.entries:
    title = entry.title
    link = entry.link
    description = getattr(entry, "summary", "")
    worksheet.append_row([title, link, description])

print("✅ 完了：スプレッドシートに書き込みました！")
