import os
import random
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# Log sistemi
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
        "👋 **Salam! Mən Təkmilləşdirilmiş Oyun Botuyam.**\n\n"
        "🎮 Qruplarda rəqəm tapma yarışı keçirirəm.\n"
        "⚡️ **Sürət Bonusu:** İlk 10 saniyədə tapanlara +2 xal!\n"
        "🎁 **Şans Turu:** Hər 5 turdan bir +3 xal qazandıran xüsusi tur!\n"
        "🌍 `/top` yazaraq dünya sıralamasını görə bilərsiniz."
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **Oyun Komandaları:**\n"
        "• `/baslat` - 25 turluq rəqabəti başladır.\n"
        "• `/bitir` - Oyunu dayandırır.\n"
        "• `/siralama` - Qrupdakı cari xallar.\n"
        "• `/top` - Bütün dünyadakı ən yaxşı 10 oyunçu.\n\n"
        "💡 **Məlumat:** Rəqəmi tapan hər kəs +1 xal qazanır."
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
        "start_time": time.time(),
        "current_scores": {}
    }
    
    await update.message.reply_text(
        f"🎮 **Oyun Başladı! (Tur 1/25)**\n"
        f"🔢 Aralıq: **{s} - {e}**\n"
        f"⚡️ Sürətli olun, xal qazanın!"
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
        # Xal hesablama logic-i
        earned_points = 1
        bonus_msg = ""
        
        # ⚡ Sürət Bonusu (10 saniyə ərzində tapsa)
        if time.time() - game["start_time"] < 10:
            earned_points += 1
            bonus_msg += "⚡ **SÜRƏT BONUSU! (+1)** "

        # 🎁 Şans Turu (Hər 5-ci turda +2 əlavə xal, cəmi 3 xal)
        if game["turn"] % 5 == 0:
            earned_points += 2
            bonus_msg += "🎁 **ŞANS TURU BONUSU! (+2)**"

        # Xalları qeyd et
        uid_str = str(user_id)
        if uid_str not in game["current_scores"]:
            game["current_scores"][uid_str] = [user_name, 0]
        game["current_scores"][uid_str][1] += earned_points
        
        # MongoDB-də qlobal xalı yenilə
        scores_col.update_one(
            {"user_id": user_id}, 
            {"$inc": {"total_points": earned_points}, "$set": {"name": user_name}}, 
            upsert=True
        )

        if game["turn"] < 25:
            game["turn"] += 1
            s, e, t = get_random_range()
            game.update({"start_num": s, "end_num": e, "target": t, "start_time": time.time()})
            
            await update.message.reply_text(
                f"✅ Düzdür {user_name}! (+{earned_points} xal)\n{bonus_msg}\n\n"
                f"🏁 **Tur {game['turn']}/25 başladı.**\n"
                f"🔢 Yeni aralıq: **{s} - {e}**"
            )
        else:
            # Final Sıralama
            sorted_res = sorted(game["current_scores"].items(), key=lambda x: x[1][1], reverse=True)
            leaderboard = "🏆 **OYUN BİTDİ! YEKUN SIRALAMA:**\n\n"
            for i, (uid, data) in enumerate(sorted_res, 1):
                leaderboard += f"{i}. {data[0]} — {data[1]} xal\n"
            
            winner = sorted_res[0][1][0] if sorted_res else "Heç kim"
            leaderboard += f"\n🥇 **Mütləq Qalib:** {winner}"
            
            await update.message.reply_text(leaderboard, parse_mode="Markdown")
            del active_games[chat_id]

async def top_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # MongoDB-dən ilk 10 oyunçunu çək
    top_players = scores_col.find().sort("total_points", -1).limit(10)
    
    res = "🌍 **Qlobal Top 10 Oyunçu:**\n\n"
    for i, player in enumerate(top_players, 1):
        name = player.get("name", "İstifadəçi")
        points = player.get("total_points", 0)
        res += f"{i}. {name} — {points} xal\n"
    
    await update.message.reply_text(res, parse_mode="Markdown")

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
    if not TOKEN or not MONGO_URL:
        print("Xəta: BOT_TOKEN və ya MONGO_URL tapılmadı!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("bitir", bitir))
    app.add_handler(CommandHandler("siralama", siralama))
    app.add_handler(CommandHandler("top", top_global))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, guess))
    
    print("Bot işə düşdü...")
    app.run_polling()

if __name__ == '__main__':
    main()
