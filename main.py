import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = "8514085828:AAG8HnMFb616cNXChB3PLXQ8U3MPiZ2UgQE"
OWNER_ID =  7958364334 # apna telegram user id daal
CHANNEL_ID =  -1003776286094 # apna channel id daal

# ================= DATABASE =================

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    content TEXT,
    file_id TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS entries (
    user_id INTEGER,
    username TEXT,
    timestamp TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    winners TEXT,
    participants INTEGER,
    date TEXT
)
""")

conn.commit()

# ================= GIVEAWAY STATE =================

giveaway_active = False
winner_count = 0

# ================= COMMANDS =================

async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global giveaway_active, winner_count

    if update.effective_user.id != OWNER_ID:
        return

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

    await asyncio.sleep(240)  # 4 minutes

    cursor.execute("SELECT * FROM entries ORDER BY timestamp ASC")
    users = cursor.fetchall()

    winners = users[:winner_count]

    winner_names = []

    for user in winners:
        user_id = user[0]
        username = user[1]

        cursor.execute("SELECT * FROM rewards LIMIT 1")
        reward = cursor.fetchone()

        if reward:
            cursor.execute("DELETE FROM rewards WHERE id = ?", (reward[0],))
            conn.commit()

            if reward[1] == "text":
                await context.bot.send_message(user_id, reward[2])
            else:
                await context.bot.send_document(user_id, reward[3])

        winner_names.append(f"@{username}")

    await context.bot.send_message(
        CHANNEL_ID,
        f"🏆 WINNERS:\n" + "\n".join(winner_names)
    )

    await context.bot.send_message(
        OWNER_ID,
        f"Giveaway Finished\nWinners:\n" + "\n".join(winner_names)
    )

    cursor.execute(
        "INSERT INTO history (winners, participants, date) VALUES (?, ?, ?)",
        (",".join(winner_names), len(users), datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()

    giveaway_active = False


async def dm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global giveaway_active

    if not giveaway_active:
        return

    user = update.effective_user

    cursor.execute("SELECT * FROM blacklist WHERE user_id = ?", (user.id,))
    if cursor.fetchone():
        return

    cursor.execute("SELECT * FROM entries WHERE user_id = ?", (user.id,))
    if cursor.fetchone():
        return

    cursor.execute(
        "INSERT INTO entries VALUES (?, ?, ?)",
        (user.id, user.username, datetime.now().isoformat())
    )
    conn.commit()

    await update.message.reply_text(
        "✅ ENTRY RECORDED\nWAIT PATIENTLY\nWINNER WILL BE DECLARED IN FOUR MINUTES\nANY PROBLEM DM @proxyfxc"
    )


async def addreward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    await update.message.reply_text("Send reward text or file now.")


async def reward_receiver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if update.message.document:
        file_id = update.message.document.file_id
        cursor.execute(
            "INSERT INTO rewards (type, content, file_id) VALUES (?, ?, ?)",
            ("file", None, file_id)
        )
    else:
        cursor.execute(
            "INSERT INTO rewards (type, content, file_id) VALUES (?, ?, ?)",
            ("text", update.message.text, None)
        )

    conn.commit()
    await update.message.reply_text("Reward stored ✅")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()

    msg = ""
    for row in rows:
        msg += f"{row[3]} | Winners: {row[1]} | Participants: {row[2]}\n"

    await update.message.reply_text(msg or "No history yet.")


# ================= MAIN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("announce", announce))
app.add_handler(CommandHandler("addreward", addreward))
app.add_handler(CommandHandler("history", history))
app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, dm_handler))
app.add_handler(MessageHandler(filters.ALL & filters.ChatType.PRIVATE, reward_receiver))

app.run_polling()
