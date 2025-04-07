from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, re, json, requests

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

def normalize_num(num):
    num = re.sub(r"[第条の]", "", num)
    num = num.replace("_", "")
    num = num.translate(str.maketrans("〇一二三四五六七八九", "0123456789"))
    return num

try:
    with open("lawlist.json", encoding="utf-8") as f:
        lawlist = json.load(f)
    law_map = {entry["lawName"]: entry["lawId"] for entry in lawlist}
except Exception as e:
    print("lawlist.json 読み込み失敗:", e)
    lawlist = []
    law_map = {}

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
    print("📩 handle_message invoked")
    text = event.message.text.strip()
    match = re.match(r"(.+?)第?([0-9０-９一二三四五六七八九十百千万]+(?:条の)?[0-9０-９一二三四五六七八九十百千万]*)条", text)
    if not match:
        reply = "法令名＋条番号の形式で送ってください（例：民法709条）"
        print(f"最終reply = {reply!r}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    law, article = match.groups()
    article = normalize_num(article.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
    print(f"送られた法令名：{law}")
    law_id = next((law_map[name] for name in law_map if law.startswith(name)), None)
    print(f"取得した law_id：{law_id}")
    if not law_id:
        reply = "その法令は未対応です。"
        print(f"最終reply = {reply!r}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    try:
        print("▶ 通常取得開始")
        url = f"https://elaws.e-gov.go.jp/api/1/articles?lawId={law_id}&article={article}"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        text_data = data["Article"][0]["Paragraph"][0]["Sentence"][0]["Text"]
        reply = f"【{law} 第{article}条】\n{text_data}\n\n📎 https://laws.e-gov.go.jp/document?lawid={law_id}"
        print(f"通常取得reply = {reply!r}")
    except Exception as e:
        print("通常取得失敗、fallbackへ:", e)
        try:
            fallback_url = f"https://elaws.e-gov.go.jp/api/1/lawdata/{law_id}"
            headers = {"Accept": "application/json"}
            print("🌐 fallback URL:", fallback_url)
            full_res = requests.get(fallback_url, headers=headers)
            full_res.raise_for_status()
            doc = full_res.json()
            articles = doc.get("Law", {}).get("Article", [])
            if isinstance(articles, dict):
                articles = [articles]
            text_data = None
            for a in articles:
                raw = a.get("Num", "")
                normalized = normalize_num(raw)
                if normalized == article:
                    para = a.get("Paragraph", [])
                    if isinstance(para, dict):
                        para = [para]
                    sentences = para[0].get("Sentence", [])
                    if isinstance(sentences, dict):
                        sentences = [sentences]
                    text_data = sentences[0].get("Text")
                    break
            if text_data is not None:
                reply = f"【{law} 第{article}条】\n{text_data}\n\n📎 https://laws.e-gov.go.jp/document?lawid={law_id}"
                print(f"fallback reply = {reply!r}")
            else:
                reply = "取得に失敗しました。"
                print(f"fallback取得失敗 reply = {reply!r}")
        except Exception as e:
            reply = "取得に失敗しました。"
            print("fallbackも例外:", e)
    print(f"✅ 最終reply = {reply!r}")
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    print("👁 MAIN.PY 起動しました")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)