import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os
import requests

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

print("🔑 Google認証開始...")
google_creds = os.environ["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
print("✅ Google認証成功")

spreadsheet_name = "タイ"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存のURLを取得して重複防止 ---
existing_urls = sheet.col_values(2)  # B列
existing_urls = existing_urls[1:] if existing_urls else []

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "ハッシュタグ", "説明", "画像URL"])

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)
entries_to_process = feed.entries[:30][::-1]  # 古い順に最大30件

# --- Selenium セットアップ ---
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
print("✅ Chrome起動成功")

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
EXCLUDE_DOMAINS = [
    "jp.fashionnetwork.com", "newscast.jp",
    "www.keidanren.or.jp", "ashu-aseanstatistics.com"
]

# --- TextRazor APIキー ---
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"

def generate_hashtags(text):
    """TextRazor APIでハッシュタグ生成"""
    url = "https://api.textrazor.com/"
    payload = {"text": text, "extractors": "entities,topics,words"}
    headers = {"X-TextRazor-Key": TEXTRAZOR_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
    data = "&".join([f"{k}={requests.utils.quote(v)}" for k, v in payload.items()])
    try:
        res = requests.post(url, headers=headers, data=data, timeout=10)
        if res.status_code != 200:
            return "#タイ #ニュース"
        data_json = res.json()
        entities = data_json.get("response", {}).get("entities", [])
        tags = []
        for e in sorted(entities, key=lambda x: x.get("confidenceScore", 0), reverse=True):
            tag = e.get("entityId") or e.get("matchedText")
            if tag:
                tag = tag.replace(" ", "")
                if tag not in tags:
                    tags.append(tag)
        if len(tags) < 5:
            for w in data_json.get("response", {}).get("words", []):
                tag = w.get("token")
                if tag and tag not in tags:
                    tags.append(tag)
                if len(tags) >= 5:
                    break
        tags = [t for t in tags if not any(c.isdigit() for c in t)]
        return " ".join(f"#{t}" for t in tags[:5]) if tags else "#タイ #ニュース"
    except Exception as e:
        print(f"TextRazor API error: {e}")
        return "#タイ #ニュース"

# --- RSS処理 ---
for entry in entries_to_process:
    title = entry.title
    google_url = entry.link

    if any(domain in google_url for domain in EXCLUDE_DOMAINS):
        print(f"除外スキップ: {title} → {google_url}")
        continue

    print(f"▶ {title}")
    print(f"  URL: {google_url}")

    try:
        driver.get(google_url)
        # ページが完全に読み込まれるまで待機
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(3)
        original_url = driver.current_url

        if any(domain in original_url for domain in EXCLUDE_DOMAINS):
            print(f"⏭ 除外スキップ: {original_url}")
            continue

        # og:image 取得
        image_url = None
        try:
            og_image_element = driver.find_element(By.XPATH, "//meta[@property='og:image']")
            image_url = og_image_element.get_attribute("content")
            if (not image_url or not image_url.startswith("http")):
                image_url = None
        except:
            image_url = None

        # description 取得
        description = ""
        try:
            desc_element = driver.find_element(By.XPATH, "//meta[@name='description']")
            description = desc_element.get_attribute("content") or ""
        except:
            description = ""

        print(f"  画像URL: {image_url}")
        print(f"  説明: {description[:60]}...")
        print(f"  リダイレクト後URL: {original_url}")

    except Exception as e:
        print(f"⚠️ URL処理エラー: {title} → {e}")
        original_url = google_url
        image_url = None
        description = ""

    # --- 書き込み判定 ---
    if image_url and original_url not in existing_urls:
        hashtags = generate_hashtags(title)
        sheet.append_row([title, original_url, hashtags, description, image_url])
        existing_urls.append(original_url)
        print(f"✅ 追加: {title}")
    else:
        print(f"⏭ スキップ: {title}（画像なし or 既存URL）")

driver.quit()
print("🎉 完了: 最新ニュースをスプレッドシートに追加しました。")
