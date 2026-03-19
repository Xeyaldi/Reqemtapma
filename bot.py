import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# Loglar
logging.basicConfig(level=logging.INFO)

# Heroku Config Vars (Environment Variables)
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "kullaniciadidi")

# MongoDB Bağlantısı
client = MongoClient(MONGO_URL)
db = client['game_bot_db']
scores_col = db['scores']

active_games = {}

def get_random_range():
    """Hər tur üçün təsadüfi bir rəqəm aralığı yaradır"""
    start_num = random.randint(1, 500)
    # Aralıq ən az 50 rəqəm fərqi olsun deyə +50 əlavə edirik
    end_num = start_num + random.randint(50, 1000)
    target = random.randint(start_num, end_num)
    return start_num, end_num, target

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_obj = await context.bot.get_me()
    keyboard = [
        [InlineKeyboardButton("➕ Məni Qrupa Əlavə Et", url=f"https://t.me/{bot_obj.username}?startgroup=true")],
        [
            InlineKeyboardButton("ℹ️ Kömək", callback_data='help'),
            InlineKeyboardButton("👨‍💻 Sahib", url=f"https://t.me/{OWNER_USERNAME}")
        ],
        [InlineKeyboardButton("📢 Kanalımız", url="https://t.me/ht_bots")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "👋 **Salam! Mən Dinamik Rəqəm Tapma Botuyam.**\n\n"
        "🎮 Hər turda fərqli rəqəm aralıqları təyin edirəm.\n"
        "🏆 25 tur sonunda ən çox xal toplayan qalib olur!\n"
        "📈 Xallarınız həm də ümumi bazada yadda qalır."
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **Oyun Qaydaları:**\n"
        "• `/baslat` - Oyunu başladır (25 tur).\n"
        "• `/bitir` - Aktiv oyunu dayandırır.\n"
        "• `/siralama` - Bu qrupdakı cari xalları göstərir.\n\n"
        "💡 Hər düzgün cavab üçün **+1 xal** verilir."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text("❌ Bu oyun yalnız qruplarda işləyir!")

    if chat_id in active_games:
        return await update.message.reply_text("⚠️ Artıq davam edən bir oyun var!")

    s, e, t = get_random_range()
    active_games[chat_id] = {
        "start_num": s,
        "end_num": e,
        "target": t,
        "turn": 1,
        "current_scores": {}
    }
    
    await update.message.reply_text(
        f"🎮 **Oyun Başladı! (Tur 1/25)**\n"
        f"🔢 Aralıq: **{s} - {e}** arası.\n"
        f"Tapın görək!"
    )

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games or not update.message.text.isdigit():
        return

    user_guess = int(update.message.text)
    game = active_games[chat_id]
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if user_guess < game["target"]:
        await update.message.reply_text(f"🔼 {user_guess} - Daha YUXARI!")
    elif user_guess > game["target"]:
        await update.message.reply_text(f"🔽 {user_guess} - Daha AŞAĞI!")
    else:
        # Xal sistemini yenilə (+1 xal)
        uid_str = str(user_id)
        if uid_str not in game["current_scores"]:
            game["current_scores"][uid_str] = [user_name, 0]
        game["current_scores"][uid_str][1] += 1
        
        # MongoDB Update
        scores_col.update_one(
            {"user_id": user_id}, 
            {"$inc": {"total_points": 1}, "$set": {"name": user_name}}, 
            upsert=True
        )

        if game["turn"] < 25:
            game["turn"] += 1
            s, e, t = get_random_range()
            game["start_num"], game["end_num"], game["target"] = s, e, t
            
            await update.message.reply_text(
                f"✅ Düzdür {user_name}! (+1 Xal)\n\n"
                f"🏁 **Tur {game['turn']}/25 başladı.**\n"
                f"🔢 Yeni aralıq: **{s} - {e}**\n"
                f"Tapın!"
            )
        else:
            # Final Sıralama
            sorted_res = sorted(game["current_scores"].items(), key=lambda x: x[1][1], reverse=True)
            leaderboard = "🏆 **OYUN BİTDİ! YEKUN SIRALAMA:**\n\n"
            for i, (uid, data) in enumerate(sorted_res, 1):
                leaderboard += f"{i}. {data[0]} — {data[1]} xal\n"
            
            winner = sorted_res[0][1][0] if sorted_res else "Heç kim"
            leaderboard += f"\n🥇 **Qalib:** {winner}"
            
            await update.message.reply_text(leaderboard, parse_mode="Markdown")
            del active_games[chat_id]

async def siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games:
        return await update.message.reply_text("❌ Hazırda aktiv oyun yoxdur.")
    
    game = active_games[chat_id]
    sorted_res = sorted(game["current_scores"].items(), key=lambda x: x[1][1], reverse=True)
    res = f"📊 **Cari Sıralama (Tur {game['turn']}/25):**\n\n"
    for i, (uid, data) in enumerate(sorted_res, 1):
        res += f"{i}. {data[0]} — {data[1]} xal\n"
    
    await update.message.reply_text(res, parse_mode="Markdown")

async def bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_games:
        del active_games[chat_id]
        await update.message.reply_text("🛑 Oyun dayandırıldı.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("bitir", bitir))
    app.add_handler(CommandHandler("siralama", siralama))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, guess))
    app.run_polling()

if __name__ == '__main__':
    main()
