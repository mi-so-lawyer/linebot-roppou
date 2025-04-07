from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, re, json, requests

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

with open("lawlist.json", encoding="utf-8") as f:
    lawlist = json.load(f)
law_map = {entry["lawName"]: entry["lawId"] for entry in lawlist}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("Error:", e)
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    match = re.match(r"(.+?)第?([0-9０-９一二三四五六七八九十百千万]+)条", text)
    if not match:
        reply = "法令名＋条番号の形式で送ってください（例：民法709条）"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    law, article = match.groups()
    article = re.sub(r"[第条]", "", article).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    law_id = next((law_map[name] for name in law_map if law.startswith(name)), None)

    if not law_id:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="その法令は未対応です"))
        return

    url = f"https://elaws.e-gov.go.jp/api/1/articles?lawId={law_id}&article={article}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        print("=== e-Gov API レスポンス ===")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        text_data = data["Article"][0]["Paragraph"][0]["Sentence"][0]["Text"]
        reply = f"【{law} 第{article}条】\n{text_data}\n\n📎 https://laws.e-gov.go.jp/document?lawid={law_id}"
    except Exception as e:
        print("=== エラー内容 ===")
        print(e)
        reply = "取得に失敗しました"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)