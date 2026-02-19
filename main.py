import sqlite3
import asyncio
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Render Environment Variables se Token uthane ke liye (Recommended)
# Agar direct daalna hai toh TOKEN = "8514085828:AAG8HnMFb616cNXChB3PLXQ8U3MPiZ2UgQE" likho
TOKEN = os.getenv("BOT_TOKEN", "8514085828:AAG8HnMFb616cNXChB3PLXQ8U3MPiZ2UgQE")
OWNER_ID = 7958364334 
CHANNEL_ID = -1003776286094

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, content TEXT, file_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS entries (user_id INTEGER, username TEXT, timestamp TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS blacklist (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, winners TEXT, participants INTEGER, date TEXT)")
conn.commit()

# ================= GIVEAWAY STATE =================
giveaway_active = False
winner_count = 0

# ================= COMMANDS =================
async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global giveaway_active, winner_count
    if update.effective_user.id != OWNER_ID: return

    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /announce your text")
        return

    giveaway_active = True
    winner_count = 2
    cursor.execute("DELETE FROM entries")
    conn.commit()

    await context.bot.send_message(CHANNEL_ID, text)
    await update.message.reply_text("Announcement sent ✅")
    asyncio.create_task(end_giveaway(context))

async def end_giveaway(context):
    global giveaway_active
    await asyncio.sleep(240) 

    cursor.execute("SELECT * FROM entries ORDER BY timestamp ASC")
    users = cursor.fetchall()
    winners = users[:winner_count]
    winner_names = []

    for user in winners:
        user_id, username = user[0], user[1]
        cursor.execute("SELECT * FROM rewards LIMIT 1")
        reward = cursor.fetchone()

        if reward:
            cursor.execute("DELETE FROM rewards WHERE id = ?", (reward[0],))
            conn.commit()
            if reward[1] == "text":
                await context.bot.send_message(user_id, reward[2])
            else:
                await context.bot.send_document(user_id, reward[3])
        winner_names.append(f"@{username}" if username else f"ID: {user_id}")

    winner_text = "\n".join(winner_names)
    await context.bot.send_message(CHANNEL_ID, f"🏆 WINNERS:\n{winner_text}")
    await context.bot.send_message(OWNER_ID, f"Giveaway Finished\nWinners:\n{winner_text}")

    cursor.execute("INSERT INTO history (winners, participants, date) VALUES (?, ?, ?)",
                   (winner_text, len(users), datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    giveaway_active = False

async def dm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not giveaway_active: return
    user = update.effective_user
    cursor.execute("SELECT * FROM blacklist WHERE user_id = ?", (user.id,))
    if cursor.fetchone(): return
    cursor.execute("SELECT * FROM entries WHERE user_id = ?", (user.id,))
    if cursor.fetchone(): return

    cursor.execute("INSERT INTO entries VALUES (?, ?, ?)", (user.id, user.username, datetime.now().isoformat()))
    conn.commit()
    await update.message.reply_text("✅ ENTRY RECORDED\nWAIT PATIENTLY\nWINNER WILL BE DECLARED IN FOUR MINUTES")

async def addreward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    await update.message.reply_text("Send reward text or file now.")

async def reward_receiver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if update.message.document:
        cursor.execute("INSERT INTO rewards (type, content, file_id) VALUES (?, ?, ?)", ("file", None, update.message.document.file_id))
    elif update.message.text:
        if update.message.text.startswith('/'): return # Commands skip karne ke liye
        cursor.execute("INSERT INTO rewards (type, content, file_id) VALUES (?, ?, ?)", ("text", update.message.text, None))
    conn.commit()
    await update.message.reply_text("Reward stored ✅")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    msg = "\n".join([f"{r[3]} | Winners: {r[1]} | Participants: {r[2]}" for r in rows])
    await update.message.reply_text(msg or "No history yet.")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(CommandHandler("addreward", addreward))
    app.add_handler(CommandHandler("history", history))
    # Naye version mein filters.Chat.PRIVATE use hota hai
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat.PRIVATE, dm_handler))
    app.add_handler(MessageHandler((filters.TEXT | filters.Document.ALL) & filters.Chat.PRIVATE, reward_receiver))

    print("Bot is running...")
    app.run_polling()
