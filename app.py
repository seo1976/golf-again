import os, sqlite3, uuid
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "golf_again.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png","jpg","jpeg","webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      nickname TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS listings(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      category TEXT NOT NULL,
      brand TEXT,
      price INTEGER NOT NULL,
      condition TEXT,
      shaft TEXT,
      flex TEXT,
      region TEXT,
      trade_method TEXT,
      description TEXT,
      image TEXT,
      status TEXT DEFAULT '판매중',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS favorites(
      user_id INTEGER NOT NULL,
      listing_id INTEGER NOT NULL,
      PRIMARY KEY(user_id, listing_id)
    );
    """)
    conn.commit()
    conn.close()
init_db()
def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if "user_id" not in session:
            flash("로그인이 필요합니다.")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrap

def save_image(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".",1)[-1].lower()
    if ext not in ALLOWED_EXT:
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename

@app.context_processor
def inject_user():
    return {"current_user": session.get("nickname")}

@app.route("/")
def index():
    q = request.args.get("q","").strip()
    category = request.args.get("category","").strip()
    conn = db()
    sql = """SELECT listings.*, users.nickname,
      (SELECT COUNT(*) FROM favorites f WHERE f.listing_id=listings.id) fav_count
      FROM listings JOIN users ON users.id=listings.user_id WHERE 1=1"""
    params=[]
    if q:
        sql += " AND (listings.title LIKE ? OR listings.brand LIKE ? OR listings.description LIKE ?)"
        like=f"%{q}%"; params += [like,like,like]
    if category:
        sql += " AND listings.category=?"; params.append(category)
    sql += " ORDER BY listings.id DESC"
    items = conn.execute(sql, params).fetchall()
    favs=set()
    if "user_id" in session:
        favs={r["listing_id"] for r in conn.execute("SELECT listing_id FROM favorites WHERE user_id=?", (session["user_id"],))}
    conn.close()
    return render_template("index.html", items=items, favs=favs, q=q, category=category)
@app.route("/listings")
def listings():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    conn = db()
    sql = """SELECT listings.*, users.nickname,
             (SELECT COUNT(*) FROM favorites
              WHERE favorites.listing_id = listings.id) AS favorite_count
             FROM listings
             JOIN users ON users.id = listings.user_id
             WHERE listings.status = '판매중'"""
    params = []

    if q:
        sql += " AND (listings.title LIKE ? OR listings.brand LIKE ? OR listings.description LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]

    if category:
        sql += " AND listings.category=?"
        params.append(category)

    sql += " ORDER BY listings.id DESC"
    items = conn.execute(sql, params).fetchall()

    favs = set()
    if "user_id" in session:
        favs = {
            r["listing_id"]
            for r in conn.execute(
                "SELECT listing_id FROM favorites WHERE user_id=?",
                (session["user_id"],)
            ).fetchall()
        }

    conn.close()
    return render_template("listings.html", items=items, favs=favs, q=q, category=category)
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        nickname=request.form["nickname"].strip()
        pw=request.form["password"]
        if len(pw)<6:
            flash("비밀번호는 6자 이상으로 입력해주세요.")
            return redirect(url_for("register"))
        conn=db()
        try:
            cur=conn.execute("INSERT INTO users(email,nickname,password_hash) VALUES(?,?,?)",
                             (email,nickname,generate_password_hash(pw)))
            conn.commit()
            session["user_id"]=cur.lastrowid
            session["nickname"]=nickname
            flash("회원가입이 완료되었습니다.")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("이미 가입된 이메일입니다.")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        pw=request.form["password"]
        conn=db()
        u=conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if u and check_password_hash(u["password_hash"], pw):
            session["user_id"]=u["id"]; session["nickname"]=u["nickname"]
            return redirect(url_for("index"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/sell", methods=["GET","POST"])
@login_required
def sell():
    if request.method=="POST":
        image=save_image(request.files.get("image"))
        conn=db()
        conn.execute("""INSERT INTO listings
          (user_id,title,category,brand,price,condition,shaft,flex,region,trade_method,description,image)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
            session["user_id"], request.form["title"], request.form["category"],
            request.form.get("brand",""), int(request.form["price"]),
            request.form.get("condition",""), request.form.get("shaft",""),
            request.form.get("flex",""), request.form.get("region",""),
            request.form.get("trade_method",""), request.form.get("description",""), image
          ))
        conn.commit(); conn.close()
        flash("상품이 등록되었습니다.")
        return redirect(url_for("index"))
    return render_template("sell.html")

@app.route("/item/<int:item_id>")
def item(item_id):
    conn=db()
    x=conn.execute("""SELECT listings.*, users.nickname,
      (SELECT COUNT(*) FROM favorites f WHERE f.listing_id=listings.id) fav_count
      FROM listings JOIN users ON users.id=listings.user_id WHERE listings.id=?""",(item_id,)).fetchone()
    conn.close()
    if not x: return "상품을 찾을 수 없습니다.",404
    return render_template("item.html", x=x)

@app.post("/favorite/<int:item_id>")
@login_required
def favorite(item_id):
    conn=db()
    exists=conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND listing_id=?",
                        (session["user_id"],item_id)).fetchone()
    if exists:
        conn.execute("DELETE FROM favorites WHERE user_id=? AND listing_id=?",(session["user_id"],item_id))
    else:
        conn.execute("INSERT OR IGNORE INTO favorites(user_id,listing_id) VALUES(?,?)",(session["user_id"],item_id))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for("index"))

@app.route("/my")
@login_required
def my():
    conn=db()
    mine=conn.execute("SELECT * FROM listings WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall()
    fav=conn.execute("""SELECT listings.* FROM listings
      JOIN favorites ON favorites.listing_id=listings.id
      WHERE favorites.user_id=? ORDER BY listings.id DESC""",(session["user_id"],)).fetchall()
    conn.close()
    return render_template("my.html", mine=mine, fav=fav)

@app.post("/status/<int:item_id>")
@login_required
def status(item_id):
    conn=db()
    item=conn.execute("SELECT * FROM listings WHERE id=?",(item_id,)).fetchone()
    if not item or item["user_id"]!=session["user_id"]:
        conn.close(); return "권한 없음",403
    new="판매완료" if item["status"]=="판매중" else "판매중"
    conn.execute("UPDATE listings SET status=? WHERE id=?",(new,item_id))
    conn.commit(); conn.close()
    return redirect(url_for("my"))

@app.post("/delete/<int:item_id>")
@login_required
def delete(item_id):
    conn=db()
    item=conn.execute("SELECT * FROM listings WHERE id=?",(item_id,)).fetchone()
    if not item or item["user_id"]!=session["user_id"]:
        conn.close(); return "권한 없음",403
    conn.execute("DELETE FROM favorites WHERE listing_id=?",(item_id,))
    conn.execute("DELETE FROM listings WHERE id=?",(item_id,))
    conn.commit(); conn.close()
    if item["image"]:
        p=os.path.join(UPLOAD_FOLDER,item["image"])
        if os.path.exists(p): os.remove(p)
    return redirect(url_for("my"))

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","5000")), debug=True)
