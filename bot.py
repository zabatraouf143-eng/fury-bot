import sqlite3
import threading
import time
import uuid
import datetime
import random
import string
from flask import Flask, render_template_string, request, session, make_response
import telebot
from telebot import types

TOKEN = "8925665338:AAG-di-iZ3KzyriU_RlOkSSw1KplFzJr3c8"
bot = telebot.TeleBot(TOKEN)
DEV_USERNAME = "raouf100K"

app = Flask(__name__)
app.secret_key = "fury_super_secret_key_2026"

conn = sqlite3.connect("fury_game.db", check_same_thread=False)
cursor = conn.cursor()

# جداول قاعدة البيانات
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            invited_by INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            reward_claimed INTEGER DEFAULT 0,
            last_active REAL DEFAULT 0
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS assistants (
            user_id INTEGER PRIMARY KEY
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS user_button_cooldowns (
            user_id INTEGER,
            button_id INTEGER,
            last_used REAL,
            PRIMARY KEY (user_id, button_id)
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS custom_links (
            button_id INTEGER PRIMARY KEY,
            url TEXT
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS user_bans (
            user_id INTEGER PRIMARY KEY,
            fail_count INTEGER DEFAULT 0,
            ban_until REAL DEFAULT 0,
            ban_level INTEGER DEFAULT 0
        )""")

cursor.execute("""CREATE TABLE IF NOT EXISTS secure_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            button_id INTEGER,
            generated_code TEXT,
            is_used INTEGER DEFAULT 0,
            expires_at REAL
        )""")

cursor.execute("CREATE TABLE IF NOT EXISTS wheel_cooldowns (user_id INTEGER PRIMARY KEY, last_spin REAL, spin_step INTEGER)")
conn.commit()

def check_and_reward_referral(user_id):
    cursor.execute("SELECT points, invited_by, reward_claimed FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        points, invited_by, reward_claimed = row[0], row[1], row[2]
        if invited_by != 0 and reward_claimed == 0 and points >= 30:
            cursor.execute("UPDATE users SET points = points + 25 WHERE user_id = ?", (invited_by,))
            cursor.execute("UPDATE users SET reward_claimed = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            try:
                bot.send_message(invited_by, "🎉 **مبروك! لقد حصلت على 25 نقطة** لأن أحد أصدقائك الذين دعيتهم وصل إلى 30 نقطة! 🚀", parse_mode="Markdown")
            except Exception:
                pass

dev_actions = {}

def is_developer(user):
    if user.username == DEV_USERNAME:
        return True
    cursor.execute("SELECT user_id FROM assistants WHERE user_id = ?", (user.id,))
    return cursor.fetchone() is not None

def main_menu_markup(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_profile = types.KeyboardButton("👤 الملف الشخصي")
    btn_earn = types.KeyboardButton("🎁 تجميع النقاط")
    btn_shop = types.KeyboardButton("🛍️ عروض المتجر")
    btn_support = types.KeyboardButton("📞 الإبلاغ بالمشاكل")
    btn_online = types.KeyboardButton("🌐 عدد المتصلين حاليا")

    markup.add(btn_profile, btn_earn)
    markup.add(btn_shop, btn_support)
    markup.add(btn_online)

    if is_developer(user):
        btn_admin = types.KeyboardButton("⚙️ لوحة المطورين")
        markup.add(btn_admin)
        
    return markup

@bot.message_handler(commands=["start"])
def send_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    current_time = time.time()
    
    args = message.text.split()
    invited_by = 0
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            if ref_id != user_id: invited_by = ref_id
        except ValueError: pass

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, invited_by, last_active) VALUES (?, ?, ?, ?)", (user_id, username, invited_by, current_time))
        if invited_by != 0:
            cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (invited_by,))
    else:
        cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    active_threshold = current_time - 86400
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (active_threshold,))
    active_users = cursor.fetchone()[0]

    welcome_text = f"💎 **أهلاً بك عزيزي في بوت شحن جواهر فري فاير مجاناً!** 🎮\n\n👥 **عدد المستخدمين الكلي:** `{total_users}`\n⚡ **المستخدمين النشطين (24 ساعة):** `{active_users}`\n\nاختر ما يناسبك من الأزرار بالأسفل لتجميع النقاط وشحن جواهرك! 🔥"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_markup(message.from_user), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["👤 الملف الشخصي", "🎁 تجميع النقاط", "🛍️ عروض المتجر", "📞 الإبلاغ بالمشاكل", "🌐 عدد المتصلين حاليا", "⚙️ لوحة المطورين", "🔙 رجوع للقائمة الرئيسية"])
def handle_main_buttons(message):
    user_id = message.from_user.id
    text = message.text
    current_time = time.time()
    cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    if text == "👤 الملف الشخصي":
        cursor.execute("SELECT points, referral_count FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        pts, refs = (res[0] if res else 0), (res[1] if res else 0)
        profile_text = f"👤 **الملف الشخصي الخاص بك:**\n\n🆔 **آيدي حسابك:** `{user_id}`\n⭐ **رصيد النقاط:** `{pts}` نقطة\n👥 **المنضمين عبر رابطك:** `{refs}` شخص\n🔗 **رابط الاحالة:**\n`https://t.me/{bot.get_me().username}?start={user_id}`"
        bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")

    elif text == "🎁 تجميع النقاط":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📌 الطريقة الأولى (رابط الاحالة)", callback_data="earn_method_1"))
        markup.add(types.InlineKeyboardButton("🔗 الطريقة الثانية (اختصار الروابط) - V3", callback_data="earn_method_2"))
        markup.add(types.InlineKeyboardButton("🎡 الطريقة الثالثة (عجلة الحظ)", callback_data="earn_wheel"))
        bot.send_message(message.chat.id, "🎁 **اختر طريقة تجميع النقاط المناسبة لك:**", reply_markup=markup, parse_mode="Markdown")

    elif text == "🛍️ عروض المتجر":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💎 110 جوهرة = 220 نقطة", callback_data="shop_1"))
        markup.add(types.InlineKeyboardButton("💎 220 جوهرة = 420 نقطة", callback_data="shop_2"))
        markup.add(types.InlineKeyboardButton("💎 330 جوهرة = 640 نقطة", callback_data="shop_3"))
        shop_msg = "🛍️ **قائمة عروض شحن جواهر فري فاير (V3):**\n\n1️⃣ **110 جوهرة** = `220 نقطة`\n2️⃣ **220 جوهرة** = `420 نقطة`\n3️⃣ **330 جوهرة** = `640 نقطة`\n\nاضغط على العرض لاختياره! 🟢"
        bot.send_message(message.chat.id, shop_msg, reply_markup=markup, parse_mode="Markdown")

    elif text == "📞 الإبلاغ بالمشاكل":
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💬 مراسلة المطور مباشرة", url=f"https://t.me/{DEV_USERNAME}"))
        bot.send_message(message.chat.id, "📞 **هل تواجه مشكلة أو استفسار؟**\nتواصل مع المطور مباشرة عبر الزر أدناه:", reply_markup=markup, parse_mode="Markdown")

    elif text == "🌐 عدد المتصلين حاليا":
        # حساب النشطين في هذه اللحظة (آخر 60 ثانية)
        online_threshold = current_time - 60
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (online_threshold,))
        online_count = cursor.fetchone()[0]
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="refresh_online"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.send_message(message.chat.id, f"🌐 **عدد المتصلين حالياً في البوت:** `{online_count}` مستخدماً 🟢", reply_markup=markup, parse_mode="Markdown")

    elif text == "⚙️ لوحة المطورين":
        if not is_developer(message.from_user):
            bot.reply_to(message, "❌ عذراً، هذه اللوحة خاصة بالمطورين فقط!")
            return
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(types.KeyboardButton("➕ إضافة نقاط"), types.KeyboardButton("➖ خصم نقاط"),
                   types.KeyboardButton("🔗 إضافة روابط"), types.KeyboardButton("📢 إضافة منشور"),
                   types.KeyboardButton("➕ إضافة مساعد"), types.KeyboardButton("➖ إزالة مساعد"),
                   types.KeyboardButton("🔍 البحث عن مستخدم"), types.KeyboardButton("🔙 رجوع للقائمة الرئيسية"))
        bot.send_message(message.chat.id, "⚙ **أهلاً بك في لوحة المطورين:**", reply_markup=markup)

    elif text == "🔙 رجوع للقائمة الرئيسية":
        bot.send_message(message.chat.id, "🏠 القائمة الرئيسية:", reply_markup=main_menu_markup(message.from_user))

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id

    if call.data == "refresh_online":
        current_time = time.time()
        online_threshold = current_time - 60
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (online_threshold,))
        online_count = cursor.fetchone()[0]
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="refresh_online"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        try:
            bot.edit_message_text(f"🌐 **عدد المتصلين حالياً في البوت:** `{online_count}` مستخدماً 🟢", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            pass
        bot.answer_callback_query(call.id, "✅ تم التحديث بنجاح!")

    elif call.data == "back_to_main":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "🏠 القائمة الرئيسية:", reply_markup=main_menu_markup(call.from_user))

    elif call.data == "earn_method_1":
        ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        text = f"📌 **الطريقة الأولى:**\nشارك رابطك:\n`{ref_link}`\n\n💡 كل شخص ينضم ويجمع 30 نقطة تربح أنت 25 نقطة!"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_earn"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "earn_method_2":
        text = "🔗 **الطريقة الثانية (اختصار الروابط) - V4:**\nاختر أحد الأزرار أدناه (1 إلى 15):"
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"زر {i}", callback_data=f"link_btn_{i}") for i in range(1, 16)]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_earn"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "earn_wheel":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎯 تدوير العجلة الآن", callback_data="do_spin"),
                   types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_earn"))
        bot.edit_message_text("🎡 **الطريقة الثالثة: عجلة الحظ اليومية!**\n\n⏳ يمكنك تدويرها كل 24 ساعة لربح نقاط مجانية.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "back_to_earn":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📌 الطريقة الأولى (رابط الاحالة)", callback_data="earn_method_1"))
        markup.add(types.InlineKeyboardButton("🔗 الطريقة الثانية (اختصار الروابط) - V4", callback_data="earn_method_2"))
        markup.add(types.InlineKeyboardButton("🎡 الطريقة الثالثة (عجلة الحظ)", callback_data="earn_wheel"))
        bot.edit_message_text("🎁 **اختر طريقة تجميع النقاط المناسبة لك:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "do_spin":
        current_time = time.time()
        cursor.execute("SELECT last_spin, spin_step FROM wheel_cooldowns WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and (current_time - row[0] < 86400):
            rem_sec = 86400 - (current_time - row[0])
            rem_h = int(rem_sec // 3600)
            rem_m = int((rem_sec % 3600) // 60)
            bot.answer_callback_query(call.id, f"⏳ عذراً، يجب الانتظار {rem_h} ساعة و {rem_m} دقيقة لتدوير العجلة مجدداً!", show_alert=True)
            return
        
        spin_step = (row[1] + 1) if row else 1
        earned_pts = 3 if spin_step == 1 else (0 if spin_step == 2 else (3 if spin_step == 3 else 1))
            
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (earned_pts, user_id))
        cursor.execute("INSERT OR REPLACE INTO wheel_cooldowns (user_id, last_spin, spin_step) VALUES (?, ?, ?)", (user_id, current_time, spin_step))
        conn.commit()
        
        check_and_reward_referral(user_id)
        
        bot.answer_callback_query(call.id, f"🎉 مبروك! ربحت {earned_pts} نقطة!", show_alert=True)
        bot.edit_message_text(f"🎯 **نتيجة عجلة الحظ:**\n✨ حصلت على: `{earned_pts} نقطة`!", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="earn_wheel")), parse_mode="Markdown")

    elif call.data.startswith("set_link_"):
        if not is_developer(call.from_user):
            bot.answer_callback_query(call.id, "❌ خاصة بالمطورين فقط!", show_alert=True)
            return
        btn_id = int(call.data.split("_")[2])
        msg = bot.send_message(call.message.chat.id, f"🔗 أرسل رابط الموقع الثابت الخاص بالزر رقم `{btn_id}`:")
        bot.register_next_step_handler(msg, lambda m: save_custom_link(m, btn_id))
        bot.answer_callback_query(call.id)

    elif call.data.startswith("link_btn_"):
        btn_id = int(call.data.split("_")[2])
        current_time = time.time()
        cursor.execute("SELECT last_used FROM user_button_cooldowns WHERE user_id = ? AND button_id = ?", (user_id, btn_id))
        row = cursor.fetchone()
        if row and (current_time - row[0] < 86400):
            rem_sec = 86400 - (current_time - row[0])
            rem_h = int(rem_sec // 3600)
            rem_m = int((rem_sec % 3600) // 60)
            bot.answer_callback_query(call.id, f"⏳ الزر قيد الانتظار. يرجى الانتظار {rem_h} ساعة و {rem_m} دقيقة.", show_alert=True)
            return

        cursor.execute("SELECT url FROM custom_links WHERE button_id = ?", (btn_id,))
        link_row = cursor.fetchone()
        
        base_site_url = link_row[0] if (link_row and link_row[0]) else f"https://yourdomain.com/earn?btn={btn_id}"

        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🌐 الانتقال لرابط الاختصار", url=base_site_url)).add(types.InlineKeyboardButton("🔙 رجوع", callback_data="earn_method_2"))
        bot.edit_message_text(f"🔗 **الزر رقم {btn_id}:**\nاضغط للذهاب لرابط الاختصار وإتمام العملية للحصول على الكود!", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("shop_"):
        shop_type = call.data.split("_")[1]
        items = {"1": "110 جوهرة (220 نقطة)", "2": "220 جوهرة (420 نقطة)", "3": "330 جوهرة (640 نقطة)"}
        item_name = items.get(shop_type, "عرض غير معروف")
        
        msg = f"🛍️ لقد اخترت عرض: {item_name}\n\nللتأكيد، راسل المطور:\n1️⃣ آيدي فري فاير\n2️⃣ آيدي البوت (`{user_id}`)\n3️⃣ اسم العرض 🟢"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💬 مراسلة المطور للتأكيد", url=f"https://t.me/{DEV_USERNAME}"))
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

def save_custom_link(message, btn_id):
    if not is_developer(message.from_user):
        bot.reply_to(message, "❌ ليس لديك صلاحية!")
        return
    url = message.text.strip()
    cursor.execute("INSERT OR REPLACE INTO custom_links (button_id, url) VALUES (?, ?)", (btn_id, url))
    conn.commit()
    bot.reply_to(message, f"✅ تم حفظ الرابط الثابت للزر رقم {btn_id} بنجاح!")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    current_time = time.time()
    cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (current_time, user_id))
    conn.commit()

    if text == "🔗 إضافة روابط" and is_developer(message.from_user):
        markup = types.InlineKeyboardMarkup(row_width=5)
        buttons = [types.InlineKeyboardButton(f"رابط {i}", callback_data=f"set_link_{i}") for i in range(1, 16)]
        markup.add(*buttons)
        bot.send_message(message.chat.id, "🔗 **اختر الزر (1 إلى 15) لتعديل رابطه الثابت:**", reply_markup=markup)
        return

    elif text == "➕ إضافة نقاط" and is_developer(message.from_user):
        dev_actions[user_id] = "add"
        msg = bot.send_message(message.chat.id, "➕ **أدخل آيدي المستخدم المراد إضافة النقاط له:**")
        bot.register_next_step_handler(msg, process_target_user_for_points)
        return

    elif text == "➖ خصم نقاط" and is_developer(message.from_user):
        dev_actions[user_id] = "sub"
        msg = bot.send_message(message.chat.id, "➖ **أدخل آيدي المستخدم المراد خصم النقاط منه:**")
        bot.register_next_step_handler(msg, process_target_user_for_points)
        return

    elif text == "📢 إضافة منشور" and is_developer(message.from_user):
        msg = bot.send_message(message.chat.id, "📢 أرسل المنشور لإرساله للجميع:")
        bot.register_next_step_handler(msg, process_broadcast)
        return

    elif text == "➕ إضافة مساعد" and is_developer(message.from_user):
        cursor.execute("SELECT COUNT(*) FROM assistants")
        count = cursor.fetchone()[0]
        msg = bot.send_message(message.chat.id, f"👥 **عدد المساعدين الحاليين:** `{count}`\n\n📥 **أدخل آيدي المساعد الجديد:**")
        bot.register_next_step_handler(msg, process_add_assistant)
        return

    elif text == "➖ إزالة مساعد" and is_developer(message.from_user):
        cursor.execute("SELECT COUNT(*) FROM assistants")
        count = cursor.fetchone()[0]
        msg = bot.send_message(message.chat.id, f"👥 **عدد المساعدين الحاليين:** `{count}`\n\n📥 **أدخل آيدي المساعد المراد إزالته:**")
        bot.register_next_step_handler(msg, process_remove_assistant)
        return

    elif text == "🔍 البحث عن مستخدم" and is_developer(message.from_user):
        msg = bot.send_message(message.chat.id, "🔍 **أدخل رقم ترتيب المستخدم في البوت (مثلاً: 1 لأول مشترك، 2 للثاني...):**")
        bot.register_next_step_handler(msg, process_search_user_by_index)
        return

    cursor.execute("SELECT fail_count, ban_until, ban_level FROM user_bans WHERE user_id = ?", (user_id,))
    ban_data = cursor.fetchone()
    if ban_data and current_time < ban_data[1]:
        bot.reply_to(message, f"❌ حسابك محظور مؤقتاً لمدة `{int((ban_data[1] - current_time) / 60)}` دقيقة.", parse_mode="Markdown")
        return

    if 8 <= len(text) <= 16:
        cursor.execute("SELECT token, button_id, is_used FROM secure_tokens WHERE
