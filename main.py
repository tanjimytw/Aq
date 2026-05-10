import random
import string
import time
import hashlib
import hmac
import base64
import struct
import telebot
from telebot import types
import sqlite3
from datetime import datetime
from flask import Flask
from threading import Thread

# ================= CONFIG =================
# আপনার দেওয়া টোকেন এবং আইডি এখানে সেট করা হয়েছে
TOKEN = "8619212784:AAGNRWitsKF5EScwGnTvhUMAzatrGjj2Glo"
ADMIN_ID = 8061525743
CHANNEL_USERNAME = "@DailyReportUpdate" 
SUPPORT_ID = "@Tanjim_admin_support"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask('')

# রেন্ডার এ বট সচল রাখার জন্য হেলথ চেক রুট
@app.route('/')
def home():
    return "Bot is active and running!"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        invites INTEGER DEFAULT 0,
        referral_earnings REAL DEFAULT 0,
        joined_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_username TEXT,
        fa_secret TEXT,
        status TEXT DEFAULT 'Pending'
    )""")
    conn.commit()
    conn.close()

init_db()

# ================= HELPERS =================
def generate_username():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=6)) + "acc"

def get_totp_code(secret):
    try:
        clean_sec = ''.join(c for c in secret if c.isalnum()).upper()
        key = base64.b32decode(clean_sec + '=' * ((8 - len(clean_sec) % 8) % 8))
        counter = struct.pack('>Q', int(time.time() // 30))
        hmac_hash = hmac.new(key, counter, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        code = (struct.unpack('>I', hmac_hash[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
        return f"{code:06d}"
    except:
        return "Invalid"

# ================= KEYBOARDS =================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📋 কাজ", "💰 ব্যালেন্স")
    markup.add("🏦 টাকা উতোলন", "🏆 লিডারবোর্ড", "📞 সাপোর্ট")
    return markup

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 স্ট্যাটাস", "📜 উইথড্র হিস্টরি", "📢 নোটিশ")
    return markup

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    uname = message.from_user.username or "User"
    
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, joined_at) VALUES (?,?,?)", 
                (user_id, uname, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 <b>এডমিন মোড সক্রিয়!</b>", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, f"👋 স্বাগতম {uname}!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "📋 কাজ")
def task_select(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💠 ইন্সটাগ্রাম 2FA (৳3.10)", callback_data="start_ig"))
    bot.send_message(message.chat.id, "কাজটি সম্পন্ন করতে নিচের বাটনে ক্লিক করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "start_ig")
def start_ig(call):
    u_name = generate_username()
    text = f"👤 <b>Username:</b> <code>{u_name}</code>\n🔓 <b>Password:</b> <code>Tanjim@2026</code>\n\nউপরে দেওয়া তথ্য দিয়ে আইডি লগইন করে 2FA কোড জেনারেট করার জন্য <b>Secret Key</b> এখানে লিখে পাঠান।"
    msg = bot.send_message(call.message.chat.id, text)
    bot.register_next_step_handler(msg, save_task, u_name)

def save_task(message, u_name):
    secret = message.text.strip()
    user_id = message.from_user.id
    otp = get_totp_code(secret)

    if otp == "Invalid":
        return bot.send_message(message.chat.id, "❌ ভুল সিক্রেট কী! আবার চেষ্টা করুন।")

    # এডমিনকে টাস্ক পাঠানো
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"appr_{user_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reje_{user_id}")
    )

    bot.send_message(ADMIN_ID, f"🆕 <b>নতুন সাবমিশন!</b>\n\nID: <code>{user_id}</code>\nUser: @{message.from_user.username}\nSecret: <code>{secret}</code>\nOTP: <code>{otp}</code>", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ আপনার টাস্ক জমা হয়েছে। এডমিন চেক করার পর ব্যালেন্স যোগ হবে।")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("appr_", "reje_")))
def admin_action(call):
    action, uid = call.data.split("_")
    if action == "appr":
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = balance + 3.10 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        bot.send_message(uid, "✅ আপনার টাস্ক অ্যাপ্রুভ হয়েছে! ৩.১০ টাকা ব্যালেন্সে যোগ করা হয়েছে।")
        bot.edit_message_text("টাস্কটি অ্যাপ্রুভ করা হয়েছে। ✅", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(uid, "❌ আপনার টাস্কটি রিজেক্ট করা হয়েছে। সঠিক তথ্য দিয়ে আবার চেষ্টা করুন।")
        bot.edit_message_text("টাস্কটি রিজেক্ট করা হয়েছে। ❌", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "💰 ব্যালেন্স")
def balance_check(message):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
    res = cur.fetchone()
    conn.close()
    bal = res[0] if res else 0
    bot.send_message(message.chat.id, f"💰 আপনার বর্তমান ব্যালেন্স: <b>৳{bal:.2f}</b>")

@bot.message_handler(func=lambda m: m.text == "📞 সাপোর্ট")
def support_info(message):
    bot.send_message(message.chat.id, f"🛠 যেকোনো সাহায্যের জন্য যোগাযোগ করুন:\n{SUPPORT_ID}")

# ================= DEPLOYMENT =================
def run():
    run_web_server()

if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    print("Bot is starting...")
    bot.infinity_polling()

