from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bots.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

@app.route('/')
def home():
    return "🔥 OSINT Bot Creator AI - Running"

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

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
        h1{color:#ff4444}
    </style>
    <h1>💀 Admin Panel</h1>
    <h3>👑 @gaurav_beniwal_0001</h3>
    <div>Total Bots: {{users|length}}</div>
    {% for u in users %}
    <div class="bot">
        <b>{{u.bot_name}}</b> | @{{u.admin_username}} | 
        <span class="{% if u.is_active and u.expires_at > now %}active{% else %}expired{% endif %}">
            {% if u.is_active and u.expires_at > now %}✅ Active{% else %}❌ Expired{% endif %}
        </span>
        | Expires: {{u.expires_at.strftime('%Y-%m-%d')}}
        | Deployed: {{'✅' if u.is_deployed else '❌'}}
    </div>
    {% endfor %}
    '''
    return render_template_string(html, users=users, now=datetime.utcnow())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
