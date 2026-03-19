import os
import random
import logging
import time
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "kullaniciadidi")

client = MongoClient(MONGO_URL)
db = client['game_bot_db']
scores_col = db['scores']

active_games = {}

async def set_bot_commands(application: Application):
    commands = [
        BotCommand("start", "Botu başladın və menyunu görün"),
        BotCommand("baslat", "Yeni 25 turluq oyun başladın"),
        BotCommand("siralama", "Qrupdakı cari xalları görün"),
        BotCommand("reqemtop", "Qlobal (Dünya) sıralamanı görün"),
        BotCommand("help", "Oyun qaydaları haqqında məlumat"),
        BotCommand("bitir", "Aktiv oyunu dayandırın")
    ]
    await application.bot.set_my_commands(commands)

def get_random_range():
    start_num = random.randint(1, 500)
    end_num = start_num + random.randint(50, 1000)
    target = random.randint(start_num, end_num)
    
    bomb_num = target
    while bomb_num == target:
        bomb_num = random.randint(start_num, end_num)
        
    return start_num, end_num, target, bomb_num

def get_start_keyboard(bot_username):
    keyboard = [
        [InlineKeyboardButton("➕ Məni Qrupa Əlavə Et", url=f"https://t.me/{bot_username}?startgroup=true")],
        [
            InlineKeyboardButton("ℹ️ Kömək", callback_data='help_menu'),
            InlineKeyboardButton("👨‍💻 Sahib", url=f"https://t.me/{OWNER_USERNAME}")
        ],
        [InlineKeyboardButton("📢 Kanalımız", url="https://t.me/ht_bots")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_obj = await context.bot.get_me()
    text = (
        "👋 Salam! Mən Təkmilləşdirilmiş Oyun Botuyam.\n\n"
        "🎮 Qruplarda rəqəm tapma yarışı keçirirəm.\n"
        "⚡️ Sürət Bonusu: İlk 10 saniyədə tapanlara +2 xal!\n"
        "🎁 Şans Turu: Hər 5 turdan bir +3 xal qazandıran xüsusi tur!\n"
        "🌍 /reqemtop yazaraq dünya sıralamasını görə bilərsiniz."
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=get_start_keyboard(bot_obj.username), parse_mode=None)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=get_start_keyboard(bot_obj.username), parse_mode=None)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_obj = await context.bot.get_me()

    if query.data == 'help_menu':
        help_text = (
            "📖 Oyun Komandaları və İzahlar:\n\n"
            "• /baslat - 25 turluq rəqabəti başladır.\n"
            "• /bitir - Aktiv oyunu dayandırır.\n"
            "• /siralama - Qrupdakı cari xalları göstərir.\n"
            "• /reqemtop - Bütün dünyadakı TOP 10 siyahısı.\n"
            "• /help - Bu menyunu açır.\n\n"
            "💡 Qaydalar: Rəqəmi tapan +1 xal qazanır. Sürətli tapanlara və şans turlarına (hər 5 turdan bir) bonus xallar verilir!"
        )
        keyboard = [[InlineKeyboardButton("⬅️ Geri", callback_data='back_to_start')]]
        await query.edit_message_text(text=help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=None)
    
    elif query.data == 'back_to_start':
        text = (
            "👋 Salam! Mən Təkmilləşdirilmiş Oyun Botuyam.\n\n"
            "🎮 Qruplarda rəqəm tapma yarışı keçirirəm.\n"
            "🌍 /reqemtop yazaraq dünya sıralamasını görə bilərsiniz."
        )
        await query.edit_message_text(text=text, reply_markup=get_start_keyboard(bot_obj.username), parse_mode=None)

async def baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text("❌ Bu oyun yalnız qruplarda işləyir!")

    if chat_id in active_games:
        return await update.message.reply_text("⚠️ Artıq davam edən bir oyun var!")

    s, e, t, b = get_random_range()
    active_games[chat_id] = {
        "start_num": s, "end_num": e, "target": t, "bomb_num": b,
        "turn": 1, "start_time": time.time(), "current_scores": {}
    }
    await update.message.reply_text(f"🎮 Oyun Başladı! (Tur 1/25)\n🔢 Aralıq: {s} - {e}")

def create_leaderboard_image(scores_data):
    width, height = 600, 800
    image = Image.new('RGB', (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(image)

    font_title = ImageFont.load_default()
    font_text = ImageFont.load_default()

    draw.text((width // 2, 50), "🏆 OYUN BİTDİ!", fill=(255, 215, 0), font=font_title, anchor="ms")
    draw.text((width // 2, 100), "Yekun Sıralama", fill=(255, 255, 255), font=font_title, anchor="ms")
    
    y_offset = 180
    sorted_res = sorted(scores_data.items(), key=lambda x: x[1][1], reverse=True)
    
    for i, (uid, data) in enumerate(sorted_res, 1):
        if i > 15: break
        
        text_color = (255, 255, 255)
        if i == 1: text_color = (255, 215, 0)
        elif i == 2: text_color = (192, 192, 192)
        elif i == 3: text_color = (205, 127, 50)
            
        text = f"{i}. {data[0]} — {data[1]} xal"
        draw.text((100, y_offset), text, fill=text_color, font=font_text)
        y_offset += 40

    winner = sorted_res[0][1][0] if sorted_res else "Heç kim"
    draw.text((width // 2, 700), f"🥇 Mütləq Qalib: {winner}", fill=(255, 215, 0), font=font_title, anchor="ms")

    draw.text((width // 2, 760), "@ht_bots", fill=(100, 100, 100), font=font_text, anchor="ms")

    img_io = BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games or not update.message.text.isdigit():
        return

    user_guess = int(update.message.text)
    game = active_games[chat_id]
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if user_guess == game["bomb_num"]:
        earned_points = -1
        bonus_msg = f"💥 BOMMm minaya basdın😕! {user_name} (-1 Xal)!"
        
        uid_str = str(user_id)
        if uid_str not in game["current_scores"]:
            game["current_scores"][uid_str] = [user_name, 0]
        game["current_scores"][uid_str][1] += earned_points
        scores_col.update_one({"user_id": user_id}, {"$inc": {"total_points": earned_points}, "$set": {"name": user_name}}, upsert=True)
        
        await update.message.reply_text(bonus_msg, parse_mode=None)
        return

    if user_guess < game["target"]:
        await update.message.reply_text(f"🔼 Daha böyük rəqəm daxil edin")
    elif user_guess > game["target"]:
        await update.message.reply_text(f"🔽 Daha kiçik rəqəm daxil edin")
    else:
        earned_points = 1
        bonus_msg = ""
        if time.time() - game["start_time"] < 10:
            earned_points += 1
            bonus_msg += "⚡ SÜRƏT BONUSU! (+1) "
        if game["turn"] % 5 == 0:
            earned_points += 2
            bonus_msg += "🎁 ŞANS TURU BONUSU! (+2)"

        uid_str = str(user_id)
        if uid_str not in game["current_scores"]:
            game["current_scores"][uid_str] = [user_name, 0]
        game["current_scores"][uid_str][1] += earned_points
        
        scores_col.update_one({"user_id": user_id}, {"$inc": {"total_points": earned_points}, "$set": {"name": user_name}}, upsert=True)

        if game["turn"] < 25:
            game["turn"] += 1
            s, e, t, b = get_random_range()
            game.update({"start_num": s, "end_num": e, "target": t, "bomb_num": b, "start_time": time.time()})
            await update.message.reply_text(f"✅ Düzdür {user_name}! (+{earned_points} xal)\n{bonus_msg}\n\n🏁 Tur {game['turn']}/25 başladı.\n🔢 Yeni aralıq: {s} - {e}")
        else:
            await update.message.reply_text("🏆 Oyun Bitdi! Yekun sıralama hazırlanır...", parse_mode=None)
            
            try:
                leaderboard_image = create_leaderboard_image(game["current_scores"])
                await context.bot.send_photo(chat_id=chat_id, photo=InputFile(leaderboard_image, filename="leaderboard.png"), caption="@ht_bots Qaliblər!")
            except Exception as e:
                logging.error(f"Vizual kart xətası: {e}")
                
            sorted_res = sorted(game["current_scores"].items(), key=lambda x: x[1][1], reverse=True)
            leaderboard_text = "🏆 OYUN BİTDİ! YEKUN SIRALAMA:\n\n"
            for i, (uid, data) in enumerate(sorted_res, 1):
                leaderboard_text += f"{i}. {data[0]} — {data[1]} xal\n"
            winner = sorted_res[0][1][0] if sorted_res else "Heç kim"
            leaderboard_text += f"\n🥇 Mütləq Qalib: {winner}"
            await update.message.reply_text(leaderboard_text, parse_mode=None)

            del active_games[chat_id]

async def top_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_players = scores_col.find().sort("total_points", -1).limit(10)
    res = "🌍 Qlobal Top 10 Oyunçu:\n\n"
    for i, player in enumerate(top_players, 1):
        res += f"{i}. {player.get('name', 'İstifadəçi')} — {player.get('total_points', 0)} xal\n"
    await update.message.reply_text(res, parse_mode=None)

async def siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games:
        return await update.message.reply_text("❌ Hazırda aktiv oyun yoxdur.")
    game = active_games[chat_id]
    sorted_res = sorted(game["current_scores"].items(), key=lambda x: x[1][1], reverse=True)
    res = f"📊 Cari Sıralama (Tur {game['turn']}/25):\n\n"
    for i, (uid, data) in enumerate(sorted_res, 1):
        res += f"{i}. {data[0]} — {data[1]} xal\n"
    await update.message.reply_text(res, parse_mode=None)

async def bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in active_games:
        del active_games[update.effective_chat.id]
        await update.message.reply_text("🛑 Oyun dayandırıldı.")

async def on_new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                await start(update, context)

def main():
    if not TOKEN or not MONGO_URL: return
    app = Application.builder().token(TOKEN).build()
    app.post_init = set_bot_commands

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("bitir", bitir))
    app.add_handler(CommandHandler("siralama", siralama))
    app.add_handler(CommandHandler("reqemtop", top_global))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, guess))
    
    app.run_polling()

if __name__ == '__main__': main()
