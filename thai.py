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

# --- 既存URLを取得して重複防止 ---
existing_urls = sheet.col_values(2)
existing_urls = existing_urls[1:] if existing_urls else []

# --- Selenium セットアップ ---
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- Googleニュース トピックスページ ---
google_news_url = "https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZ4ZERBU0Ftb0Jna0FQAQ?hl=ja&gl=JP&ceid=JP:ja"
driver.get(google_news_url)
time.sleep(3)

# --- 記事を取得 ---
articles = driver.find_elements("xpath", "//article//h3/a")
print(f"📌 記事取得件数: {len(articles)}")

# --- TextRazor API ---
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096f166561c9cfb85bc36b44c1c16c8b8a2"
FALLBACK_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg"

def generate_hashtags(text):
    url = "https://api.textrazor.com/"
    payload = {"text": text, "extractors": "entities,topics,words"}
    headers = {"X-TextRazor-Key": TEXTRAZOR_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
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
        return " ".join(f"#{t}" for t in tags[:5]) if tags else "#タイ #ニュース"
    except Exception as e:
        print(f"TextRazor API error: {e}")
        return "#タイ #ニュース"

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "ハッシュタグ", "説明", "画像URL"])

# --- 記事ごとにスプレッドシートに追加 ---
for i, article in enumerate(articles, 1):
    try:
        title = article.text
        url = article.get_attribute("href")

        if url in existing_urls:
            print(f"⏭ スキップ（既存URL）: {title}")
            continue

        # --- 記事ページを開いて description と og:image を取得 ---
        driver.get(url)
        time.sleep(2)
        description = ""
        image_url = FALLBACK_IMAGE_URL

        try:
            desc_element = driver.find_element("xpath", "//meta[@name='description']")
            description = desc_element.get_attribute("content") or ""
        except:
            description = ""

        try:
            img_element = driver.find_element("xpath", "//meta[@property='og:image']")
            img = img_element.get_attribute("content")
            if img and img.startswith("http"):
                image_url = img
        except:
            image_url = FALLBACK_IMAGE_URL

        hashtags = generate_hashtags(title)

        # --- スプレッドシートに追加 ---
        sheet.append_row([title, url, hashtags, description, image_url])
        existing_urls.append(url)
        print(f"✅ 追加成功: {title}")

    except Exception as e:
        print(f"❌ 記事処理失敗: {e}")

driver.quit()
print("🎉 Googleニュース記事をスプレッドシートに追加完了")
