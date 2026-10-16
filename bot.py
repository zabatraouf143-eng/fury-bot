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
        markup.add(types.InlineKeyboardButton("🔗 الطريقة الثانية (اختصار الروابط) - V4", callback_data="earn_method_2"))
        markup.add(types.InlineKeyboardButton("🎡 الطريقة الثالثة (عجلة الحظ)", callback_data="earn_wheel"))
        bot.send_message(message.chat.id, "🎁 **اختر طريقة تجميع النقاط المناسبة لك:**", reply_markup=markup, parse_mode="Markdown")

    elif text == "🛍️ عروض المتجر":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💎 110 جوهرة = 220 نقطة", callback_data="shop_1"))
        markup.add(types.InlineKeyboardButton("💎 220 جوهرة = 420 نقطة", callback_data="shop_2"))
        markup.add(types.InlineKeyboardButton("💎 330 جوهرة = 640 نقطة", callback_data="shop_3"))
        shop_msg = "🛍️ **قائمة عروض شحن جواهر فري فاير (V4):**\n\n1️⃣ **110 جوهرة** = `220 نقطة`\n2️⃣ **220 جوهرة** = `420 نقطة`\n3️⃣ **330 جوهرة** = `640 نقطة`\n\nاضغط على العرض لاختياره! 🟢"
        bot.send_message(message.chat.id, shop_msg, reply_markup=markup, parse_mode="Markdown")

    elif text == "📞 الإبلاغ بالمشاكل":
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💬 مراسلة المطور مباشرة", url=f"https://t.me/{DEV_USERNAME}"))
        bot.send_message(message.chat.id, "📞 **هل تواجه مشكلة أو استفسار؟**\nتواصل مع المطور مباشرة عبر الزر أدناه:", reply_markup=markup, parse_mode="Markdown")

    elif text == "🌐 عدد المتصلين حاليا":
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
        
        base_site_url = link_row[0] if (link_row and link_row[0]) else f"https://fury-bot-4pef.onrender.com/earn?btn={btn_id}"

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
        cursor.execute("SELECT token, button_id, is_used FROM secure_tokens WHERE generated_code = ? AND user_id = ?", (text, user_id))
        token_row = cursor.fetchone()
        if token_row:
            if token_row[2] == 1:
                bot.reply_to(message, "⚠ هذا الكود مستخدم من قبل!", parse_mode="Markdown")
                return
            cursor.execute("UPDATE secure_tokens SET is_used = 1 WHERE token = ?", (token_row[0],))
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT OR REPLACE INTO user_button_cooldowns (user_id, button_id, last_used) VALUES (?, ?, ?)", (user_id, token_row[1], current_time))
            cursor.execute("DELETE FROM user_bans WHERE user_id = ?", (user_id,))
            conn.commit()
            
            check_and_reward_referral(user_id)
            
            bot.reply_to(message, "🎉 **تهانينا! الكود صحيح وتم إضافة `1 نقطة` بنجاح!** 🔥", parse_mode="Markdown")
            return
        else:
            handle_failed_code(message, user_id)
            return

