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
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

print("🔑 Google認証開始...")

try:
    google_creds = os.environ["GOOGLE_CREDENTIALS"]
    creds_dict = json.loads(google_creds)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    print("✅ Google認証成功")
except Exception as e:
    print("❌ Google認証失敗:", e)
    exit(1)

# --- スプレッドシート設定 ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1m9mYYpfonBFSILYUTLqUsF4bJEj6Srs4N3lMxPG1ZhA/edit"
try:
    sheet = client.open_by_url(SPREADSHEET_URL).sheet1
    print("✅ スプレッドシート接続成功")
except Exception as e:
    print("❌ スプレッドシート接続失敗:", e)
    exit(1)

# --- 既存のURLを取得して重複防止 ---
existing_urls = sheet.col_values(2)
existing_urls = existing_urls[1:] if existing_urls else []
print(f"📄 既存URL件数: {len(existing_urls)}")

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "ハッシュタグ", "説明", "画像URL"])

# --- RSSフィード ---
rss_url = "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGRtTVhnU0FtcGhLQUFQAQ?hl=ja&gl=JP&ceid=JP%3Aja&oc=11"
feed = feedparser.parse(rss_url)
entries_to_process = feed.entries[:50][::-1]

# --- Seleniumセットアップ ---
print("🧭 Chromeドライバー起動中...")
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
print("✅ Selenium起動成功")

# --- 定数 ---
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")
EXCLUDE_DOMAINS = ["jp.fashionnetwork.com", "newscast.jp", "www.keidanren.or.jp", "ashu-aseanstatistics.com"]
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"

# --- TextRazorでハッシュタグ生成 ---
def generate_hashtags(text):
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
                if tag:
                    tag = tag.replace(" ", "")
                    if tag not in tags:
                        tags.append(tag)
                if len(tags) >= 5:
                    break
        tags = [t for t in tags if not any(c.isdigit() for c in t)]
        return " ".join(f"#{t}" for t in tags[:5]) if tags else "#タイ #ニュース"
    except Exception as e:
        print(f"TextRazor API error: {e}")
        return "#タイ #ニュース"

# --- テスト書き込み確認 ---
try:
    test_row = ["接続テスト", "https://example.com", "#test", "テスト説明", "https://example.com/test.jpg"]
    sheet.append_row(test_row)
    print("✅ テスト書き込み成功（スプレッドシート動作確認OK）")
except Exception as e:
    print("❌ スプレッドシート書き込みエラー:", e)
    driver.quit()
    exit(1)

# --- RSSフィード処理 ---
for entry in entries_to_process:
    title = entry.title
    google_url = entry.link

    if any(domain in google_url for domain in EXCLUDE_DOMAINS):
        print(f"⏭ 除外ドメインスキップ: {title}")
        continue

    try:
        driver.get(google_url)
        time.sleep(5)
        original_url = driver.current_url
        if any(domain in original_url for domain in EXCLUDE_DOMAINS):
            print(f"⏭ 除外スキップ: {title}")
            continue

        # og:image 取得
        image_url = None
        try:
            og_image = driver.find_element("xpath", "//meta[@property='og:image']")
            image_url = og_image.get_attribute("content")
            if (not image_url or not image_url.lower().endswith(VALID_EXTENSIONS) or not image_url.startswith("https://")):
                image_url = None
        except:
            image_url = None

        # description 取得
        description = None
        try:
            desc = driver.find_element("xpath", "//meta[@name='description']")
            description = desc.get_attribute("content")
        except:
            description = ""

    except Exception as e:
        print(f"⚠️ URL取得エラー: {title} → {e}")
        original_url = google_url
        image_url = None
        description = ""

    # --- 書き込み条件 ---
    if image_url and original_url not in existing_urls:
        hashtags = generate_hashtags(title)
        try:
            sheet.append_row([title, original_url, hashtags, description, image_url])
            existing_urls.append(original_url)
            print(f"✅ 追加: {title} → {original_url}")
        except Exception as e:
            print(f"❌ 書き込み失敗: {title} → {e}")
    else:
        print(f"⏭ スキップ: {title}（画像なし or 既存URL）")

driver.quit()
print("🎉 完了: 最新ニュースをスプレッドシートに追加しました。")
