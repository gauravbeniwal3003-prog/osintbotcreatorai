import os, json, hmac, hashlib, base64, asyncio, threading, requests, sys, time, multiprocessing
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== HARDCODED CONFIG ====================
BOT_TOKEN = "8745866721:AAHxyMyLu0D8-vuvAM5sP0RV5nLDYot0pOU"
CASHFREE_APP_ID = "12765199c4c89286efc175eec099156721"
CASHFREE_SECRET = "cfsk_ma_prod_1f9abc0880569bd7a4b0ea1c712adb53_ad67e85f"
ADMIN_ID = "gaurav_beniwal_0001"
CASHFREE_API = "https://api.cashfree.com/pg"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bots.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================
class UserBot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True)
    bot_token = db.Column(db.String(200))
    bot_name = db.Column(db.String(100))
    admin_username = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=False)
    is_deployed = db.Column(db.Boolean, default=False)
    order_id = db.Column(db.String(100))

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50))
    order_id = db.Column(db.String(100), unique=True)
    amount = db.Column(db.Float, default=500)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ==================== PAYMENT FUNCTIONS ====================
def create_payment(user_id):
    order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}"
    payload = {
        "order_id": order_id,
        "order_amount": 500,
        "order_currency": "INR",
        "customer_details": {"customer_id": user_id, "customer_name": f"User_{user_id}"}
    }
    headers = {"x-api-version": "2022-09-01", "x-client-id": CASHFREE_APP_ID, "x-client-secret": CASHFREE_SECRET}
    try:
        resp = requests.post(f"{CASHFREE_API}/orders", json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            payment = Payment(user_id=user_id, order_id=order_id)
            db.session.add(payment)
            db.session.commit()
            return data
    except Exception as e:
        print(f"Payment error: {e}")
    return None

def check_payment_status(order_id):
    headers = {"x-api-version": "2022-09-01", "x-client-id": CASHFREE_APP_ID, "x-client-secret": CASHFREE_SECRET}
    try:
        resp = requests.get(f"{CASHFREE_API}/orders/{order_id}", headers=headers, timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except:
        return None

def verify_webhook():
    signature = request.headers.get('x-webhook-signature')
    timestamp = request.headers.get('x-webhook-timestamp')
    raw = request.data.decode('utf-8')
    if not signature or not timestamp:
        return False
    expected = base64.b64encode(hmac.new(CASHFREE_SECRET.encode(), f"{timestamp}.{raw}".encode(), hashlib.sha256).digest()).decode()
    return expected == signature

# ==================== DEPLOYMENT ====================
def deploy_bot(user_bot):
    template = f'''
import asyncio, aiohttp, json, sys, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = "{user_bot.bot_token}"
TRACEX_API = "https://tracexdata-api.onrender.com/api/lookup?key=Tracexbotnumberapi&number="

async def start(update, context):
    keyboard = [[InlineKeyboardButton("📱 Phone Lookup", callback_data="lookup")]]
    await update.message.reply_text(
        "🔥 **OSINT Bot**\\n\\nSend any 10-digit Indian number!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "lookup":
        await query.edit_message_text("📱 Send 10-digit number:")
        context.user_data['state'] = 'num'

async def handle(update, context):
    if context.user_data.get('state') == 'num':
        num = update.message.text.strip()
        if not (num.isdigit() and len(num)==10):
            await update.message.reply_text("❌ Invalid number! Send 10 digits only.")
            return
        msg = await update.message.reply_text("🔍 Searching.")
        for i in range(5):
            await asyncio.sleep(0.5)
            await msg.edit_text("🔍 Searching" + "."*(i%4+1))
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{{TRACEX_API}}{{num}}") as resp:
                    data = await resp.json()
                    result = "📊 **Result:**\\n\\n```json\\n" + json.dumps(data, indent=2) + "\\n```"
                    keyboard = [[InlineKeyboardButton("🔄 New Search", callback_data="lookup")]]
                    await msg.edit_text(result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await msg.edit_text(f"❌ Error: {{str(e)}}")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
print("🤖 User Bot Running!")
app.run_polling()
'''
    os.makedirs("deployed_bots", exist_ok=True)
    filename = f"deployed_bots/bot_{user_bot.user_id}.py"
    with open(filename, 'w') as f:
        f.write(template)
    user_bot.is_deployed = True
    db.session.commit()
    
    try:
        threading.Thread(target=lambda: os.system(f"python {filename} > /dev/null 2>&1 &"), daemon=True).start()
    except:
        pass
    return True

# ==================== TELEGRAM BOT HANDLERS ====================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    user = UserBot.query.filter_by(user_id=uid).first()
    
    if user and user.is_active and user.expires_at > datetime.utcnow():
        keyboard = [
            [InlineKeyboardButton("🤖 My Bot", callback_data="mybot")],
            [InlineKeyboardButton("💳 Extend", callback_data="extend")],
            [InlineKeyboardButton("🛑 Stop", callback_data="stop")]
        ]
    else:
        keyboard = [[InlineKeyboardButton("🚀 Create Bot (₹500/mo)", callback_data="create")]]
    
    await update.message.reply_text(
        "🔥 **OSINT Bot Creator AI**\n\n"
        "Create your own phone lookup bot!\n"
        "💰 ₹500/month • Auto-deploy • 24/7 support\n"
        f"👑 Admin: @{ADMIN_ID}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    data = query.data
    
    if data == "create":
        context.user_data['state'] = 'token'
        await query.edit_message_text(
            "🤖 **Step 1/3:** Send your bot token from @BotFather\n"
            "Format: `123456:ABC-DEF1234ghIkl`",
            parse_mode='Markdown'
        )
    
    elif data == "mybot":
        user = UserBot.query.filter_by(user_id=uid).first()
        if user:
            days = (user.expires_at - datetime.utcnow()).days
            await query.edit_message_text(
                f"🤖 **Your Bot**\n"
                f"Name: {user.bot_name}\n"
                f"Admin: @{user.admin_username}\n"
                f"Expires: {days} days\n"
                f"Status: {'✅ Active' if user.is_active else '❌ Inactive'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Restart", callback_data="restart")],
                    [InlineKeyboardButton("💳 Extend", callback_data="extend")]
                ])
            )
    
    elif data == "extend":
        order = create_payment(uid)
        if order:
            await query.edit_message_text(
                f"💳 **Payment Order Created**\n"
                f"Order ID: {order['order_id']}\n"
                f"Amount: ₹500\n\n"
                f"[Pay Now](https://pay.cashfree.com/order/{order['payment_session_id']})",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Check Status", callback_data="checkpay")]
                ])
            )
        else:
            await query.edit_message_text("❌ Payment gateway error! Try again.")
    
    elif data == "checkpay":
        payment = Payment.query.filter_by(user_id=uid, status='pending').first()
        if payment:
            status = check_payment_status(payment.order_id)
            if status and status.get('order_status') == 'PAID':
                payment.status = 'success'
                user = UserBot.query.filter_by(user_id=uid).first()
                if user:
                    user.is_active = True
                    user.expires_at = datetime.utcnow() + timedelta(days=30)
                    db.session.commit()
                    deploy_bot(user)
                    await query.edit_message_text("✅ Payment success! Bot deployed 🎉")
                else:
                    await query.edit_message_text("❌ User not found!")
            else:
                await query.edit_message_text("⏳ Still pending... try again in 10s")
        else:
            await query.edit_message_text("❌ No pending payment found.")
    
    elif data == "stop":
        user = UserBot.query.filter_by(user_id=uid).first()
        if user:
            user.is_active = False
            db.session.commit()
            await query.edit_message_text("🛑 Bot stopped. Use /start to reactivate")
    
    elif data == "restart":
        user = UserBot.query.filter_by(user_id=uid).first()
        if user:
            user.is_active = True
            db.session.commit()
            await query.edit_message_text("🔄 Bot restarted!")

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    text = update.message.text
    
    if context.user_data.get('state') == 'token':
        if ':' in text and len(text) > 20:
            context.user_data['bot_token'] = text
            context.user_data['state'] = 'botname'
            await update.message.reply_text("✅ **Step 2/3:** Enter bot display name:")
        else:
            await update.message.reply_text("❌ Invalid token! Get from @BotFather")
    
    elif context.user_data.get('state') == 'botname':
        context.user_data['bot_name'] = text[:30]
        context.user_data['state'] = 'adminname'
        await update.message.reply_text("✅ **Step 3/3:** Enter admin username (without @):")
    
    elif context.user_data.get('state') == 'adminname':
        admin = text.replace('@', '').strip()
        user = UserBot(
            user_id=uid,
            bot_token=context.user_data['bot_token'],
            bot_name=context.user_data['bot_name'],
            admin_username=admin,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(user)
        db.session.commit()
        
        order = create_payment(uid)
        context.user_data['state'] = None
        
        if order:
            await update.message.reply_text(
                f"✅ **Bot created!**\n"
                f"Name: {context.user_data['bot_name']}\n"
                f"Admin: @{admin}\n\n"
                f"💰 Pay ₹500 to activate:\n"
                f"https://pay.cashfree.com/order/{order['payment_session_id']}\n\n"
                f"After payment, bot auto-deploys in 2 mins!"
            )
        else:
            await update.message.reply_text(
                f"✅ **Bot created!**\n"
                f"Name: {context.user_data['bot_name']}\n"
                f"Admin: @{admin}\n\n"
                f"⚠️ Payment gateway temporarily down. Contact @{ADMIN_ID}"
            )

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    return "🔥 OSINT Bot Creator AI - Running"

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if not verify_webhook():
        return jsonify({"error": "Invalid"}), 400
    data = request.get_json()
    if not data:
        return '', 200
    order_id = data.get('order_id')
    if data.get('payment_status') == 'SUCCESS' and order_id:
        payment = Payment.query.filter_by(order_id=order_id).first()
        if payment:
            payment.status = 'success'
            user = UserBot.query.filter_by(user_id=payment.user_id).first()
            if user:
                user.is_active = True
                user.expires_at = datetime.utcnow() + timedelta(days=30)
                deploy_bot(user)
                db.session.commit()
    return '', 200

@app.route('/admin')
def admin():
    if request.args.get('key') != 'admin123':
        return "🔒 Access Denied"
    users = UserBot.query.all()
    html = '''
    <style>
        body{background:#0a0a0a;color:#fff;font-family:monospace;padding:20px}
        .bot{border:1px solid #333;padding:10px;margin:5px;border-radius:5px}
        .active{color:#0f0}
        .expired{color:#f00}
        .pending{color:#ff0}
        h1{color:#ff4444}
    </style>
    <h1>💀 Admin Panel</h1>
    <h3>👑 @gaurav_beniwal_0001</h3>
    <div>Total Bots: {{users|length}}</div>
    {% for u in users %}
    <div class="bot">
        <b>{{u.bot_name}}</b> | @{{u.admin_username}} | 
        <span class="{% if u.is_active and u.expires_at > now %}active{% elif u.is_active %}pending{% else %}expired{% endif %}">
            {% if u.is_active and u.expires_at > now %}✅ Active{% elif u.is_active %}⏳ Pending Payment{% else %}❌ Expired{% endif %}
        </span>
        | Expires: {{u.expires_at.strftime('%Y-%m-%d')}}
        | Deployed: {{'✅' if u.is_deployed else '❌'}}
        | ID: {{u.user_id}}
    </div>
    {% endfor %}
    '''
    return render_template_string(html, users=users, now=datetime.utcnow())

# ==================== RUN BOT ====================
def run_telegram_bot():
    """Run Telegram bot with retry"""
    while True:
        try:
            print("🤖 Starting Telegram bot...")
            bot = Application.builder().token(BOT_TOKEN).build()
            bot.add_handler(CommandHandler("start", start_cmd))
            bot.add_handler(CallbackQueryHandler(button_cb))
            bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
            print("🤖 Bot started successfully! Polling...")
            bot.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            print(f"❌ Bot error: {e}")
            time.sleep(5)

# ==================== MAIN ====================
if __name__ == "__main__":
    # Start bot in separate process
    p = multiprocessing.Process(target=run_telegram_bot)
    p.daemon = True
    p.start()
    print("✅ Bot process started")
    
    # Run Flask
    port = int(os.environ.get("PORT", 5000))
    print(f"🔥 Flask server running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
