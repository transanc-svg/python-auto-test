import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

# 環境変数からJSON読み込み
google_creds = os.environ.get("GOOGLE_CREDENTIALS")
if not google_creds:
    raise Exception("環境変数 GOOGLE_CREDENTIALS が設定されていません")

creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# --- シートを開く ---
spreadsheet_name = "タイ"
sheet = client.open(spreadsheet_name).sheet1

# --- テスト用RSS ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"

# RSS取得（User-Agent 指定）
feed = feedparser.parse(rss_url, request_headers={'User-Agent': 'Mozilla/5.0'})

print(f"取得記事件数: {len(feed.entries)}")
if len(feed.entries) == 0:
    print("RSSが取得できません。URLや接続を確認してください。")
else:
    # 最初の3件を表示
    for entry in feed.entries[:3]:
        print("タイトル:", entry.title)
        print("リンク:", entry.link)

# --- スプレッドシートにテスト書き込み ---
try:
    sheet.append_row(["テストタイトル", "https://example.com"])
    print("スプレッドシート書き込み成功")
except Exception as e:
    print("スプレッドシート書き込み失敗:", e)
