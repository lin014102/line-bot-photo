from upload_to_drive import upload_file_to_drive
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextMessage
import os
import io
from datetime import datetime
import requests  # ← 要有這行

# ===== LINE 憑證設定 =====
channel_secret = '27ebdd000f8a4e674a505c184452ea1f'
channel_access_token = 'YryJhncuBcIsr3JAkiZjpMuTgsOVJuzEJxEirbT6UforkbEfMIGFjMrfFkJ3ytiI1uBk376jL4c5sL9uZkIp9h0YQ4kqlIRu49MVgBFp3EJfcGk7Wfu0MEYLjaKk3rQm4Mu5aNqBvEgZBDjZPcGXKQdB04t89/1O/w1cDnyilFU='
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# ===== 群組對應資料夾設定 =====
GROUP_ID_TO_FOLDER = {
    'Cbc65ba2020b0bb362aaee4e9df2b4ed0': r'D:\001公運\公務\001公運\114年清潔\保安轉運站',
    'C0300f880576bd5549c6e7c8c4eb76699': r'D:\001公運\公務\001公運\114測試'
}

group_latest_text = {}
pending_images = {}

app = Flask(__name__)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    group_id = getattr(event.source, 'group_id', None)
    if group_id and group_id in GROUP_ID_TO_FOLDER:
        text = event.message.text.strip()
        group_latest_text[group_id] = text

        if group_id in pending_images:
            for image_path in pending_images[group_id]:
                folder_path = os.path.dirname(image_path)
                date_str = os.path.basename(folder_path)
                month_folder = os.path.basename(os.path.dirname(folder_path))
                save_root = GROUP_ID_TO_FOLDER[group_id]
                new_folder_path = os.path.join(save_root, month_folder, date_str)

                os.makedirs(new_folder_path, exist_ok=True)

                count = 1
                while True:
                    new_filename = f"{date_str}__{text}_{count}.jpg"
                    new_path = os.path.join(new_folder_path, new_filename)
                    if not os.path.exists(new_path):
                        os.rename(image_path, new_path)
                        break
                    count += 1

            pending_images[group_id] = []

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    group_id = getattr(event.source, 'group_id', None)
    if not group_id or group_id not in GROUP_ID_TO_FOLDER:
        return

    message_id = event.message.id

    try:
        image_content_response = line_bot_api.get_message_content(message_id)
        image_bytes = io.BytesIO(image_content_response.content)
    except Exception as e:
        print(f"[錯誤] 下載圖片失敗: {e}")
        return

    now = datetime.now()
    month_folder = f"{now.month}月"
    date_str = now.strftime('%m%d')

    save_root = GROUP_ID_TO_FOLDER[group_id]
    folder_path = os.path.join(save_root, month_folder, date_str)
    os.makedirs(folder_path, exist_ok=True)

    temp_filename = f"{now.strftime('%H%M%S')}_{message_id}.jpg"
    file_path = os.path.join(folder_path, temp_filename)

    try:
        with open(file_path, 'wb') as f:
            f.write(image_bytes.getvalue())
            upload_file_to_drive(file_path, os.path.basename(file_path))
    except Exception as e:
        print(f"[錯誤] 儲存圖片失敗: {e}")
        return

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        print(f"[成功] 圖片已儲存：{file_path}")
    else:
        print(f"[錯誤] 圖片儲存失敗或為空檔：{file_path}")

    if group_id not in pending_images:
        pending_images[group_id] = []
    pending_images[group_id].append(file_path)


# ===== Webhook 自動設定區段 =====
def set_webhook_url(webhook_url):
    headers = {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "endpoint": webhook_url
    }
    res = requests.put("https://api.line.me/v2/bot/channel/webhook/endpoint", headers=headers, json=data)
    print(f"[Webhook 設定] 狀態碼: {res.status_code}")
    print(f"[Webhook 設定] 回應內容: {res.text}")

if __name__ == "__main__":
    # 從 ngrok_url.txt 讀取網址
    if os.path.exists("ngrok_url.txt"):
        with open("ngrok_url.txt", "r") as f:
            url = f.read().strip()
            if url:
                set_webhook_url(f"{url}/callback")

    app.run()
