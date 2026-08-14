import os, sqlite3, random, secrets
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "vals_club.sqlite3")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION")

XP_LEVEL = 250
CHEST_XP = [50, 75, 100, 150, 200, 300]
TASKS = [
    ("Giriş Yap", "Bugün Vals Club'a giriş yap.", 50),
    ("Günün Sorusu", "Ev aletleri hakkında mini quiz.", 100),
    ("Enerji Testi", "3 soruluk enerji tasarrufu testi.", 100),
    ("Mini Görev", "Bugünün kısa görevini tamamla.", 100),
]
PRODUCTS = [
    ("SF16", "Vals SF16 Vantilatör", "🌬️", "RARE", 5),
    ("TH18", "Vals TH18 Isıtıcı", "🔥", "RARE", 6),
    ("VSC300", "Vals VSC 300 Süpürge", "🧹", "EPIC", 8),
    ("SMARTFAN", "Vals Smart Fan", "📱", "LEGENDARY", 10),
]

QUIZZES = [
    ("q1", "Bir vantilatörün elektrik tüketimini azaltmanın en doğrudan yollarından biri hangisidir?", ["Daha yüksek hızda çalıştırmak", "Daha düşük hızda çalıştırmak", "Izgarasını kapatmak", "Odayı ısıtmak"], 1, "Daha düşük hızda çalıştırmak, motorun çektiği gücü azaltabilir."),
    ("q2", "Bir ısıtıcıyı gereksiz yere açık bırakmak neden verimsizdir?", ["Elektrik tüketmeye devam eder", "Odayı soğutur", "Havayı nemlendirir", "Sesi azaltır"], 0, "Isıtıcı çalıştığı sürece enerji tüketir; ihtiyaç yokken açık bırakmak gereksiz tüketimdir."),
    ("q3", "HEPA filtreli bir süpürgede filtrenin düzenli temizliği/değişimi neden önemlidir?", ["Sadece rengi için", "Hava akışını ve filtreleme performansını korumak için", "Motoru daha çok ısıtmak için", "Bataryayı büyütmek için"], 1, "Tıkalı filtre hava akışını azaltabilir ve performansı düşürebilir."),
    ("q4", "Bir odada vantilatör kullanırken en önemli gerçek nedir?", ["Vantilatör odayı klimadan bağımsız olarak soğutur", "Vantilatör esas olarak hava hareketiyle serinlik hissi sağlar", "Vantilatör havadaki oksijeni artırır", "Vantilatör nemi tamamen yok eder"], 1, "Vantilatör havayı hareket ettirerek vücudun ısı kaybını artırır; ortam sıcaklığını klima gibi düşürmez."),
]
ENERGY_QUESTIONS = [
    ("e1", "Ev boşken elektrikli ısıtıcıyı açık bırakmak", ["Enerji tasarrufudur", "Gereksiz tüketimdir", "Elektriği üretir"], 1),
    ("e2", "Vantilatör filtresi/ızgarası tozla kaplandığında", ["Hava akışı etkilenebilir", "Elektrik üretir", "Hiçbir etkisi olmaz"], 0),
    ("e3", "Süpürgede dolu/tozlu filtre ile çalışmaya devam etmek", ["Her zaman performansı artırır", "Hava akışını ve performansı düşürebilir", "Motoru güçlendirir"], 1),
]
MINI_TASKS = [
    ("m1", "Evinizde bugün en çok kullanılan elektrikli ev aletini bulun ve kullanımını 1 cümleyle düşünün."),
    ("m2", "Bir vantilatör veya ısıtıcıyı gereksiz yere açık bırakmadığınızdan emin olun."),
    ("m3", "Evdeki bir elektrikli cihazın enerji etiketini kontrol edin."),
    ("m4", "Süpürgenizin filtre/bakım durumunu kontrol edin."),
]

# ---------- Database ----------
def db():
    if DATABASE_URL:
        import psycopg
        conn = psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row)
        return conn
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def is_pg():
    return bool(DATABASE_URL)

def qmark(sql):
    return sql.replace("?", "%s") if is_pg() else sql

def execute(c, sql, params=()):
    return c.execute(qmark(sql), params)

def one(c, sql, params=()):
    return execute(c, sql, params).fetchone()

def allrows(c, sql, params=()):
    return execute(c, sql, params).fetchall()

def last_id(c):
    if is_pg():
        return one(c, "SELECT LASTVAL() AS id")["id"]
    return c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

