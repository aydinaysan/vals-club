import os, sqlite3, secrets, random
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "vals_club.sqlite3")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION")

XP_LEVEL = 250
CHEST_XP = [50, 75, 100, 150, 200, 300]
TASKS = [
    ("Giriş Yap", "Bugün Vals Club'a giriş yap.", 50),
    ("Günün Sorusu", "Ev aletleri hakkında mini quiz.", 100),
    ("Enerji Testi", "10 saniyelik enerji tasarrufu testini tamamla.", 100),
    ("Mini Görev", "Bugünün kısa görevini tamamla.", 100),
]
PRODUCTS = [
    ("SF16", "Vals SF16 Vantilatör", "🌬️", "RARE", 5),
    ("TH18", "Vals TH18 Isıtıcı", "🔥", "RARE", 6),
    ("VSC300", "Vals VSC 300 Süpürge", "🧹", "EPIC", 8),
    ("SMARTFAN", "Vals Smart Fan", "📱", "LEGENDARY", 10),
]

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      xp INTEGER DEFAULT 0,
      streak INTEGER DEFAULT 0,
      last_login TEXT,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tasks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT UNIQUE NOT NULL,
      title TEXT NOT NULL,
      description TEXT NOT NULL,
      xp INTEGER NOT NULL,
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS completions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      task_id INTEGER NOT NULL,
      day TEXT NOT NULL,
      UNIQUE(user_id, task_id, day)
    );
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      icon TEXT NOT NULL,
      rarity TEXT NOT NULL,
      rating INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS user_products(
      user_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      added_at TEXT NOT NULL,
      PRIMARY KEY(user_id, product_id)
    );
    CREATE TABLE IF NOT EXISTS rewards(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT NOT NULL,
      cost INTEGER NOT NULL,
      icon TEXT NOT NULL,
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS redemptions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      reward_id INTEGER NOT NULL,
      created_at TEXT NOT NULL
    );
    """)
    for i,(title,desc,xp) in enumerate(TASKS,1):
        c.execute("INSERT OR IGNORE INTO tasks(code,title,description,xp) VALUES(?,?,?,?)",
                  (f"daily_{i}",title,desc,xp))
    for code,name,icon,rarity,rating in PRODUCTS:
        c.execute("INSERT OR IGNORE INTO products(code,name,icon,rarity,rating) VALUES(?,?,?,?,?)",
                  (code,name,icon,rarity,rating))
    rewards = [
        ("%10 İndirim Kuponu","Bir sonraki alışverişte kullanılabilir.",500,"🏷️"),
        ("Ücretsiz Kargo","Bir siparişte ücretsiz kargo.",300,"🚚"),
        ("6 Ay Garanti Uzatma","Ürün kayıtlı kullanıcılar için.",1000,"🛡️"),
        ("Çekiliş Hakkı","Aylık ödül çekilişinde 1 hak.",200,"🎟️"),
    ]
    for r in rewards:
        c.execute("INSERT OR IGNORE INTO rewards(title,description,cost,icon) VALUES(?,?,?,?)",r)
    # pilot admin
    if not c.execute("SELECT 1 FROM users WHERE email=?",("admin@valsclub.local",)).fetchone():
        c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                  ("Vals Admin","admin@valsclub.local",generate_password_hash("ChangeMe123!"),datetime.utcnow().isoformat()))
    c.commit(); c.close()

def current_user():
    uid=session.get("uid")
    if not uid: return None
    c=db(); u=c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); c.close()
    return u

@app.context_processor
def inject():
    return {"user": current_user()}

def login_required(f):
    @wraps(f)
    def wrap(*a,**kw):
        if not current_user():
            return redirect(url_for("login"))
        return f(*a,**kw)
    return wrap

@app.route("/")
def index():
    if not current_user(): return redirect(url_for("login"))
    return redirect(url_for("home"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form["name"].strip()
        email=request.form["email"].strip().lower()
        password=request.form["password"]
        if len(password)<8:
            flash("Şifre en az 8 karakter olmalı.","error")
        else:
            c=db()
            try:
                c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                          (name,email,generate_password_hash(password),datetime.utcnow().isoformat()))
                c.commit()
                uid=c.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()["id"]
                session["uid"]=uid
                c.close()
                return redirect(url_for("home"))
            except sqlite3.IntegrityError:
                c.close(); flash("Bu e-posta zaten kayıtlı.","error")
    return render_template("auth.html",mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        password=request.form["password"]
        c=db(); u=c.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); c.close()
        if u and check_password_hash(u["password_hash"],password):
            session["uid"]=u["id"]; return redirect(url_for("home"))
        flash("E-posta veya şifre hatalı.","error")
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

def do_daily_login(u):
    today=str(date.today())
    c=db()
    last=u["last_login"]
    if last != today:
        streak = u["streak"]
        if last:
            try:
                if date.fromisoformat(last) == date.today()-timedelta(days=1): streak += 1
                else: streak = 1
            except: streak = 1
        else: streak = 1
        c.execute("UPDATE users SET xp=xp+50, streak=?, last_login=? WHERE id=?",(streak,today,u["id"]))
        c.execute("INSERT OR IGNORE INTO completions(user_id,task_id,day) VALUES(?,?,?)",
                  (u["id"],1,today))
        c.commit()
    c.close()

@app.route("/home")
@login_required
def home():
    u=current_user(); do_daily_login(u); u=current_user()
    c=db()
    tasks=c.execute("SELECT * FROM tasks WHERE active=1").fetchall()
    done={r["task_id"] for r in c.execute("SELECT task_id FROM completions WHERE user_id=? AND day=?",(u["id"],str(date.today()))).fetchall()}
    products=c.execute("""SELECT p.*, up.added_at FROM products p LEFT JOIN user_products up
                         ON p.id=up.product_id AND up.user_id=?""",(u["id"],)).fetchall()
    rewards=c.execute("SELECT * FROM rewards WHERE active=1 ORDER BY cost").fetchall()
    c.close()
    rating=sum(p["rating"] for p in products if p["added_at"])
    level=(u["xp"]//XP_LEVEL)+1
    next_xp=level*XP_LEVEL
    return render_template("home.html",u=u,tasks=tasks,done=done,products=products,rewards=rewards,
                           rating=rating,level=level,next_xp=next_xp)

@app.post("/task/<int:task_id>")
@login_required
def complete_task(task_id):
    u=current_user(); today=str(date.today()); c=db()
    task=c.execute("SELECT * FROM tasks WHERE id=? AND active=1",(task_id,)).fetchone()
    if not task: c.close(); return redirect(url_for("home"))
    try:
        c.execute("INSERT INTO completions(user_id,task_id,day) VALUES(?,?,?)",(u["id"],task_id,today))
        c.execute("UPDATE users SET xp=xp+? WHERE id=?",(task["xp"],u["id"]))
        c.commit(); flash(f"+{task['xp']} XP kazandın.","ok")
    except sqlite3.IntegrityError:
        flash("Bu görevi bugün zaten tamamladın.","error")
    c.close(); return redirect(url_for("home"))

@app.post("/chest")
@login_required
def chest():
    u=current_user(); today=str(date.today()); key=f"chest_{today}"
    if session.get(key):
        flash("Bugünkü sandığı zaten açtın.","error"); return redirect(url_for("home"))
    amount=random.choice(CHEST_XP)
    c=db(); c.execute("UPDATE users SET xp=xp+? WHERE id=?",(amount,u["id"])); c.commit(); c.close()
    session[key]=True; flash(f"Sandıktan +{amount} XP çıktı!","ok"); return redirect(url_for("home"))

@app.post("/product/<code>")
@login_required
def add_product(code):
    u=current_user(); c=db()
    p=c.execute("SELECT * FROM products WHERE code=?",(code,)).fetchone()
    if p:
        try:
            c.execute("INSERT INTO user_products VALUES(?,?,?)",(u["id"],p["id"],datetime.utcnow().isoformat()))
            c.execute("UPDATE users SET xp=xp+500 WHERE id=?",(u["id"],))
            c.commit(); flash(f"{p['name']} koleksiyonuna eklendi. +500 XP","ok")
        except sqlite3.IntegrityError: flash("Bu ürün zaten koleksiyonunda.","error")
    c.close(); return redirect(url_for("home"))

@app.post("/reward/<int:rid>")
@login_required
def redeem(rid):
    u=current_user(); c=db()
    r=c.execute("SELECT * FROM rewards WHERE id=? AND active=1",(rid,)).fetchone()
    if not r: c.close(); flash("Ödül bulunamadı.","error"); return redirect(url_for("home"))
    if u["xp"] < r["cost"]:
        c.close(); flash("Bu ödül için yeterli XP yok.","error"); return redirect(url_for("home"))
    c.execute("UPDATE users SET xp=xp-? WHERE id=?",(r["cost"],u["id"]))
    c.execute("INSERT INTO redemptions(user_id,reward_id,created_at) VALUES(?,?,?)",(u["id"],rid,datetime.utcnow().isoformat()))
    c.commit(); c.close(); flash(f"{r['title']} kullanıldı.","ok"); return redirect(url_for("home"))

@app.route("/leaderboard")
@login_required
def leaderboard():
    c=db(); rows=c.execute("SELECT name,xp,streak FROM users ORDER BY xp DESC LIMIT 50").fetchall(); c.close()
    return render_template("leaderboard.html",rows=rows)

@app.route("/admin")
@login_required
def admin():
    u=current_user()
    if u["email"]!="admin@valsclub.local": return "Yetkisiz",403
    c=db()
    stats={
      "users":c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"],
      "active_today":c.execute("SELECT COUNT(*) n FROM users WHERE last_login=?",(str(date.today()),)).fetchone()["n"],
      "products":c.execute("SELECT COUNT(*) n FROM user_products").fetchone()["n"],
      "xp":c.execute("SELECT COALESCE(SUM(xp),0) n FROM users").fetchone()["n"],
    }
    users=c.execute("SELECT id,name,email,xp,streak,last_login,created_at FROM users ORDER BY xp DESC").fetchall()
    c.close(); return render_template("admin.html",stats=stats,users=users)

@app.route("/health")
def health(): return jsonify(ok=True)

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
