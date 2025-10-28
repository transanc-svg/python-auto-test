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
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- ヘッダー追加 ---
if not existing_urls:
    sheet.append_row(["タイトル", "URL", "C列", "D列(description)", "画像URL(E列)"])

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")
EXCLUDE_DOMAINS = ["jp.fashionnetwork.com", "newscast.jp", "www.keidanren.or.jp", "ashu-aseanstatistics.com"]

# --- TextRazor APIキー ---
TEXTRAZOR_API_KEY = "fbedccf39739132e30c41096c166561c9cfb85bc36b44c1c16c8b8a2"

# --- TextRazorでハッシュタグ生成 ---
def generate_hashtags(text):
    url = "https://api.textrazor.com/"
    payload = {"text": text, "extractors": "entities,topics,words"}
    headers = {
        "X-TextRazor-Key": TEXTRAZOR_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
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

    try:
        # Googleニュースの中継URLを開く
        driver.get(google_url)
        time.sleep(2)

        # 本物の記事URLを取得（最初のリンク）
        try:
            article_element = driver.find_element("css selector", "article a")
            original_url = article_element.get_attribute("href")
        except:
            original_url = google_url

        # 除外ドメインチェック
        if any(domain in original_url for domain in EXCLUDE_DOMAINS):
            print(f"除外スキップ: {title} → {original_url}")
            continue

        # 本記事ページを開く
        driver.get(original_url)
        time.sleep(2)

        image_url = None
        description = None

        # 1️⃣ og:image を取得
        try:
            og_image_element = driver.find_element("xpath", "//meta[@property='og:image']")
            image_url = og_image_element.get_attribute("content")
            if not image_url or not image_url.lower().endswith(VALID_EXTENSIONS):
                image_url = None
        except:
            image_url = None

        # 2️⃣ og:image がない場合はページ内 img タグから取得
        if not image_url:
            try:
                img_element = driver.find_element(
                    "xpath", "//img[contains(@src,'.jpg') or contains(@src,'.png') or contains(@src,'.jpeg')]"
                )
                img_src = img_element.get_attribute("src")
                if img_src and img_src.startswith("http"):
                    image_url = img_src
            except:
                image_url = None

        # description を取得
        try:
            desc_element = driver.find_element("xpath", "//meta[@name='description']")
            description = desc_element.get_attribute("content")
        except:
            description = None

    except Exception as e:
        print(f"Error fetching URL for {title}: {e}")
        image_url = None
        description = None
        original_url = google_url

    # 画像がある場合のみスプレッドシートに追加
    if image_url and original_url not in existing_urls:
        description = description or ""
        hashtags = generate_hashtags(title)
        sheet.append_row([title, original_url, hashtags, description, image_url])
        existing_urls.append(original_url)
        print(f"✅ 追加: {title} → {original_url} / {image_url}")
    else:
        print(f"⏭ スキップ: {title}（画像なし/既存）")

driver.quit()
print("✅ 最新ニュースから画像・description・ハッシュタグをスプレッドシートに追加しました。")