def init_db():
    c = db()
    if is_pg():
        schema = """
        CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,xp INTEGER DEFAULT 0,streak INTEGER DEFAULT 0,last_login TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id SERIAL PRIMARY KEY,code TEXT UNIQUE NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,xp INTEGER NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS completions(id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,task_id INTEGER NOT NULL,day TEXT NOT NULL,UNIQUE(user_id,task_id,day));
        CREATE TABLE IF NOT EXISTS products(id SERIAL PRIMARY KEY,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,icon TEXT NOT NULL,rarity TEXT NOT NULL,rating INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS user_products(user_id INTEGER NOT NULL,product_id INTEGER NOT NULL,added_at TEXT NOT NULL,PRIMARY KEY(user_id,product_id));
        CREATE TABLE IF NOT EXISTS rewards(id SERIAL PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,cost INTEGER NOT NULL,icon TEXT NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS redemptions(id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,reward_id INTEGER NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS quiz_questions(id SERIAL PRIMARY KEY,code TEXT UNIQUE NOT NULL,question TEXT NOT NULL,options TEXT NOT NULL,correct_index INTEGER NOT NULL,explanation TEXT NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS activity_attempts(id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,kind TEXT NOT NULL,activity_code TEXT NOT NULL,day TEXT NOT NULL,score INTEGER DEFAULT 0,completed INTEGER DEFAULT 0,UNIQUE(user_id,kind,day));
        """
    else:
        schema = """
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,xp INTEGER DEFAULT 0,streak INTEGER DEFAULT 0,last_login TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,xp INTEGER NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS completions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,task_id INTEGER NOT NULL,day TEXT NOT NULL,UNIQUE(user_id,task_id,day));
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,icon TEXT NOT NULL,rarity TEXT NOT NULL,rating INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS user_products(user_id INTEGER NOT NULL,product_id INTEGER NOT NULL,added_at TEXT NOT NULL,PRIMARY KEY(user_id,product_id));
        CREATE TABLE IF NOT EXISTS rewards(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,description TEXT NOT NULL,cost INTEGER NOT NULL,icon TEXT NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS redemptions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,reward_id INTEGER NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS quiz_questions(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,question TEXT NOT NULL,options TEXT NOT NULL,correct_index INTEGER NOT NULL,explanation TEXT NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS activity_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,kind TEXT NOT NULL,activity_code TEXT NOT NULL,day TEXT NOT NULL,score INTEGER DEFAULT 0,completed INTEGER DEFAULT 0,UNIQUE(user_id,kind,day));
        """
    c.execute(schema)
    for i,(title,desc,xp) in enumerate(TASKS,1):
        if not one(c,"SELECT 1 FROM tasks WHERE code=?",(f"daily_{i}",)):
            execute(c,"INSERT INTO tasks(code,title,description,xp) VALUES(?,?,?,?)",(f"daily_{i}",title,desc,xp))
    for code,name,icon,rarity,rating in PRODUCTS:
        if not one(c,"SELECT 1 FROM products WHERE code=?",(code,)):
            execute(c,"INSERT INTO products(code,name,icon,rarity,rating) VALUES(?,?,?,?,?)",(code,name,icon,rarity,rating))
    rewards = [("%10 İndirim Kuponu","Bir sonraki alışverişte kullanılabilir.",500,"🏷️"),("Ücretsiz Kargo","Bir siparişte ücretsiz kargo.",300,"🚚"),("6 Ay Garanti Uzatma","Ürün kayıtlı kullanıcılar için.",1000,"🛡️"),("Çekiliş Hakkı","Aylık ödül çekilişinde 1 hak.",200,"🎟️")]
    for r in rewards:
        if not one(c,"SELECT 1 FROM rewards WHERE title=?",(r[0],)):
            execute(c,"INSERT INTO rewards(title,description,cost,icon) VALUES(?,?,?,?)",r)
    for code,question,options,correct,explanation in QUIZZES:
        import json
        if not one(c,"SELECT 1 FROM quiz_questions WHERE code=?",(code,)):
            execute(c,"INSERT INTO quiz_questions(code,question,options,correct_index,explanation) VALUES(?,?,?,?,?)",(code,question,json.dumps(options,ensure_ascii=False),correct,explanation))
    if not one(c,"SELECT 1 FROM users WHERE email=?",("admin@valsclub.local",)):
        execute(c,"INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",("Vals Admin","admin@valsclub.local",generate_password_hash("ChangeMe123!"),datetime.utcnow().isoformat()))
    c.commit(); c.close()

