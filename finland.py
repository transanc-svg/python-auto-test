import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os
from oauth2client.service_account import ServiceAccountCredentials

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

# GitHub Secrets から JSON を読み込む
google_creds = os.environ["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(google_creds)

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)


# --- スプレッドシート名 ---
spreadsheet_name = "finland"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存のURLを取得して重複防止 ---
existing_urls = sheet.col_values(2)  # B列のURL
if existing_urls:
    existing_urls = existing_urls[1:]  # ヘッダーを除外
else:
    existing_urls = []

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/search?hl=ja&gl=JP&ceid=JP%3Aja&oc=11&q=%E3%83%95%E3%82%A3%E3%83%B3%E3%83%A9%E3%83%B3%E3%83%89"
feed = feedparser.parse(rss_url)

# --- 最新10件を逆順にする（古い順から処理） ---
entries_to_process = feed.entries[:20][::-1]

# --- Selenium セットアップ（ヘッドレス） ---
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- ヘッダーがなければ追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "C列", "D列", "画像URL(E列)"])

# --- Instagram 投稿可能な拡張子 ---
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")

# --- 最新10件を処理 ---
for entry in entries_to_process:
    title = entry.title
    google_url = entry.link

    # SeleniumでオリジナルURLと画像を取得
    try:
        driver.get(google_url)
        time.sleep(2)
        original_url = driver.current_url

        # ページ内の最初の画像を取得
        try:
            img_element = driver.find_element("xpath", "//img")
            image_url = img_element.get_attribute("src")
            # Instagram 投稿可能な拡張子のみ許可
            if not image_url or not image_url.lower().endswith(VALID_EXTENSIONS):
                image_url = None  # 画像なし or 非対応形式 → スキップ
        except:
            image_url = None
    except Exception as e:
        print(f"Error fetching URL for {title}: {e}")
        original_url = google_url
        image_url = None

    # 画像があるかつ既存URLにない場合のみ書き込み
    if image_url and original_url not in existing_urls:
        sheet.append_row([title, original_url, "", "", image_url])
        existing_urls.append(original_url)
        print(f"追加: {title} → {original_url} / {image_url}")
    else:
        print(f"スキップ: {title}（画像なし/Instagram非対応/既存）")

driver.quit()
print("最新10件のInstagram対応画像付きニュースをスプレッドシート 'finland' に追加しました。")


