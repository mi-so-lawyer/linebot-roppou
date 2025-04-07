from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, re, json, requests, sys
import xml.etree.ElementTree as ET

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

def log(msg):
    sys.stderr.write(f"{msg}\n")
    sys.stderr.flush()

def normalize_num(num):
    num = re.sub(r"[第条の]", "", num)
    num = num.replace("_", "")
    num = num.translate(str.maketrans("〇一二三四五六七八九", "0123456789"))
    return num

try:
    with open("lawlist.json", encoding="utf-8") as f:
        lawlist = json.load(f)
    log("=== lawlist.json の先頭5件 ===")
    for entry in lawlist[:5]:
        log(json.dumps(entry, ensure_ascii=False))
    law_map = {}
    for entry in lawlist:
        law_map[entry["lawName"]] = entry["lawId"]
        for alias in entry.get("aliases", []):
            law_map[alias] = entry["lawId"]
    log(f"✅ '憲法' in law_map? → {'憲法' in law_map}")
    log(f"✅ '民法' in law_map? → {'民法' in law_map}")
except Exception as e:
    log(f"lawlist.json 読み込み失敗: {e}")
    lawlist = []
    law_map = {}

@app.route("/callback", methods=["POST"])
def callback():
    return "OK"