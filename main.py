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
    law_map = {}
    for entry in lawlist:
        law_map[entry["lawName"]] = entry["lawId"]
        for alias in entry.get("aliases", []):
            law_map[alias] = entry["lawId"]
    log("🔍 law_map構築完了。キー一覧（上位10件）:")
    for i, key in enumerate(list(law_map.keys())[:10]):
        log(f"  {i+1}. {key} → {law_map[key]}")
    log(f"✅ '憲法' in law_map? → {'憲法' in law_map}")
except Exception as e:
    log(f"lawlist.json 読み込み失敗: {e}")
    lawlist = []
    law_map = {}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        log(f"handle error: {e}")
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    log("📩 handle_message invoked")
    text = event.message.text.strip()
    match = re.match(r"(.+?)第?([0-9０-９一二三四五六七八九十百千万]+(?:条の)?[0-9０-９一二三四五六七八九十百千万]*)条", text)
    if not match:
        reply = "法令名＋条番号の形式で送ってください（例：民法709条）"
        log(f"最終reply = {reply!r}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    law, article = match.groups()
    article = normalize_num(article.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
    log(f"送られた法令名：{law}")
    law_id = law_map.get(law)
    log(f"取得した law_id：{law_id}")

    if not law_id:
        reply = "その法令は未対応です。"
        log(f"最終reply = {reply!r}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    reply = f"【{law} 第{article}条】\n（ダミー本文）\n\n📎 https://laws.e-gov.go.jp/document?lawid={law_id}"
    log(f"✅ 最終reply = {reply!r}")
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    log("👁 MAIN.PY 起動しました")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)