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
TOKEN = "8619212784:AAGNRWitsKF5EScwGnTvhUMAzatrGjj2Glo"
ADMIN_ID = 8061525743
CHANNEL_USERNAME = "@ws_vip_season_"
SUPPORT_ID = "@FB_SALL_AD"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
server = Flask('')

@server.route('/')
def home():
    return "Bot is Alive!"

def run_web():
    server.run(host='0.0.0.0', port=8080)

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
        referrer_id INTEGER,
        joined_at TEXT,
        last_task_date TEXT
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_username TEXT,
        password TEXT,
        fa_secret TEXT,
        timestamp TEXT
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        nagad_number TEXT,
        amount REAL,
        status TEXT DEFAULT 'Pending',
        timestamp TEXT
    )""")
    
    conn.commit()
    conn.close()

init_db()

# ================= HELPERS =================
def generate_username():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=6)) + ''.join(random.choices(string.ascii_lowercase, k=8))

def clean_secret(secret):
    return ''.join(c for c in secret if c.isalnum()).upper()

def get_totp_code(secret):
    try:
        clean_sec = clean_secret(secret)
        key = base64.b32decode(clean_sec + '=' * ((8 - len(clean_sec) % 8) % 8))
        counter = struct.pack('>Q', int(time.time() // 30))
        hmac_hash = hmac.new(key, counter, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        code = (struct.unpack('>I', hmac_hash[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
        return f"{code:06d}"
    except:
        return "❌ Invalid Secret Key"

def is_joined(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return True # টেস্ট করার জন্য ট্রু রাখা হয়েছে

def get_referral_link(user_id):
    return f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"

# ================= MENUS =================
def menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📋 কাজ", "💰 ব্যালেন্স")
    markup.add("🏦 টাকা উতোলন", "🏆 লিডারবোর্ড")
    markup.add("🎁 Invite & Earn", "📞 সাপোর্ট")
    return markup

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 চেক স্ট্যাটাস", "👥 রেফার")
    markup.add("📜 উইথড্র হিস্টরি", "📢 নোটিশ")
    return markup

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    referrer_id = None

    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith("ref_"):
            try:
                referrer_id = int(param[4:])
                if referrer_id == user_id: referrer_id = None
            except: referrer_id = None

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, referrer_id, joined_at) VALUES (?,?,?,?)", 
                (user_id, username, referrer_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 Welcome Admin", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, f"👋 Welcome {username}", reply_markup=menu())

# ================= USER LOGIC =================
@bot.message_handler(func=lambda m: m.text == "📋 কাজ")
def task_handler(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💠 ইন্সটাগ্রাম 2FA (৳2.10)", callback_data="ig_2fa"))
    bot.send_message(message.chat.id, "⚡️ যেকোনো একটি কাজ সিলেক্ট করুন⏬", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "ig_2fa")
def ig_2fa(call):
    username = generate_username()
    text = f"👤 <b>Username:</b> <code>{username}</code>\n🔓 <b>Password:</b> <code>omor1212</code>\n\n2FA Enable করে Secret Key পাঠান।"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔐 2FA Secret Key আছে", callback_data=f"has2fa_{username}"))
    bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("has2fa_"))
def ask_secret(call):
    username = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, "🔑 2FA Secret Key পেস্ট করুন:")
    bot.register_next_step_handler(msg, process_secret, username)

def process_secret(message, username):
    secret = message.text.strip()
    user_id = message.from_user.id
    otp = get_totp_code(secret)

    if "Invalid" in otp:
        return bot.send_message(message.chat.id, otp)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
    )

    bot.send_message(ADMIN_ID, f"🆕 নতুন টাস্ক\nID: <code>{user_id}</code>\nUser: @{message.from_user.username}\nSecret: <code>{secret}</code>\nOTP: <code>{otp}</code>", reply_markup=markup)
    bot.send_message(message.chat.id, f"✅ সাবমিট হয়েছে। Current Code: <code>{otp}</code>")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def admin_decision(call):
    action, uid = call.data.split("_")
    if action == "approve":
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = balance + 2.10 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        bot.send_message(uid, "✅ আপনার টাস্কটি অ্যাপ্রুভ হয়েছে! ২.১০৳ যোগ করা হয়েছে।")
    else:
        bot.send_message(uid, "❌ আপনার টাস্কটি বাতিল করা হয়েছে।")
    bot.edit_message_text(f"Status: {action.upper()}", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "💰 ব্যালেন্স")
def bal(message):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
    res = cur.fetchone()
    conn.close()
    balance = res[0] if res else 0
    bot.send_message(message.chat.id, f"💰 আপনার ব্যালেন্স: {balance:.2f}৳")

@bot.message_handler(func=lambda m: m.text == "📞 সাপোর্ট")
def supp(message):
    bot.send_message(message.chat.id, f"🛠 সাপোর্ট: {SUPPORT_ID}")

# ================= RUNNER =================
def keep_alive():
    t = Thread(target=run_web)
    t.start()

if __name__ == "__main__":
    keep_alive()
    print("Bot is Starting...")
    bot.infinity_polling()
           