def process_add_assistant(message):
    if not is_developer(message.from_user): return
    try:
        ast_id = int(message.text.strip())
        cursor.execute("INSERT OR IGNORE INTO assistants (user_id) VALUES (?)", (ast_id,))
        conn.commit()
        bot.reply_to(message, f"✅ تمت إضافة المستخدم `{ast_id}` كـ مساعد معك بنجاح وأصبح قادراً على الوصول لوحة المطورين! 🟢", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ يرجى إدخال آيدي صحيح (أرقام فقط)!")

def process_remove_assistant(message):
    if not is_developer(message.from_user): return
    try:
        ast_id = int(message.text.strip())
        cursor.execute("DELETE FROM assistants WHERE user_id = ?", (ast_id,))
        conn.commit()
        bot.reply_to(message, f"✅ تمت إزالة المستخدم `{ast_id}` من قائمة المساعدين بنجاح!", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ يرجى إدخال آيدي صحيح (أرقام فقط)!")

def process_search_user_by_index(message):
    if not is_developer(message.from_user): return
    try:
        index = int(message.text.strip())
        if index < 1:
            bot.reply_to(message, "❌ يرجى إدخال رقم يبدأ من 1 فصاعداً!")
            return
        cursor.execute("SELECT user_id, username, points, invited_by, referral_count FROM users LIMIT 1 OFFSET ?", (index - 1,))
        row = cursor.fetchone()
        if not row:
            bot.reply_to(message, "❌ عذراً، لا يوجد مستخدم بهذا الترتيب في البوت!")
            return
        u_id, u_name, pts, inv, refs = row
        result_text = f"🔍 **نتيجة البحث عن المستخدم رقم `{index}`:**\n\n🆔 **الايدي:** `{u_id}`\n👤 **اليوزر:** @{u_name}\n⭐ **النقاط:** `{pts}`\n👥 **المحيل (دعاه):** `{inv}`\n🔗 **عدد الدعوات:** `{refs}` شخص"
        bot.reply_to(message, result_text, parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ يرجى إدخال رقم صحيح!")

def handle_failed_code(message, user_id):
    current_time = time.time()
    cursor.execute("SELECT fail_count, ban_level FROM user_bans WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    fail_count = (row[0] + 1) if row else 1
    ban_level = row[1] if row else 0

    if fail_count >= 3:
        ban_level += 1
        ban_duration = 600 if ban_level == 1 else (3600 if ban_level == 2 else 86400)
        cursor.execute("INSERT OR REPLACE INTO user_bans (user_id, fail_count, ban_until, ban_level) VALUES (?, 0, ?, ?)", (user_id, current_time + ban_duration, ban_level))
        conn.commit()
        bot.reply_to(message, f"❌ خطأ 3 مرات! تم حظرك مؤقتاً لمدة `{int(ban_duration / 60)}` دقيقة.", parse_mode="Markdown")
    else:
        cursor.execute("INSERT OR REPLACE INTO user_bans (user_id, fail_count, ban_until, ban_level) VALUES (?, ?, 0, ?)", (user_id, fail_count, ban_level))
        conn.commit()
        bot.reply_to(message, f"❌ كود خاطئ! تتبقى لك `{3 - fail_count}` محاولات.", parse_mode="Markdown")

def process_target_user_for_points(message):
    if not is_developer(message.from_user): return
    try:
        target_id = int(message.text.strip())
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (target_id,))
        row = cursor.fetchone()
        if not row:
            bot.reply_to(message, "❌ المستخدم غير موجود في قاعدة البيانات!")
            return
        current_pts = row[0]
        action_type = dev_actions.get(message.from_user.id, "add")
        action_name = "إضافتها" if action_type == "add" else "خصمها"
        
        msg = bot.send_message(message.chat.id, f"👤 **المستخدم:** `{target_id}`\n⭐ **عدد نقاطه الحالية:** `{current_pts}` نقطة\n\n📥 **أدخل عدد النقاط التي تريد {action_name}:**")
        bot.register_next_step_handler(msg, lambda m: execute_points_change(m, target_id, action_type))
    except ValueError:
        bot.reply_to(message, "❌ يرجى إدخال آيدي صحيح (أرقام فقط)!")

def execute_points_change(message, target_id, action_type):
    if not is_developer(message.from_user): return
    try:
        amount = int(message.text.strip())
        if action_type == "add":
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, target_id))
            action_desc = "إضافة"
        else:
            cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (amount, target_id))
            action_desc = "خصم"
        conn.commit()
        
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (target_id,))
        new_pts = cursor.fetchone()[0]
        
        if action_type == "add":
            check_and_reward_referral(target_id)
            
        bot.reply_to(message, f"✅ تم {action_desc} `{amount}` نقطة بنجاح!\n⭐ الرصيد الجديد للمستخدم: `{new_pts}` نقطة.")
    except ValueError:
        bot.reply_to(message, "❌ يرجى إدخال رقم صحيح لعدد النقاط!")

