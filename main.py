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
    text = event.message.text.strip()
    match = re.match(r"(.+?)第?([0-9０-９一二三四五六七八九十百千万]+(?:条の)?[0-9０-９一二三四五六七八九十百千万]*)条", text)
    if not match:
        reply = (
            "法令名＋条番号の形式で送ってください（例：民法709条）"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    law, article = match.groups()
    article = normalize_num(article.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
    print(f"送られた法令名：{law}")
    law_id = next((law_map[name] for name in law_map if law.startswith(name)), None)
    print(f"取得した law_id：{law_id}")

    if not law_id:
        reply = (
            "その法令は未対応です。\n"
            "・法令名が正しくない\n"
            "・lawlistに未登録の可能性があります"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    try:
        url = f"https://elaws.e-gov.go.jp/api/1/articles?lawId={law_id}&article={article}"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        text_data = data["Article"][0]["Paragraph"][0]["Sentence"][0]["Text"]
    except Exception as e:
        print("通常取得失敗、fallbackへ:", e)
        try:
            fallback_url = f"https://elaws.e-gov.go.jp/api/1/lawdata/{law_id}"
            headers = {"Accept": "application/json"}
            print("fallback URL:", fallback_url)
            full_res = requests.get(fallback_url, headers=headers)
            print("fallback status:", full_res.status_code)
            print("fallback text (head):", full_res.text[:500])
            full_res.raise_for_status()
            doc = full_res.json()

            text_data = None
            articles = doc.get("Law", {}).get("Article", [])
            if isinstance(articles, dict):
                articles = [articles]
            elif not isinstance(articles, list):
                articles = []

            print("Article件数:", len(articles))

            for a in articles:
                raw = a.get("Num", "")
                print(f"Numの生値: {raw}")
                normalized = normalize_num(raw)
                print(f"比較: {normalized} == {article}")
                if normalized == article:
                    para = a.get("Paragraph", [])
                    if isinstance(para, dict):
                        para = [para]
                    sentences = para[0].get("Sentence", [])
                    if isinstance(sentences, dict):
                        sentences = [sentences]
                    text_data = sentences[0].get("Text")
                    print(f"text_data: {text_data}")
                    break
        except Exception as e:
            print("fallbackも失敗:", e)
            text_data = None

    if text_data is not None:
        reply = f"【{law} 第{article}条】\n{text_data}\n\n📎 https://laws.e-gov.go.jp/document?lawid={law_id}"
    else:
        reply = (
            "取得に失敗しました。\n"
            "・法令名や条番号に誤りがある\n"
            "・対応していない法令かもしれません\n"
            "・または通信タイムアウトの可能性があります"
        )

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)