# ---------- Auth ----------
def current_user():
    uid=session.get("uid")
    if not uid: return None
    c=db(); u=one(c,"SELECT * FROM users WHERE id=?",(uid,)); c.close(); return u

@app.context_processor
def inject(): return {"user": current_user(), "XP_LEVEL": XP_LEVEL}

def login_required(f):
    @wraps(f)
    def wrap(*a,**kw):
        if not current_user(): return redirect(url_for("login"))
        return f(*a,**kw)
    return wrap

@app.route("/")
def index(): return redirect(url_for("home" if current_user() else "login"))

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); password=request.form.get("password","")
        if not name or len(password)<8: flash("Adınızı girin ve en az 8 karakterlik şifre kullanın.","error")
        else:
            c=db()
            try:
                execute(c,"INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",(name,email,generate_password_hash(password),datetime.utcnow().isoformat())); c.commit()
                uid=one(c,"SELECT id FROM users WHERE email=?",(email,))["id"]; session["uid"]=uid; c.close(); return redirect(url_for("home"))
            except Exception:
                c.rollback(); c.close(); flash("Bu e-posta zaten kayıtlı.","error")
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); password=request.form.get("password",""); c=db(); u=one(c,"SELECT * FROM users WHERE email=?",(email,)); c.close()
        if u and check_password_hash(u["password_hash"],password): session["uid"]=u["id"]; return redirect(url_for("home"))
        flash("E-posta veya şifre hatalı.","error")
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

# ---------- Daily mechanics ----------
def do_daily_login(u):
    today=str(date.today()); c=db(); last=u["last_login"]
    if last != today:
        streak=u["streak"]
        if last:
            try: streak=streak+1 if date.fromisoformat(last)==date.today()-timedelta(days=1) else 1
            except: streak=1
        else: streak=1
        execute(c,"UPDATE users SET xp=xp+50,streak=?,last_login=? WHERE id=?",(streak,today,u["id"]))
        execute(c,"INSERT INTO completions(user_id,task_id,day) VALUES(?,?,?) ON CONFLICT(user_id,task_id,day) DO NOTHING",(u["id"],1,today)) if is_pg() else execute(c,"INSERT OR IGNORE INTO completions(user_id,task_id,day) VALUES(?,?,?)",(u["id"],1,today))
        c.commit()
    c.close()

def daily_code(kind, items):
    idx=(date.today().toordinal())%len(items)
    return items[idx][0], idx

def get_quiz_for_today(c):
    rows=allrows(c,"SELECT * FROM quiz_questions WHERE active=1 ORDER BY id")
    if not rows: return None
    return rows[date.today().toordinal()%len(rows)]

def activity_done(c,u,kind):
    return one(c,"SELECT * FROM activity_attempts WHERE user_id=? AND kind=? AND day=?",(u["id"],kind,str(date.today())))

def award_activity(c,u,task_code,score=0):
    task=one(c,"SELECT * FROM tasks WHERE code=? AND active=1",(task_code,))
    if not task: return False,0
    today=str(date.today())
    existing=one(c,"SELECT 1 FROM completions WHERE user_id=? AND task_id=? AND day=?",(u["id"],task["id"],today))
    if existing: return False,0
    execute(c,"INSERT INTO completions(user_id,task_id,day) VALUES(?,?,?)",(u["id"],task["id"],today))
    execute(c,"UPDATE users SET xp=xp+? WHERE id=?",(task["xp"],u["id"]))
    return True,task["xp"]

