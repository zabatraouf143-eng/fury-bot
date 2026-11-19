import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

# إعداد الـ Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# هيكل بيانات اللعبة
game_data = {
    "status": "waiting",  # waiting, prison, active
    "players": {},        # chat_id -> {name, money, room, door_hp, door_max_hp, door_level, has_gun}
    "monster": {
        "target_room": None,
        "hp": 500,
        "max_hp": 500,
        "is_charging": False,
        "action": "يبحث عن ضحية..."
    }
}

TOKEN = "8638452052:AAGz5E-bd3GBY47R-zM5rTmw8uCq9BpPrXc"

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if game_data["status"] != "waiting":
        await update.message.reply_text("⚠️ اللعبة جارية بالفعل حالياً! انتظر حتى تنتهي الجولة.")
        return

    if user_id not in game_data["players"]:
        game_data["players"][user_id] = {
            "name": user.first_name,
            "money": 10,       # تبدأ بـ 10 نقود أولية
            "room": None,
            "door_hp": 100,
            "door_max_hp": 100,
            "door_level": 1,
            "has_gun": False
        }
        await update.message.reply_text(f"✅ {user.first_name} انضم للعبة! (عدد اللاعبين: {len(game_data['players'])}/4)")
    
    if len(game_data["players"]) == 4:
        game_data["status"] = "prison"
        await update.message.reply_text("🚨 اكتمل عدد اللاعبين (4 أشخاص)! تبدأ الرحلة في السجن...")
        asyncio.create_task(start_prison_countdown(context, update.effective_chat.id))
    else:
        keyboard = [[InlineKeyboardButton("انضم للعبة 🎮", callback_data="join")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🏰 **لعبة الحصار (Dorm Hunted)**\nاضغط للانضمام للعبة:", reply_markup=reply_markup)

async def start_prison_countdown(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    message = await context.bot.send_message(chat_id, "🔒 أنتم الآن محبوسون جماعياً في السجن...\nالعداد التنازلي: **10** ثوانٍ لفتح الأبواب!")
    
    for i in range(10, 0, -1):
        await asyncio.sleep(1)
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.message_id,
                text=f"🔒 السجن جماعي...\nالعداد التنازلي: **{i}** ثوانٍ ⏳",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    game_data["status"] = "active"
    
    # توزيع اللاعبين وإظهار خيار اختيار الغرف
    keyboard = [
        [InlineKeyboardButton("🚪 الغرفة 1", callback_data="room_1"), InlineKeyboardButton("🚪 الغرفة 2", callback_data="room_2")],
        [InlineKeyboardButton("🚪 الغرفة 3", callback_data="room_3"), InlineKeyboardButton("🚪 الغرفة 4", callback_data="room_4")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id, "🟢 **انفتح باب السجن!** اخرجوا بسرعة، اختر غرفتك للنوم وجني النقود قبل أن يصل الوحش:", reply_markup=reply_markup)
    
    # بدء حلقة هجمات الوحش وجمع الأموال في الخلفية
    asyncio.create_task(game_loop(context, chat_id))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "join":
        if user_id not in game_data["players"] and game_data["status"] == "waiting":
            game_data["players"][user_id] = {
                "name": query.from_user.first_name,
                "money": 10,
                "room": None,
                "door_hp": 100,
                "door_max_hp": 100,
                "door_level": 1,
                "has_gun": False
            }
            await query.edit_message_text(f"✅ انضممت بنجاح! اللاعبون حالياً: {len(game_data['players'])}/4")
            if len(game_data["players"]) == 4:
                game_data["status"] = "prison"
                await context.bot.send_message(query.message.chat_id, "🚨 اكتمل العدد! تبدأ اللعبة في السجن...")
                asyncio.create_task(start_prison_countdown(context, query.message.chat_id))
        else:
            await query.answer("لا يمكنك الانضمام الآن!", show_alert=True)
            
    elif data.startswith("room_"):
        room_num = int(data.split("_")[1])
        if user_id in game_data["players"]:
            game_data["players"][user_id]["room"] = room_num
            
            # لوحة تحكم الغرفة الخاصة باللاعب
            keyboard = [
                [InlineKeyboardButton("🛏️ تطوير السرير (+5 ذهب/ث)", callback_data="upgrade_bed"), InlineKeyboardButton("🚪 تطوير الباب (50 ذهب)", callback_data="upgrade_door")],
                [InlineKeyboardButton("🔫 شراء رشاش دفاعي (100 ذهب)", callback_data="buy_gun")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🛏️ اخترت الغرفة رقم {room_num}!\n"
                f"💰 النقود: 10 | 🚪 صحة الباب: 100/100 (مستوى 1)\n"
                f"💤 أنت تنام الآن وتجمع النقود تدريجياً...",
                reply_markup=reply_markup
            )

    elif data == "upgrade_door":
        p = game_data["players"].get(user_id)
        if p and p["money"] >= 50:
            p["money"] -= 50
            p["door_level"] += 1
            p["door_max_hp"] += 100
            p["door_hp"] = p["door_max_hp"] # تصليح كامل عند التطوير
            await query.answer("✅ تم تطوير الباب بنجاح وزيادة صلابته!", show_alert=True)
        else:
            await query.answer("❌ لا تملك نقوداً كافية (تحتاج 50 ذهب)!", show_alert=True)

    elif data == "buy_gun":
        p = game_data["players"].get(user_id)
        if p and not p["has_gun"] and p["money"] >= 100:
            p["money"] -= 100
            p["has_gun"] = True
            await query.answer("🔫 اشتريت رشاشاً دفاعياً لإطلاق النار على الوحش تلقائياً!", show_alert=True)
        elif p and p["has_gun"]:
            await query.answer("⚠️ لديك رشاش بالفعل!", show_alert=True)
        else:
            await query.answer("❌ لا تملك نقوداً كافية (تحتاج 100 ذهب)!", show_alert=True)

async def game_loop(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    import random
    
    while game_data["status"] == "active":
        await asyncio.sleep(4) # كل 4 ثوانٍ دورة جديدة في اللعبة
        
        # 1. تجميع النقود تلقائياً للنائمين في غرفهم
        for uid, p in game_data["players"].items():
            if p["room"] is not None:
                p["money"] += 15 # دخل النوم
                
        # 2. اختيار ضحية عشوائية للوحش أو متابعة الهجوم
        active_players = [uid for uid, p in game_data["players"].items() if p["room"] is not None and p["door_hp"] > 0]
        if not active_players:
            await context.bot.send_message(chat_id, "💀 انتهت اللعبة! الوحش افترس الجميع ولم تبقَ أي غرفة آمنة.")
            game_data["status"] = "ended"
            break
            
        target_uid = random.choice(active_players)
        target_player = game_data["players"][target_uid]
        
        # 3. شحن طاقة الوحش (Monster Charging) وهجومه
        game_data["monster"]["is_charging"] = True
        game_data["monster"]["action"] = f"الوحش يشحن طاقته لمهاجمة غرفة {target_player['name']}! ⚡"
        
        # إرسال تنبيه بالهجوم القادم
        status_msg = (
            f"⚠️ **حالة الوحش واللعبة:**\n"
            f"👹 الوحش HP: {game_data['monster']['hp']}/{game_data['monster']['max_hp']} | {game_data['monster']['action']}\n\n"
            f"🚪 **حالة غرفة اللاعب {target_player['name']}:**\n"
            f"صحة الباب: `{target_player['door_hp']}/{target_player['door_max_hp']}` (مستوى {target_player['door_level']})\n"
            f"💰 نقوده: {target_player['money']} | 🔫 سلاح دفاعي: {'نعم' if target_player['has_gun'] else 'لا'}"
        )
        await context.bot.send_message(chat_id, status_msg, parse_mode="Markdown")
        
        await asyncio.sleep(2) # انتظار ضربة الوحش
        
        # إذا كان اللاعب يملك رشاشاً، يطلق النار على الوحش وينقص دمو
        damage_to_monster = 30 if target_player["has_gun"] else 0
        if damage_to_monster > 0:
            game_data["monster"]["hp"] -= damage_to_monster
            if game_data["monster"]["hp"] < 0:
                game_data["monster"]["hp"] = 0

        # الوحش يضرب الباب
        damage_to_door = 40
        target_player["door_hp"] -= damage_to_door
        
        if target_player["door_hp"] <= 0:
            target_player["door_hp"] = 0
            target_player["room"] = None # تحطمت الغرفة!
            await context.bot.send_message(chat_id, f"💥 **تكسر باب غرفة {target_player['name']} بالكامل!** الوحش دخل وافترسه! 💀")
        
        # فوز اللاعبين إذا مات الوحش
        if game_data["monster"]["hp"] <= 0:
            await context.bot.send_message(chat_id, "🏆 **لقد قضى اللاعبون على الوحش تماماً! فاز الناجون في هذه الجولة! 🎉**")
            game_data["status"] = "ended"
            break

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_game))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 البوت يعمل بكامل الإبداع والجاهزية...")
    app.run_polling()

if __name__ == "__main__":
    main()
  
