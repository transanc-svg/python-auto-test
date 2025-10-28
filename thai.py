import requests
import feedparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# --- Google スプレッドシート認証 ---
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

google_creds = os.environ.get("GOOGLE_CREDENTIALS")
if not google_creds:
    raise Exception("環境変数 GOOGLE_CREDENTIALS が設定されていません")

creds_dict = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfil
