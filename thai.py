import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
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

spreadsheet_name = "タイ"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存URL取得（重複防止） ---
existing_urls = sheet.col_values(2)
existing_urls = existing_urls[1:] if existing_urls else []

# --- RSS取得 ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)
entries = feed.entries[:20][::-1]  # 最新20件を古い順

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "オリジナルURL"])

# --- Seleniumセットアップ（ヘッドレス） ---
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- RSS処理 ---
for entry in entries:
    title = entry.title
    google_url = entry.link

    # 既存URLはスキップ
    if google_url in existing_urls:
        print(f"既存スキップ: {title}")
        continue

    try:
        driver.get(google_url)
        time.sleep(2)  # リダイレクト待ち
        original_url = driver.current_url
        sheet.append_row([title, original_url])
        existing_urls.append(google_url)
        print(f"追加: {title} → {original_url}")
    except Exception as e:
        print(f"Error fetching URL for {title}: {e}")

driver.quit()
print("RSSからオリジナルURLの書き出し完了。")