@app.route("/home")
@login_required
def home():
    u=current_user(); do_daily_login(u); u=current_user(); c=db()
    tasks=allrows(c,"SELECT * FROM tasks WHERE active=1 ORDER BY id")
    done={r["task_id"] for r in allrows(c,"SELECT task_id FROM completions WHERE user_id=? AND day=?",(u["id"],str(date.today())))}
    products=allrows(c,"SELECT p.*,up.added_at FROM products p LEFT JOIN user_products up ON p.id=up.product_id AND up.user_id=? ORDER BY p.id",(u["id"],))
    rewards=allrows(c,"SELECT * FROM rewards WHERE active=1 ORDER BY cost")
    quiz_done=bool(activity_done(c,u,"quiz")); energy_done=bool(activity_done(c,u,"energy")); mini_done=bool(activity_done(c,u,"mini"))
    c.close(); rating=sum(p["rating"] for p in products if p["added_at"]); level=(u["xp"]//XP_LEVEL)+1; next_xp=level*XP_LEVEL
    return render_template("home.html",u=u,tasks=tasks,done=done,products=products,rewards=rewards,rating=rating,level=level,next_xp=next_xp,quiz_done=quiz_done,energy_done=energy_done,mini_done=mini_done)

@app.post("/task/<int:task_id>")
@login_required
def complete_task(task_id):
    u=current_user(); c=db(); task=one(c,"SELECT * FROM tasks WHERE id=? AND active=1",(task_id,))
    if not task: c.close(); return redirect(url_for("home"))
    if task["code"]=="daily_2": c.close(); return redirect(url_for("quiz"))
    if task["code"]=="daily_3": c.close(); return redirect(url_for("energy_test"))
    if task["code"]=="daily_4": c.close(); return redirect(url_for("mini_task"))
    try:
        award_activity(c,u,"daily_1"); c.commit(); flash("+50 XP kazandın.","ok")
    except Exception: c.rollback(); flash("Bu görev bugün zaten tamamlandı.","error")
    c.close(); return redirect(url_for("home"))

# ---------- Interactive daily activities ----------
@app.route("/quiz",methods=["GET","POST"])
@login_required
def quiz():
    import json
    u=current_user(); c=db(); existing=activity_done(c,u,"quiz")
    if existing:
        q=get_quiz_for_today(c); c.close(); return render_template("quiz.html",q=q,options=json.loads(q["options"]) if q else [],done=True,result=existing["score"],explanation=q["explanation"] if q else "")
    q=get_quiz_for_today(c)
    if not q: c.close(); flash("Bugünün sorusu hazırlanamadı.","error"); return redirect(url_for("home"))
    options=json.loads(q["options"])
    if request.method=="POST":
        try: answer=int(request.form.get("answer","-1"))
        except: answer=-1
        correct=answer==q["correct_index"]; score=100 if correct else 0
        awarded,xp=(False,0)
        if correct:
            awarded,xp=award_activity(c,u,"daily_2")
        else:
            task=one(c,"SELECT * FROM tasks WHERE code=? AND active=1",("daily_2",))
            already=one(c,"SELECT 1 FROM completions WHERE user_id=? AND task_id=? AND day=?",(u["id"],task["id"],str(date.today()))) if task else None
            if task and not already:
                execute(c,"INSERT INTO completions(user_id,task_id,day) VALUES(?,?,?)",(u["id"],task["id"],str(date.today())))
        execute(c,"INSERT INTO activity_attempts(user_id,kind,activity_code,day,score,completed) VALUES(?,?,?,?,?,1)",(u["id"],"quiz",q["code"],str(date.today()),score))
        c.commit(); c.close(); flash((f"Doğru! +{xp} XP kazandın." if correct else "Yanlış cevap. XP kazanamadın."),"ok" if correct else "error")
        return render_template("quiz.html",q=q,options=options,done=True,result=score,explanation=q["explanation"])
    c.close(); return render_template("quiz.html",q=q,options=options,done=False)

@app.route("/energy",methods=["GET","POST"])
@login_required
def energy_test():
    u=current_user(); c=db(); existing=activity_done(c,u,"energy")
    idx=date.today().toordinal()%len(ENERGY_QUESTIONS)
    # One daily 3-question test, deterministic by day.
    questions=[ENERGY_QUESTIONS[(idx+i)%len(ENERGY_QUESTIONS)] for i in range(3)]
    if existing:
        c.close(); return render_template("energy.html",questions=questions,done=True,score=existing["score"])
    if request.method=="POST":
        score=0
        for i,(code,q,opts,correct) in enumerate(questions):
            try: ans=int(request.form.get(f"q{i}","-1"))
            except: ans=-1
            if ans==correct: score+=1
        awarded,xp=award_activity(c,u,"daily_3",score)
        execute(c,"INSERT INTO activity_attempts(user_id,kind,activity_code,day,score,completed) VALUES(?,?,?,?,?,1)",(u["id"],"energy","energy",str(date.today()),score))
        c.commit(); c.close(); flash((f"Test tamamlandı: {score}/3. +{xp} XP kazandın." if awarded else f"Test tamamlandı: {score}/3."),"ok")
        return render_template("energy.html",questions=questions,done=True,score=score)
    c.close(); return render_template("energy.html",questions=questions,done=False)

@app.route("/mini-task",methods=["GET","POST"])
@login_required
def mini_task():
    u=current_user(); c=db(); existing=activity_done(c,u,"mini"); code,idx=daily_code("mini",MINI_TASKS); text=MINI_TASKS[idx][1]
    if existing:
        c.close(); return render_template("mini_task.html",text=text,done=True)
    if request.method=="POST":
        note=request.form.get("note","").strip()
        if len(note)<3: c.close(); flash("Görevi tamamladığını belirtmek için kısa bir cevap yaz.","error"); return redirect(url_for("mini_task"))
        awarded,xp=award_activity(c,u,"daily_4")
        execute(c,"INSERT INTO activity_attempts(user_id,kind,activity_code,day,score,completed) VALUES(?,?,?,?,?,1)",(u["id"],"mini",code,str(date.today()),1))
        c.commit(); c.close(); flash(f"Mini görev tamamlandı. +{xp} XP kazandın.","ok"); return redirect(url_for("home"))
    c.close(); return render_template("mini_task.html",text=text,done=False)

@app.post("/chest")
@login_required
def chest():
    u=current_user(); today=str(date.today()); c=db(); existing=one(c,"SELECT 1 FROM activity_attempts WHERE user_id=? AND kind=? AND day=?",(u["id"],"chest",today))
    if existing: c.close(); flash("Bugünkü sandığı zaten açtın.","error"); return redirect(url_for("home"))
    amount=random.choice(CHEST_XP); execute(c,"UPDATE users SET xp=xp+? WHERE id=?",(amount,u["id"])); execute(c,"INSERT INTO activity_attempts(user_id,kind,activity_code,day,score,completed) VALUES(?,?,?,?,?,1)",(u["id"],"chest","daily_chest",today,amount)); c.commit(); c.close(); flash(f"Sandıktan +{amount} XP çıktı!","ok"); return redirect(url_for("home"))

@app.post("/product/<code>")
@login_required
def add_product(code):
    u=current_user(); c=db(); p=one(c,"SELECT * FROM products WHERE code=?",(code,))
    if p:
        try:
            execute(c,"INSERT INTO user_products(user_id,product_id,added_at) VALUES(?,?,?)",(u["id"],p["id"],datetime.utcnow().isoformat())); execute(c,"UPDATE users SET xp=xp+500 WHERE id=?",(u["id"],)); c.commit(); flash(f"{p['name']} koleksiyonuna eklendi. +500 XP","ok")
        except Exception: c.rollback(); flash("Bu ürün zaten koleksiyonunda.","error")
    c.close(); return redirect(url_for("home"))

@app.post("/reward/<int:rid>")
@login_required
def redeem(rid):
    u=current_user(); c=db(); r=one(c,"SELECT * FROM rewards WHERE id=? AND active=1",(rid,))
    if not r: c.close(); flash("Ödül bulunamadı.","error"); return redirect(url_for("home"))
    if u["xp"]<r["cost"]: c.close(); flash("Bu ödül için yeterli XP yok.","error"); return redirect(url_for("home"))
    execute(c,"UPDATE users SET xp=xp-? WHERE id=?",(r["cost"],u["id"])); execute(c,"INSERT INTO redemptions(user_id,reward_id,created_at) VALUES(?,?,?)",(u["id"],rid,datetime.utcnow().isoformat())); c.commit(); c.close(); flash(f"{r['title']} kullanıldı.","ok"); return redirect(url_for("home"))

@app.route("/leaderboard")
@login_required
def leaderboard():
    c=db(); rows=allrows(c,"SELECT name,xp,streak FROM users ORDER BY xp DESC LIMIT 50"); c.close(); return render_template("leaderboard.html",rows=rows)

@app.route("/admin")
@login_required
def admin():
    u=current_user()
    if u["email"]!="admin@valsclub.local": return "Yetkisiz",403
    c=db(); stats={"users":one(c,"SELECT COUNT(*) n FROM users")["n"],"active_today":one(c,"SELECT COUNT(*) n FROM users WHERE last_login=?",(str(date.today()),))["n"],"products":one(c,"SELECT COUNT(*) n FROM user_products")["n"],"xp":one(c,"SELECT COALESCE(SUM(xp),0) n FROM users")["n"],"quiz_today":one(c,"SELECT COUNT(*) n FROM activity_attempts WHERE kind='quiz' AND day=?",(str(date.today()),))["n"]}; users=allrows(c,"SELECT id,name,email,xp,streak,last_login,created_at FROM users ORDER BY xp DESC"); c.close(); return render_template("admin.html",stats=stats,users=users)

@app.route("/health")
def health(): return jsonify(ok=True)

with app.app_context():
    init_db()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