def process_broadcast(message):
    if not is_developer(message.from_user): return
    success = sum(1 for u in cursor.execute("SELECT user_id FROM users").fetchall() if bot.send_message(u[0], message.text))
    bot.reply_to(message, f"📢 تم الإرسال إلى {success} مستخدماً.")

# قالب صفحة الويب الثابتة والمحمية ضد التلاعب والـ Refresh مع النص المعدل الواضح
HTML_TEMPLATE = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FURY SYSTEM V4 - الحصول على الكود</title>
<style>
body{background:#0f172a;color:#f8fafc;font-family:Tahoma;text-align:center;padding:20px;margin:0}
.container{max-width:400px;margin:50px auto;background:#1e293b;padding:25px;border-radius:15px;box-shadow:0 10px 25px rgba(0,0,0,0.3)}
input{width:90%;padding:12px;margin:15px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;text-align:center;font-size:16px}
button{background:#22c55e;color:#fff;border:none;padding:12px;border-radius:8px;width:100%;font-weight:bold;cursor:pointer;font-size:16px}
button:hover{background:#16a34a}
.error{color:#ef4444;font-weight:bold;background:#1e293b;padding:10px;border-radius:6px;border:1px solid #ef4444}
.success{color:#22c55e;font-size:18px;font-weight:bold;background:#0f172a;padding:15px;border-radius:8px;border:1px dashed #22c55e;word-break:break-all}
</style>
</head>
<body>
<div class="container">
<h2>🔥 نظام الحصول على الكود (V4)</h2>
{% if error %}
<p class="error">{{ error }}</p>
{% elif code %}
<p>✅ تم توليد الكود بنجاح:</p>
<div class="success" id="codeText">{{ code }}</div>
<button onclick="copyCode()" style="margin-top:15px; background:#3b82f6;">📋 نسخ الكود</button>
<script>
function copyCode() {
    var text = document.getElementById("codeText").innerText;
    navigator.clipboard.writeText(text);
    alert("✅ تم نسخ الكود بنجاح! الصقه في البوت الآن.");
}
</script>
{% else %}
<form method="POST">
<input type="number" name="telegram_id" placeholder="أدخل آيدي حسابك في البوت" required autocomplete="off">
<button type="submit">إرسال والحصول على الكود</button>
</form>
{% endif %}
</div>
</body></html>"""

@app.route("/earn", methods=["GET", "POST"])
def earn_page():
    btn_id = request.args.get("btn", "1")
    
    response = make_response()
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    if request.method == "POST":
        if session.get("already_claimed"):
            return render_template_string(HTML_TEMPLATE, error="❌ هذه الصفحة منتهية أو تم استهلاكها مسبقاً! ابدأ من جديد من البوت.")

        try:
            user_id = int(request.form.get("telegram_id"))
        except ValueError:
            return render_template_string(HTML_TEMPLATE, error="❌ آيدي غير صالح!")

        current_time = time.time()
        cursor.execute("SELECT last_used FROM user_button_cooldowns WHERE user_id = ? AND button_id = ?", (user_id, btn_id))
        row = cursor.fetchone()
        if row and (current_time - row[0] < 86400):
            rem_sec = 86400 - (current_time - row[0])
            rem_h = int(rem_sec // 3600)
            rem_m = int((rem_sec % 3600) // 60)
            return render_template_string(HTML_TEMPLATE, error=f"❌ عذراً، لقد استخدمت هذا الزر مسبقاً! يجب الانتظار {rem_h} ساعة و {rem_m} دقيقة.")

        token = str(uuid.uuid4())
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        expires_at = current_time + 600

        cursor.execute("INSERT INTO secure_tokens (token, user_id, button_id, generated_code, expires_at) VALUES (?, ?, ?, ?, ?)", (token, user_id, int(btn_id), code, expires_at))
        conn.commit()

        session["already_claimed"] = True

        return render_template_string(HTML_TEMPLATE, code=code)

    session.pop("already_claimed", None)
    return render_template_string(HTML_TEMPLATE)

def run_flask(): app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 [FURY SYSTEM V4 - SECURE WEB] Running Successfully!")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
                                                                                                                        
