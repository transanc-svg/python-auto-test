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

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
google_creds = os.environ["GOOGLE_CREDENTIALS"]
creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

spreadsheet_name = "タイ"
sheet = client.open(spreadsheet_name).sheet1

# --- 既存のURLを取得して重複防止 ---
existing_urls = sheet.col_values(2)  # B列
existing_urls = existing_urls[1:] if existing_urls else []

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)
entries_to_process = feed.entries[:50][::-1]  # 最新50件を古い順に

# --- Selenium セットアップ ---
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "ハッシュタグ", "説明", "画像URL"])

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
EXCLUDE_DOMAINS = ["jp.fashionnetwork.com", "newscast.jp", "www.keidanren.or.jp", "ashu-aseanstatistics.com"]

# --- TextRazor APIキー ---
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"

# --- 代替画像URL（画像がない場合に使う） ---
FALLBACK_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg"

def generate_hashtags(text):
    """TextRazor APIでハッシュタグ生成"""
    url = "https://api.textrazor.com/"
    payload = {
        "text": text,
        "extractors": "entities,topics,words"
    }
    headers = {
        "X-TextRazor-Key": TEXTRAZOR_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = "&".join([f"{k}={requests.utils.quote(v)}" for k,v in payload.items()])
    try:
        res = requests.post(url, headers=headers, data=data, timeout=10)
        if res.status_code != 200:
            return "#タイ #ニュース"
        data_json = res.json()
        entities = data_json.get("response", {}).get("entities", [])
        tags = []
        for e in sorted(entities, key=lambda x: x.get("confidenceScore",0), reverse=True):
            tag = e.get("entityId") or e.get("matchedText")
            if tag:
                tag = tag.replace(" ", "")
                if tag not in tags:
                    tags.append(tag)
        if len(tags) < 5:
            for w in data_json.get("response", {}).get("words", []):
                tag = w.get("token")
                if tag:
                    tag = tag.replace(" ", "")
                    if tag not in tags:
                        tags.append(tag)
                if len(tags) >= 5:
                    break
        tags = [t for t in tags if not any(c.isdigit() for c in t)]
        if not tags:
            return "#タイ #ニュース"
        return " ".join(f"#{t}" for t in tags[:5])
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

    try:
        driver.get(google_url)
        time.sleep(3)
        original_url = driver.current_url

        if any(domain in original_url for domain in EXCLUDE_DOMAINS):
            print(f"除外スキップ: {title} → {original_url}")
            continue

        image_url = None
        description = None

        try:
            og_image_element = driver.find_element("xpath", "//meta[@property='og:image']")
            image_url = og_image_element.get_attribute("content")
            if not image_url or not image_url.startswith("https://"):
                image_url = None
        except:
            image_url = None

        try:
            desc_element = driver.find_element("xpath", "//meta[@name='description']")
            description = desc_element.get_attribute("content")
        except:
            description = None

    except Exception as e:
        print(f"Error fetching URL for {title}: {e}")
        original_url = google_url
        image_url = None
        description = None

    # --- 画像がない場合は代替画像を使用 ---
    if not image_url:
        image_url = FALLBACK_IMAGE_URL

    # --- 書き込み（すべての記事を対象） ---
    if original_url not in existing_urls:
        description = description or ""
        hashtags = generate_hashtags(title)
        try:
            sheet.append_row([title, original_url, hashtags, description, image_url])
            existing_urls.append(original_url)
            print(f"✅ 追加: {title} → {original_url}")
        except Exception as e:
            print(f"❌ 書き込み失敗: {title} → {e}")
    else:
        print(f"⏭ スキップ: {title}（既存URL）")

driver.quit()
print("🎉 すべてのニュースをスプレッドシートに追加しました（画像なしは代替画像を使用）。")
