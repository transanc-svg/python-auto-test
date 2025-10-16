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
import requests

# --- TextRazor APIキー ---
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

google_creds = os.environ["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# --- スプレッドシート名 ---
spreadsheet_name = "タイ"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存URLを取得して重複防止 ---
existing_urls = sheet.col_values(2)  # B列
if existing_urls:
    existing_urls = existing_urls[1:]  # ヘッダーを除く
else:
    existing_urls = []

# --- RSSフィード（Googleニュース: タイ） ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)
entries_to_process = feed.entries[:10][::-1]  # 最新10件を古い順で処理

# --- Selenium セットアップ ---
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- ヘッダーがなければ追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "ハッシュタグ(C列)", "説明(D列)", "画像URL(E列)"])

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")
EXCLUDE_DOMAINS = ["jp.fashionnetwork.com", "newscast.jp", "www.keidanren.or.jp", "ashu-aseanstatistics.com"]

# --- TextRazorでハッシュタグを生成 ---
def generate_hashtags(text):
    try:
        url = "https://api.textrazor.com/"
        payload = {"text": text, "extractors": "entities,topics,words"}
        headers = {
            "X-TextRazor-Key": TEXTRAZOR_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code != 200:
            return "#タイ #ニュース"

        data = response.json()
        entities = data.get("response", {}).get("entities", [])
        tags = []

        for e in sorted(entities, key=lambda x: x.get("confidenceScore", 0), reverse=True):
            tag = e.get("entityId") or e.get("matchedText")
            if tag:
                tag = tag.replace(" ", "").replace("#", "")
                if tag not in tags:
                    tags.append(tag)
            if len(tags) >= 5:
                break

        tags = [t for t in tags if not any(c.isdigit() for c in t) and not t.isascii()]

        if not tags:
            return "#タイ #ニュース"

        return " ".join(["#" + t for t in tags[:5]])
    except Exception as e:
        print("TextRazorエラー:", e)
        return "#タイ #ニュース"

# --- RSSの記事を処理 ---
for entry in entries_to_process:
    title = entry.title
    google_url = entry.link

    if any(domain in google_url for domain in EXCLUDE_DOMAINS):
        print(f"除外スキップ: {title} → {google_url}")
        continue

    try:
        driver.get(google_url)
        time.sleep(2)
        original_url = driver.current_url

        if any(domain in original_url for domain in EXCLUDE_DOMAINS):
            print(f"除外スキップ: {title} → {original_url}")
            continue

        # og:image
        image_url = None
        try:
            og_image_element = driver.find_element("xpath", "//meta[@property='og:image']")
            image_url = og_image_element.get_attribute("content")
            if not (image_url and image_url.lower().endswith(VALID_EXTENSIONS) and image_url.startswith("https://")):
                image_url = None
        except:
            image_url = None

        # meta description
        try:
            desc_element = driver.find_element("xpath", "//meta[@name='description']")
            description = desc_element.get_attribute("content")
        except:
            description = ""

    except Exception as e:
        print(f"Error fetching URL for {title}: {e}")
        original_url = google_url
        image_url = None
        description = ""

    if image_url and original_url not in existing_urls:
        hashtags = generate_hashtags(title)
        sheet.append_row([title, original_url, hashtags, description, image_url])
        existing_urls.append(original_url)
        print(f"追加: {title} → {hashtags}")
        time.sleep(1.2)
    else:
        print(f"スキップ: {title}（og:imageなし/既存URL）")

# --- 最大30件を超えた場合、古い順に削除 ---
MAX_ROWS = 30
total_rows = len(sheet.get_all_values())
if total_rows > MAX_ROWS:
    rows_to_delete = total_rows - MAX_ROWS
    for _ in range(rows_to_delete):
        sheet.delete_rows(2)  # ヘッダー行の次(2行目)から削除
    print(f"{rows_to_delete}件の古いデータを削除しました。")

driver.quit()
print("完了: 最新10件を追加、最大30件を維持しました。")
