import os
import sqlite3
import secrets
from functools import wraps
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "bojjimi.db")

ADMIN_ID = os.environ.get("ADMIN_ID", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-1234")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bojjimi-change-this-secret")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        nickname TEXT NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS addresses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT DEFAULT 'ê¸°ë³¸ ë°°ì¡ì§',
        recipient TEXT NOT NULL,
        phone TEXT NOT NULL,
        postcode TEXT,
        address1 TEXT NOT NULL,
        address2 TEXT,
        is_default INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_type TEXT NOT NULL DEFAULT 'ê³µëêµ¬ë§¤',
        brand TEXT,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        subtitle TEXT,
        original_price INTEGER,
        sale_price INTEGER,
        image_url TEXT,
        buy_url TEXT,
        description TEXT,
        badge TEXT,
        status TEXT DEFAULT 'íë§¤ì¤',
        featured INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS favorites(
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS cart_items(
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, product_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        recipient TEXT NOT NULL,
        phone TEXT NOT NULL,
        postcode TEXT,
        address1 TEXT NOT NULL,
        address2 TEXT,
        subtotal INTEGER NOT NULL DEFAULT 0,
        shipping_fee INTEGER NOT NULL DEFAULT 0,
        total INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ì£¼ë¬¸ì ì',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        title TEXT NOT NULL,
        price INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS compare_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        brand TEXT,
        model_no TEXT,
        category TEXT,
        image_url TEXT,
        description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS compare_offers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        seller TEXT NOT NULL,
        price INTEGER NOT NULL,
        shipping INTEGER DEFAULT 0,
        buy_url TEXT NOT NULL,
        note TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(item_id) REFERENCES compare_items(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS vendors(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subtext TEXT,
        logo_text TEXT,
        url TEXT,
        sort_order INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
    );
    """)

    admin = conn.execute("SELECT * FROM admins WHERE username=?", (ADMIN_ID,)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO admins(username,password_hash) VALUES(?,?)",
            (ADMIN_ID, generate_password_hash(ADMIN_PASSWORD))
        )

    if conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"] == 0:
        conn.executemany(
            """INSERT INTO products(
                product_type,brand,category,title,subtitle,
                original_price,sale_price,image_url,buy_url,
                description,badge,status,featured
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                ("ê³µëêµ¬ë§¤","ìë§ì¥ë","ìí","ìë§ì¥ë ê¹ì¹","ì§ë°¥ì´ ìê°ëë ì ì± ê°ë ê¹ì¹",35000,29900,"","#","ìë§ì¥ë ëí ìíìëë¤.","ëíìí","íë§¤ì¤",1),
                ("ê³µëêµ¬ë§¤","ìë§ì¥ë","ìí","ìë§ê° ë§ë  ì¡°ì ê°ì¥","ê¹ê³  ê¹ëí ì íµ ì¥ë§",25000,22000,"","#","ì§ë°¥ì ê¸°ë³¸ì´ ëë ì¡°ì ê°ì¥ìëë¤.","ìë§ì¥ë","íë§¤ì¤",1),
                ("ê³µëêµ¬ë§¤","ìë§ì¥ë","ìí","ìë§ê° ë§ë  ëì¥","êµ¬ìíê³  ê¹ì ì§ëì¥",28000,25000,"","#","ì°ê°ì ë¬´ì¹¨ì ì ì´ì¸ë¦¬ë ëì¥ìëë¤.","ìë§ì¥ë","íë§¤ì¤",1),
                ("ê³µëêµ¬ë§¤","RUBIE","ë·°í°","RUBIE ì²ì°ì¤ì¼ ì¼ì´","ë£¨ë¹ì ë¸ëë ì¤ë¹ì¤",59000,39900,"","#","RUBIE ì²ì°ì¤ì¼ ê¸°ë° ë¼ì´í ë·°í° ì í ìììëë¤.","COMING SOON","ì¤ë¹ì¤",1),
            ]
        )

    if conn.execute("SELECT COUNT(*) c FROM compare_items").fetchone()["c"] == 0:
        items = [
            ("ë¤ì´ì¨ ìì´ë© ì»´íë¦¬í¸ ë¡±","Dyson","HS05","ë·°í°ê°ì ","","íë§¤ì²ë³ ì¤êµ¬ë§¤ê° ë¹êµ"),
            ("Apple ìì´í íë¡ 2ì¸ë","Apple","MTJV3KH/A","ê°ì ","","íë§¤ì²ë³ ì¤êµ¬ë§¤ê° ë¹êµ"),
        ]
        ids=[]
        for x in items:
            cur=conn.execute("INSERT INTO compare_items(title,brand,model_no,category,image_url,description) VALUES(?,?,?,?,?,?)",x)
            ids.append(cur.lastrowid)
        conn.executemany(
            "INSERT INTO compare_offers(item_id,seller,price,shipping,buy_url,note) VALUES(?,?,?,?,?,?)",
            [
                (ids[0],"Aëª°",548000,0,"#","ë¬´ë£ë°°ì¡"),
                (ids[0],"Bëª°",555000,0,"#","ì¹´ëí ì¸ ë³ë"),
                (ids[1],"Aëª°",269000,0,"#","ë¬´ë£ë°°ì¡"),
                (ids[1],"Bëª°",274000,2500,"#","ì¼ë°ë°°ì¡"),
            ]
        )

    if conn.execute("SELECT COUNT(*) c FROM vendors").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO vendors(name,subtext,logo_text,url,sort_order,active) VALUES(?,?,?,?,?,?)",
            [
                ("ì¿ í¡","ë¤ìí ìíì ë¹ ë¥´ê³  í¸ë¦¬íê²","coupang","#",1,1),
                ("ë¤ì´ë² ì¼í","ë¤ì´ë²ìì ì°¾ì ì¤ë§í¸í ì¼í","N","#",2,1),
                ("11ë²ê°","í¹ë³í ííì ë§ëë³´ì¸ì","11","#",3,1),
                ("Gë§ì¼","ëíë¯¼êµ­ ëí ì¨ë¼ì¸ ì¼íëª°","G","#",4,1),
                ("ìë§ì¥ë ê³µìëª°","ìë§ì¥ë ê³µì ì¤í ì´","ìë§ì¥ë","#",5,1),
                ("RUBIE ê³µìëª°","RUBIE ê³µì ì¤í ì´","RUBIE","#",6,1),
            ]
        )

    conn.commit()
    conn.close()


init_db()


def money(v):
    if v is None or v == "":
        return ""
    return f"{int(v):,}"

app.jinja_env.filters["money"] = money


def user_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("ë¡ê·¸ì¸ì´ íìí©ëë¤.")
            return redirect(url_for("login", next=request.path))
        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("ê´ë¦¬ì ë¡ê·¸ì¸ì´ íìí©ëë¤.")
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper


def user_counts():
    if not session.get("user_id"):
        return {"favorites":0, "cart":0}
    conn=db()
    fav=conn.execute("SELECT COUNT(*) c FROM favorites WHERE user_id=?",(session["user_id"],)).fetchone()["c"]
    cart=conn.execute("SELECT COALESCE(SUM(quantity),0) c FROM cart_items WHERE user_id=?",(session["user_id"],)).fetchone()["c"]
    conn.close()
    return {"favorites":fav,"cart":cart}


BASE_HTML = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | ë³´ì°ë¯¸</title>
<style>
*{box-sizing:border-box}:root{--pink:#ff2f78;--pink2:#ff6a93;--line:#ececef;--muted:#757b82;--bg:#fafafa;--dark:#20242a;--green:#19865b}
body{margin:0;background:var(--bg);color:#1f2328;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR",Arial,sans-serif}a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}
.top{background:#fff;border-bottom:1px solid var(--line)}.top-inner{max-width:1500px;margin:auto;padding:14px 22px;display:grid;grid-template-columns:250px minmax(300px,1fr) 330px;gap:20px;align-items:center}.logo-wrap{display:flex;align-items:center;gap:10px}.logo-icon{width:42px;height:42px;border:2px solid var(--pink);border-radius:13px;display:flex;align-items:center;justify-content:center;color:var(--pink);font-size:22px}.logo{color:var(--pink);font-size:30px;font-weight:950}.logo-sub{font-size:12px;font-weight:700}.search-main{display:flex;height:48px;border:1.5px solid #dcdce2;border-radius:8px;overflow:hidden}.search-main input{flex:1;border:0;outline:0;padding:0 16px}.search-main button{width:55px;border:0;background:linear-gradient(135deg,var(--pink),var(--pink2));color:#fff;font-size:20px}.quick-icons{display:flex;justify-content:flex-end;gap:23px}.quick-icons a{text-align:center;font-size:12px;font-weight:750;position:relative}.quick-icons b{display:block;font-size:22px;margin-bottom:3px;font-weight:500}.count{position:absolute;right:3px;top:-5px;background:var(--pink);color:white;border-radius:12px;min-width:18px;padding:2px 5px;font-size:10px}
.navbar{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:40}.navbar-inner{max-width:1500px;margin:auto;display:flex;align-items:center;padding:0 20px;overflow-x:auto}.navbar-inner a{padding:17px 18px;font-size:14px;font-weight:850;white-space:nowrap}.navbar-inner a:hover,.navbar-inner a:first-child{color:var(--pink)}
.page{max-width:1500px;margin:auto;padding:22px 20px 60px}.flash{max-width:1500px;margin:14px auto 0;background:#fff7d8;border:1px solid #eedf94;padding:10px 13px;border-radius:8px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:22px}.sidebar{position:sticky;top:76px}.hero{min-height:320px;border-radius:13px;background:linear-gradient(135deg,#fff7f9,#ffeef4);border:1px solid #ffe0ea;padding:42px 48px;display:grid;grid-template-columns:1.15fr .85fr;align-items:center}.hero h1{margin:0;font-size:44px;line-height:1.35;letter-spacing:-2px}.hero h1 strong{color:var(--pink)}.hero p{font-size:17px;color:#5a5d63;line-height:1.7}.hero-btn,.btn{display:inline-block;border:1px solid var(--line);background:#fff;border-radius:8px;padding:10px 14px;font-weight:900;cursor:pointer}.hero-btn,.btn.pink{background:var(--pink);border-color:var(--pink);color:#fff}.btn.dark{background:#222;border-color:#222;color:#fff}.btn.green{background:var(--green);border-color:var(--green);color:#fff}.btn.danger{background:#fff0f0;color:#a33;border-color:#efcccc}.hero-art{height:220px;display:flex;align-items:center;justify-content:center}.bag{width:160px;height:180px;background:linear-gradient(135deg,#ef91b0,#da5e89);border-radius:8px;color:white;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:950;box-shadow:0 18px 40px rgba(224,80,125,.22)}
.shortcuts{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:18px}.shortcut{background:#fff;border:1px solid var(--line);border-radius:10px;min-height:110px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:7px;text-align:center;font-weight:900}.ico{width:50px;height:50px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:23px;background:#ffe8f0}.section{margin-top:34px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:14px}.section-head h2{margin:0;font-size:24px}.muted{color:var(--muted);font-size:12px}.product-grid,.compare-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card,.compare-card{background:#fff;border:1px solid var(--line);border-radius:11px;overflow:hidden}.card-img{aspect-ratio:1/1;background:#f4f1ee;display:flex;align-items:center;justify-content:center;font-size:52px;overflow:hidden;position:relative}.card-img img{width:100%;height:100%;object-fit:cover}.badge{position:absolute;top:9px;left:9px;background:var(--pink);color:white;padding:5px 7px;border-radius:6px;font-size:10px;font-weight:900}.card-body{padding:13px}.tag{display:inline-block;background:#ffe4ee;color:var(--pink);padding:4px 6px;border-radius:5px;font-size:10px;font-weight:900}.card-title{font-size:14px;font-weight:900;min-height:38px;line-height:1.4;margin-top:7px}.sale{color:var(--pink);font-size:18px;font-weight:950;margin-top:8px}.original{color:#9ca0a5;font-size:12px;text-decoration:line-through}.card-actions{display:flex;gap:6px;margin-top:10px}.card-actions form{flex:1}.card-actions button{width:100%;padding:8px;border-radius:7px;border:1px solid var(--line);background:white}.compare-search{display:flex;border:1.5px solid #ffd4e2;border-radius:9px;overflow:hidden;background:white;height:48px}.compare-search input{flex:1;border:0;outline:0;padding:0 14px}.compare-search button{width:130px;border:0;background:var(--pink);color:white;font-weight:900}.compare-img{aspect-ratio:1.35/1;background:#f6f6f6;display:flex;align-items:center;justify-content:center;font-size:45px}.compare-body{padding:12px}.lowest{color:var(--pink);font-weight:950;margin-top:7px}.outline-btn{display:block;border:1px solid var(--pink);color:var(--pink);text-align:center;padding:8px;border-radius:6px;margin-top:9px;font-size:12px;font-weight:900}
.vendor-box,.panel,.form,.side-card,.admin-box,.offer-table{background:#fff;border:1px solid var(--line);border-radius:11px}.vendor-box{border:2px solid var(--pink);overflow:hidden}.vendor-head{padding:15px;border-bottom:1px solid var(--line)}.vendor-item{display:grid;grid-template-columns:55px 1fr;gap:11px;padding:13px;border-bottom:1px solid var(--line)}.vendor-logo{width:55px;height:55px;border-radius:10px;background:#f6f6f8;display:flex;align-items:center;justify-content:center;font-weight:950}.vendor-item h4{margin:0 0 4px}.vendor-item p{margin:0;font-size:11px;color:var(--muted)}.vendor-link{display:inline-block;background:#ff738b;color:white;border-radius:5px;padding:6px 12px;font-size:11px;font-weight:900;margin-top:6px}.side-card{padding:16px;margin-top:13px}.form{max-width:800px;margin:auto;padding:24px}.panel{padding:22px}.field{margin:14px 0}.field label{display:block;font-size:13px;font-weight:900;margin-bottom:7px}.field input,.field select,.field textarea{width:100%;padding:12px;border:1px solid #dadbe0;border-radius:8px}.field textarea{min-height:140px}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.table{background:white;border:1px solid var(--line);border-radius:11px;overflow:hidden}.tr{display:grid;grid-template-columns:1.4fr .8fr .8fr .8fr;gap:10px;padding:13px 15px;border-bottom:1px solid var(--line);align-items:center}.tr.head{background:#f6f6f8;font-weight:900}.empty{background:white;border:1px solid var(--line);border-radius:11px;padding:38px;text-align:center;color:var(--muted)}
.profile-grid{display:grid;grid-template-columns:230px 1fr;gap:18px}.profile-menu{background:white;border:1px solid var(--line);border-radius:11px;overflow:hidden}.profile-menu a{display:block;padding:13px 15px;border-bottom:1px solid var(--line);font-weight:800}.profile-menu a:hover{color:var(--pink);background:#fff7fa}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.summary .panel{text-align:center}.summary strong{display:block;font-size:25px;color:var(--pink);margin-top:5px}
footer{background:#1c1c1d;color:#d7d7da;margin-top:55px}.footer-inner{max-width:1500px;margin:auto;padding:32px 22px;display:grid;grid-template-columns:1.4fr repeat(3,1fr);gap:25px;font-size:12px;line-height:1.8}.footer-brand{font-size:20px;font-weight:950;color:#fff}.copyright{text-align:center;border-top:1px solid #333;padding:13px;font-size:11px;color:#999}
@media(max-width:1100px){.top-inner{grid-template-columns:220px 1fr}.quick-icons{display:none}.layout{grid-template-columns:1fr}.sidebar{position:static}.product-grid,.compare-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:720px){.top-inner{grid-template-columns:1fr;padding:11px}.logo-wrap{justify-content:center}.logo-sub{display:none}.page{padding:13px 11px 40px}.navbar-inner{padding:0 5px}.navbar-inner a{padding:15px 11px;font-size:12px}.hero{grid-template-columns:1fr;padding:28px 22px;min-height:auto}.hero h1{font-size:31px}.hero-art{height:150px}.bag{width:115px;height:130px;font-size:21px}.shortcuts{grid-template-columns:repeat(5,120px);overflow-x:auto}.row,.profile-grid{grid-template-columns:1fr}.summary{grid-template-columns:repeat(3,1fr)}.tr{grid-template-columns:1fr 1fr}.tr.head{display:none}.footer-inner{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<div class="top"><div class="top-inner">
<div class="logo-wrap"><div class="logo-icon">â¡</div><a class="logo" href="{{url_for('home')}}">ë³´ì°ë¯¸</a><span class="logo-sub">ì¢ì ì íì ì¢ì ê°ê²©ì</span></div>
<form class="search-main" action="{{url_for('compare')}}"><input name="q" placeholder="ìíëª, ë¸ëë, ëª¨ë¸ëªì ê²ìí´ë³´ì¸ì"><button>â</button></form>
<div class="quick-icons">
{% if session.get('user_id') %}<a href="{{url_for('mypage')}}"><b>â</b>{{session.get('nickname')}}ë</a>{% else %}<a href="{{url_for('login')}}"><b>â</b>ë¡ê·¸ì¸</a>{% endif %}
<a href="{{url_for('favorites_page')}}"><b>â¡</b>ì° ëª©ë¡{% if counts.favorites %}<span class="count">{{counts.favorites}}</span>{% endif %}</a>
<a href="{{url_for('cart')}}"><b>ð</b>ì¥ë°êµ¬ë{% if counts.cart %}<span class="count">{{counts.cart}}</span>{% endif %}</a>
</div></div></div>
<div class="navbar"><div class="navbar-inner"><a href="{{url_for('home')}}">ë³´ì°ë¯¸ í</a><a href="{{url_for('shop')}}">ì¤ëì ì° / ê³µëêµ¬ë§¤</a><a href="{{url_for('brand_page',brand='ìë§ì¥ë')}}">ìë§ì¥ë</a><a href="{{url_for('brand_page',brand='RUBIE')}}">RUBIE</a><a href="{{url_for('compare')}}">ìµì ê° ì°¾ê¸°</a>{% if session.get('user_id') %}<a href="{{url_for('orders')}}">ì£¼ë¬¸ë´ì­</a><a href="{{url_for('mypage')}}">ë§ì´íì´ì§</a>{% endif %}{% if session.get('admin') %}<a href="{{url_for('admin_dashboard')}}">ê´ë¦¬ì</a>{% endif %}</div></div>
{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
<div class="page">{{content|safe}}</div>
<footer><div class="footer-inner"><div><div class="footer-brand">ë³´ì°ë¯¸</div>ì¢ì ê²ë§ ê³¨ë¼ ì°.</div><div><b>íì¬ ì ë³´</b><br>íì¬ìê°<br>ì´ì©ì½ê´<br>ê°ì¸ì ë³´ì²ë¦¬ë°©ì¹¨</div><div><b>ê³ ê°ì¼í°</b><br>ê³µì§ì¬í­<br>1:1 ë¬¸ì<br>ìì£¼ ë¬»ë ì§ë¬¸</div><div><b>íí¸ë</b><br>íë§¤ì ì í´<br>ìì  ìë´<br>ê´ê³  ë¬¸ì</div></div><div class="copyright">Â© 2026 BOJJIMI</div></footer>
</body></html>'''


def page(title, body, **ctx):
    content=render_template_string(body, **ctx)
    return render_template_string(BASE_HTML, title=title, content=content, counts=user_counts())


def product_card(p):
    img=f'<img src="{p["image_url"]}" alt="">' if p["image_url"] else "ð"
    sale=f'{money(p["sale_price"])}ì' if p["sale_price"] else "ê°ê²©ë¬¸ì"
    original=f'<div class="original">ì ìê° {money(p["original_price"])}ì</div>' if p["original_price"] else ""
    badge=f'<div class="badge">{p["badge"]}</div>' if p["badge"] else ""
    actions=""
    if session.get("user_id"):
        actions=f'''<div class="card-actions"><form method="post" action="{url_for('favorite_toggle',product_id=p['id'])}"><button>â¡ ì°</button></form><form method="post" action="{url_for('cart_add',product_id=p['id'])}"><button>ð ë´ê¸°</button></form></div>'''
    return f'''<div class="card"><a href="{url_for('product_detail',product_id=p['id'])}"><div class="card-img">{badge}{img}</div><div class="card-body"><span class="tag">{p['brand'] or p['product_type']}</span><div class="card-title">{p['title']}</div><div class="sale">{sale}</div>{original}</div></a><div class="card-body" style="padding-top:0">{actions}</div></div>'''


@app.route("/")
def home():
    conn=db()
    products=conn.execute("SELECT * FROM products WHERE featured=1 ORDER BY id DESC LIMIT 4").fetchall()
    compares=conn.execute("SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c ORDER BY c.id DESC LIMIT 4").fetchall()
    vendors=conn.execute("SELECT * FROM vendors WHERE active=1 ORDER BY sort_order,id").fetchall()
    conn.close()
    return page("í", r'''
    <div class="layout"><main>
    <section class="hero"><div><h1>ì¢ì ì íì<br><strong>ì¢ì ì¬ëë¤ê³¼</strong><br>ì¢ì ê°ê²©ì</h1><p>ìë§ì¥ë Â· RUBIE Â· ê³µëêµ¬ë§¤ Â· ìµì ê° ë¹êµê¹ì§<br>ë³´ì°ë¯¸ìì í ë²ì.</p><a class="hero-btn" href="{{url_for('shop')}}">ì¤ëì ì° ë³´ë¬ê°ê¸°</a></div><div class="hero-art"><div class="bag">ë³´ì°ë¯¸</div></div></section>
    <div class="shortcuts"><a class="shortcut" href="{{url_for('shop')}}"><div class="ico">ð·</div>ì¤ëì ì°</a><a class="shortcut" href="{{url_for('brand_page',brand='ìë§ì¥ë')}}"><div class="ico">ðº</div>ìë§ì¥ë</a><a class="shortcut" href="{{url_for('brand_page',brand='RUBIE')}}"><div class="ico">ð¿</div>RUBIE</a><a class="shortcut" href="{{url_for('favorites_page')}}"><div class="ico">â¡</div>ì° ëª©ë¡</a><a class="shortcut" href="{{url_for('compare')}}"><div class="ico">â</div>ìµì ê° ì°¾ê¸°</a></div>
    <section class="section"><div class="section-head"><h2>ì¤ëì ì° / ê³µëêµ¬ë§¤</h2><a href="{{url_for('shop')}}">ì ì²´ ë³´ê¸° âº</a></div><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div></section>
    <section class="section"><div class="section-head"><h2>ìµì ê° ì°¾ê¸°</h2><a href="{{url_for('compare')}}">ì ì²´ ë³´ê¸° âº</a></div><div class="compare-grid">{% for x in compares %}<div class="compare-card"><div class="compare-img">ð</div><div class="compare-body"><b>{{x['title']}}</b><div class="lowest">{% if x['lowest'] %}{{x['lowest']|money}}ì~{% endif %}</div><a class="outline-btn" href="{{url_for('compare_detail',item_id=x['id'])}}">ìµì ê° ë³´ê¸°</a></div></div>{% endfor %}</div></section>
    </main><aside class="sidebar"><div class="vendor-box"><div class="vendor-head"><b>ë³´ì°ë¯¸ ì°ê²° ë²¤ë</b></div>{% for v in vendors %}<div class="vendor-item"><div class="vendor-logo">{{v['logo_text']}}</div><div><h4>{{v['name']}}</h4><p>{{v['subtext']}}</p><a class="vendor-link" href="{{v['url']}}" target="_blank">ë°ë¡ê°ê¸°</a></div></div>{% endfor %}</div><div class="side-card"><b>íì ë©ë´</b><div style="line-height:2;margin-top:8px">{% if session.get('user_id') %}<a href="{{url_for('mypage')}}">ë§ì´íì´ì§</a><br><a href="{{url_for('orders')}}">ì£¼ë¬¸ë´ì­</a><br><a href="{{url_for('addresses')}}">ë°°ì¡ì§ ê´ë¦¬</a>{% else %}<a href="{{url_for('register')}}">íìê°ì</a><br><a href="{{url_for('login')}}">ë¡ê·¸ì¸</a>{% endif %}</div></div></aside></div>
    ''',products=products,compares=compares,vendors=vendors,product_card=product_card)


@app.route("/shop")
def shop():
    conn=db(); products=conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall(); conn.close()
    return page("ì¼í",'<div class="section-head"><h2>ë³´ì°ë¯¸ ì¼í</h2></div><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div>',products=products,product_card=product_card)


@app.route("/brand/<brand>")
def brand_page(brand):
    conn=db(); products=conn.execute("SELECT * FROM products WHERE brand=? ORDER BY id DESC",(brand,)).fetchall(); conn.close()
    return page(brand,'<section class="hero" style="min-height:220px"><div><h1>{{brand}}</h1><p>{% if brand=="ìë§ì¥ë" %}ê¹ì¹ Â· ì¡°ì ê°ì¥ Â· ëì¥{% else %}RUBIE ë¼ì´í ë·°í° ë¸ëë{% endif %}</p></div><div class="hero-art"><div class="bag">{{brand}}</div></div></section><section class="section"><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div></section>',brand=brand,products=products,product_card=product_card)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn=db(); p=conn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone(); conn.close()
    if not p:return "ìíì ì°¾ì ì ììµëë¤.",404
    return page(p["title"],r'''<div class="row"><div class="card-img" style="border-radius:12px;min-height:430px">{% if p['image_url'] %}<img src="{{p['image_url']}}">{% else %}ð{% endif %}</div><div class="form" style="max-width:none;margin:0"><span class="tag">{{p['brand'] or p['product_type']}}</span><h1>{{p['title']}}</h1><div class="sale" style="font-size:29px">{% if p['sale_price'] %}{{p['sale_price']|money}}ì{% else %}ê°ê²©ë¬¸ì{% endif %}</div><p>{{p['subtitle'] or ''}}</p><div style="white-space:pre-wrap;line-height:1.8">{{p['description'] or ''}}</div><div class="actions" style="margin-top:20px">{% if session.get('user_id') %}<form method="post" action="{{url_for('favorite_toggle',product_id=p['id'])}}" style="display:inline"><button class="btn">â¡ ì°íê¸°</button></form><form method="post" action="{{url_for('cart_add',product_id=p['id'])}}" style="display:inline"><button class="btn pink">ð ì¥ë°êµ¬ë</button></form>{% endif %}{% if p['buy_url'] and p['buy_url']!='#' %}<a class="btn green" href="{{p['buy_url']}}" target="_blank">ì¸ë¶ êµ¬ë§¤ì²</a>{% endif %}</div></div></div>''',p=p)


# íìê°ì / ë¡ê·¸ì¸
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); nickname=request.form.get("nickname","").strip(); phone=request.form.get("phone","").strip(); pw=request.form.get("password","")
        if not email or not nickname or len(pw)<6:
            flash("ì´ë©ì¼Â·ëë¤ìì ìë ¥íê³  ë¹ë°ë²í¸ë 6ì ì´ìì¼ë¡ ì¤ì í´ì£¼ì¸ì."); return redirect(url_for("register"))
        conn=db()
        try:
            cur=conn.execute("INSERT INTO users(email,nickname,phone,password_hash) VALUES(?,?,?,?)",(email,nickname,phone,generate_password_hash(pw))); conn.commit()
            session["user_id"]=cur.lastrowid; session["nickname"]=nickname
            flash("ë³´ì°ë¯¸ íìê°ìì´ ìë£ëììµëë¤."); return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            flash("ì´ë¯¸ ê°ìë ì´ë©ì¼ìëë¤.")
        finally: conn.close()
    return page("íìê°ì",'''<div class="form"><h2>ë³´ì°ë¯¸ íìê°ì</h2><form method="post"><div class="field"><label>ì´ë©ì¼</label><input type="email" name="email" required></div><div class="field"><label>ëë¤ì</label><input name="nickname" required></div><div class="field"><label>í´ëí°</label><input name="phone"></div><div class="field"><label>ë¹ë°ë²í¸</label><input type="password" name="password" minlength="6" required></div><button class="btn pink" style="width:100%">íìê°ì</button></form></div>''')


@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        conn=db(); u=conn.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); conn.close()
        if u and check_password_hash(u["password_hash"],pw):
            session["user_id"]=u["id"]; session["nickname"]=u["nickname"]
            flash("ë¡ê·¸ì¸ëììµëë¤."); return redirect(request.args.get("next") or url_for("home"))
        flash("ì´ë©ì¼ ëë ë¹ë°ë²í¸ê° ì¬ë°ë¥´ì§ ììµëë¤.")
    return page("ë¡ê·¸ì¸",'''<div class="form"><h2>ë¡ê·¸ì¸</h2><form method="post"><div class="field"><label>ì´ë©ì¼</label><input type="email" name="email" required></div><div class="field"><label>ë¹ë°ë²í¸</label><input type="password" name="password" required></div><button class="btn pink" style="width:100%">ë¡ê·¸ì¸</button></form><p style="text-align:center"><a href="{{url_for('register')}}">ìì§ íìì´ ìëì ê°ì? íìê°ì</a></p></div>''')


@app.route("/logout")
def logout():
    session.pop("user_id",None); session.pop("nickname",None); flash("ë¡ê·¸ììëììµëë¤."); return redirect(url_for("home"))


@app.route("/mypage")
@user_required
def mypage():
    conn=db(); u=conn.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone(); fav=conn.execute("SELECT COUNT(*) c FROM favorites WHERE user_id=?",(u["id"],)).fetchone()["c"]; cartn=conn.execute("SELECT COALESCE(SUM(quantity),0)c FROM cart_items WHERE user_id=?",(u["id"],)).fetchone()["c"]; ordersn=conn.execute("SELECT COUNT(*)c FROM orders WHERE user_id=?",(u["id"],)).fetchone()["c"]; conn.close()
    return page("ë§ì´íì´ì§",'''<div class="profile-grid"><nav class="profile-menu"><a href="{{url_for('mypage')}}">ë§ì´íì´ì§</a><a href="{{url_for('favorites_page')}}">ì° ëª©ë¡</a><a href="{{url_for('cart')}}">ì¥ë°êµ¬ë</a><a href="{{url_for('orders')}}">ì£¼ë¬¸ë´ì­</a><a href="{{url_for('addresses')}}">ë°°ì¡ì§ ê´ë¦¬</a><a href="{{url_for('change_password')}}">ë¹ë°ë²í¸ ë³ê²½</a><a href="{{url_for('logout')}}">ë¡ê·¸ìì</a></nav><div><div class="panel"><h2>{{u['nickname']}}ë, ìëíì¸ì.</h2><div class="muted">{{u['email']}} Â· {{u['phone'] or 'í´ëí° ë¯¸ë±ë¡'}}</div></div><div class="summary" style="margin-top:12px"><div class="panel">ì°<strong>{{fav}}</strong></div><div class="panel">ì¥ë°êµ¬ë<strong>{{cartn}}</strong></div><div class="panel">ì£¼ë¬¸<strong>{{ordersn}}</strong></div></div><div class="panel" style="margin-top:12px"><h3>íì ê´ë¦¬</h3><form method="post" action="{{url_for('withdraw')}}" onsubmit="return confirm('ì ë§ íìíí´í ê¹ì? íìÂ·ì°Â·ì¥ë°êµ¬ëÂ·ì£¼ë¬¸ ë°ì´í°ê° ì­ì ë©ëë¤.')"><button class="btn danger">íì íí´</button></form></div></div></div>''',u=u,fav=fav,cartn=cartn,ordersn=ordersn)


@app.post("/favorite/<int:product_id>")
@user_required
def favorite_toggle(product_id):
    conn=db(); exists=conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND product_id=?",(session["user_id"],product_id)).fetchone()
    if exists: conn.execute("DELETE FROM favorites WHERE user_id=? AND product_id=?",(session["user_id"],product_id))
    else: conn.execute("INSERT OR IGNORE INTO favorites(user_id,product_id) VALUES(?,?)",(session["user_id"],product_id))
    conn.commit(); conn.close(); return redirect(request.referrer or url_for("shop"))


@app.route("/favorites")
@user_required
def favorites_page():
    conn=db(); items=conn.execute("SELECT p.* FROM products p JOIN favorites f ON f.product_id=p.id WHERE f.user_id=? ORDER BY f.created_at DESC",(session["user_id"],)).fetchall(); conn.close()
    return page("ì° ëª©ë¡",'<div class="section-head"><h2>ì° ëª©ë¡</h2></div>{% if items %}<div class="product-grid">{% for p in items %}{{product_card(p)|safe}}{% endfor %}</div>{% else %}<div class="empty">ì°í ìíì´ ììµëë¤.</div>{% endif %}',items=items,product_card=product_card)


@app.post("/cart/add/<int:product_id>")
@user_required
def cart_add(product_id):
    conn=db(); row=conn.execute("SELECT quantity FROM cart_items WHERE user_id=? AND product_id=?",(session["user_id"],product_id)).fetchone()
    if row: conn.execute("UPDATE cart_items SET quantity=quantity+1 WHERE user_id=? AND product_id=?",(session["user_id"],product_id))
    else: conn.execute("INSERT INTO cart_items(user_id,product_id,quantity) VALUES(?,?,1)",(session["user_id"],product_id))
    conn.commit(); conn.close(); flash("ì¥ë°êµ¬ëì ë´ììµëë¤."); return redirect(request.referrer or url_for("cart"))


@app.route("/cart")
@user_required
def cart():
    conn=db(); items=conn.execute("SELECT c.quantity,p.* FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=? ORDER BY c.created_at DESC",(session["user_id"],)).fetchall(); conn.close()
    subtotal=sum((x["sale_price"] or 0)*x["quantity"] for x in items)
    return page("ì¥ë°êµ¬ë",'''<div class="section-head"><h2>ì¥ë°êµ¬ë</h2></div>{% if items %}<div class="table">{% for x in items %}<div class="tr"><div><b>{{x['title']}}</b><div class="muted">{{x['brand'] or ''}}</div></div><div>{{x['sale_price']|money}}ì</div><div><form method="post" action="{{url_for('cart_update',product_id=x['id'])}}"><input style="width:65px;padding:7px" type="number" min="1" name="quantity" value="{{x['quantity']}}"><button class="btn">ë³ê²½</button></form></div><div><form method="post" action="{{url_for('cart_remove',product_id=x['id'])}}"><button class="btn danger">ì­ì </button></form></div></div>{% endfor %}</div><div class="panel" style="margin-top:15px;text-align:right"><b>ìí í©ê³ {{subtotal|money}}ì</b><br><a class="btn pink" style="margin-top:12px" href="{{url_for('checkout')}}">ì£¼ë¬¸íê¸°</a></div>{% else %}<div class="empty">ì¥ë°êµ¬ëê° ë¹ì´ ììµëë¤.</div>{% endif %}''',items=items,subtotal=subtotal)


@app.post("/cart/update/<int:product_id>")
@user_required
def cart_update(product_id):
    q=max(1,int(request.form.get("quantity",1))); conn=db(); conn.execute("UPDATE cart_items SET quantity=? WHERE user_id=? AND product_id=?",(q,session["user_id"],product_id)); conn.commit(); conn.close(); return redirect(url_for("cart"))


@app.post("/cart/remove/<int:product_id>")
@user_required
def cart_remove(product_id):
    conn=db(); conn.execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?",(session["user_id"],product_id)); conn.commit(); conn.close(); return redirect(url_for("cart"))


@app.route("/addresses",methods=["GET","POST"])
@user_required
def addresses():
    conn=db()
    if request.method=="POST":
        recipient=request.form.get("recipient","").strip(); phone=request.form.get("phone","").strip(); address1=request.form.get("address1","").strip()
        if recipient and phone and address1:
            default=1 if not conn.execute("SELECT 1 FROM addresses WHERE user_id=?",(session["user_id"],)).fetchone() else 0
            conn.execute("INSERT INTO addresses(user_id,label,recipient,phone,postcode,address1,address2,is_default) VALUES(?,?,?,?,?,?,?,?)",(session["user_id"],request.form.get("label","ê¸°ë³¸ ë°°ì¡ì§"),recipient,phone,request.form.get("postcode",""),address1,request.form.get("address2",""),default)); conn.commit(); flash("ë°°ì¡ì§ë¥¼ ì ì¥íìµëë¤.")
    rows=conn.execute("SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC,id DESC",(session["user_id"],)).fetchall(); conn.close()
    return page("ë°°ì¡ì§ ê´ë¦¬",'''<div class="row"><div class="form"><h2>ë°°ì¡ì§ ì¶ê°</h2><form method="post"><div class="field"><label>ë°°ì¡ì§ ì´ë¦</label><input name="label" value="ê¸°ë³¸ ë°°ì¡ì§"></div><div class="row"><div class="field"><label>ë°ë ë¶</label><input name="recipient" required></div><div class="field"><label>ì°ë½ì²</label><input name="phone" required></div></div><div class="field"><label>ì°í¸ë²í¸</label><input name="postcode"></div><div class="field"><label>ì£¼ì</label><input name="address1" required></div><div class="field"><label>ìì¸ì£¼ì</label><input name="address2"></div><button class="btn pink" style="width:100%">ì ì¥</button></form></div><div><h2>ì ì¥ë ë°°ì¡ì§</h2>{% for a in rows %}<div class="panel" style="margin-bottom:10px"><b>{{a['label']}} {% if a['is_default'] %}<span class="tag">ê¸°ë³¸</span>{% endif %}</b><p>{{a['recipient']}} Â· {{a['phone']}}</p><div>{{a['postcode']}} {{a['address1']}} {{a['address2']}}</div><form method="post" action="{{url_for('address_delete',address_id=a['id'])}}" style="margin-top:10px"><button class="btn danger">ì­ì </button></form></div>{% else %}<div class="empty">ì ì¥ë ë°°ì¡ì§ê° ììµëë¤.</div>{% endfor %}</div></div>''',rows=rows)


@app.post("/address/<int:address_id>/delete")
@user_required
def address_delete(address_id):
    conn=db(); conn.execute("DELETE FROM addresses WHERE id=? AND user_id=?",(address_id,session["user_id"])); conn.commit(); conn.close(); return redirect(url_for("addresses"))


@app.route("/checkout",methods=["GET","POST"])
@user_required
def checkout():
    conn=db(); cartrows=conn.execute("SELECT c.quantity,p.* FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=?",(session["user_id"],)).fetchall(); addr=conn.execute("SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC,id DESC LIMIT 1",(session["user_id"],)).fetchone()
    if not cartrows:
        conn.close(); flash("ì¥ë°êµ¬ëê° ë¹ì´ ììµëë¤."); return redirect(url_for("cart"))
    subtotal=sum((x["sale_price"] or 0)*x["quantity"] for x in cartrows); shipping=0; total=subtotal+shipping
    if request.method=="POST":
        recipient=request.form.get("recipient","").strip(); phone=request.form.get("phone","").strip(); address1=request.form.get("address1","").strip()
        if not recipient or not phone or not address1:
            conn.close(); flash("ë°°ì¡ ì ë³´ë¥¼ ëª¨ë ìë ¥í´ì£¼ì¸ì."); return redirect(url_for("checkout"))
        order_no=datetime.now().strftime("BJ%Y%m%d%H%M%S")+secrets.token_hex(2).upper()
        cur=conn.execute("INSERT INTO orders(order_no,user_id,recipient,phone,postcode,address1,address2,subtotal,shipping_fee,total) VALUES(?,?,?,?,?,?,?,?,?,?)",(order_no,session["user_id"],recipient,phone,request.form.get("postcode",""),address1,request.form.get("address2",""),subtotal,shipping,total)); oid=cur.lastrowid
        conn.executemany("INSERT INTO order_items(order_id,product_id,title,price,quantity) VALUES(?,?,?,?,?)",[(oid,x["id"],x["title"],x["sale_price"] or 0,x["quantity"]) for x in cartrows]); conn.execute("DELETE FROM cart_items WHERE user_id=?",(session["user_id"],)); conn.commit(); conn.close(); flash("ì£¼ë¬¸ì´ ì ìëììµëë¤. íì¬ ë²ì ì ê²°ì  ì°ë ì  ì£¼ë¬¸ì ì íì¤í¸ì©ìëë¤."); return redirect(url_for("order_detail",order_id=oid))
    conn.close()
    return page("ì£¼ë¬¸íê¸°",'''<div class="row"><div class="form"><h2>ë°°ì¡ ì ë³´</h2><form method="post"><div class="row"><div class="field"><label>ë°ë ë¶</label><input name="recipient" required value="{{addr['recipient'] if addr else ''}}"></div><div class="field"><label>ì°ë½ì²</label><input name="phone" required value="{{addr['phone'] if addr else ''}}"></div></div><div class="field"><label>ì°í¸ë²í¸</label><input name="postcode" value="{{addr['postcode'] if addr else ''}}"></div><div class="field"><label>ì£¼ì</label><input name="address1" required value="{{addr['address1'] if addr else ''}}"></div><div class="field"><label>ìì¸ì£¼ì</label><input name="address2" value="{{addr['address2'] if addr else ''}}"></div><button class="btn pink" style="width:100%">ì£¼ë¬¸ ì ì</button></form></div><div class="panel"><h2>ì£¼ë¬¸ ìì½</h2>{% for x in items %}<p>{{x['title']}} Ã {{x['quantity']}} <b style="float:right">{{((x['sale_price'] or 0)*x['quantity'])|money}}ì</b></p>{% endfor %}<hr><h3>ì´ {{total|money}}ì</h3><div class="muted">â» ì¹´ë/ê°í¸ê²°ì ë ë¤ì ë¨ê³ìì PG ì°ëì´ íìí©ëë¤.</div></div></div>''',items=cartrows,addr=addr,total=total)


@app.route("/orders")
@user_required
def orders():
    conn=db(); rows=conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall(); conn.close()
    return page("ì£¼ë¬¸ë´ì­",'''<div class="section-head"><h2>ì£¼ë¬¸ë´ì­</h2></div>{% if rows %}<div class="table"><div class="tr head"><div>ì£¼ë¬¸ë²í¸</div><div>ê¸ì¡</div><div>ìí</div><div>ì£¼ë¬¸ì¼</div></div>{% for o in rows %}<a class="tr" href="{{url_for('order_detail',order_id=o['id'])}}"><div><b>{{o['order_no']}}</b></div><div>{{o['total']|money}}ì</div><div>{{o['status']}}</div><div>{{o['created_at'][:10]}}</div></a>{% endfor %}</div>{% else %}<div class="empty">ì£¼ë¬¸ë´ì­ì´ ììµëë¤.</div>{% endif %}''',rows=rows)


@app.route("/order/<int:order_id>")
@user_required
def order_detail(order_id):
    conn=db(); o=conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?",(order_id,session["user_id"])).fetchone(); items=conn.execute("SELECT * FROM order_items WHERE order_id=?",(order_id,)).fetchall(); conn.close()
    if not o:return "ì£¼ë¬¸ì ì°¾ì ì ììµëë¤.",404
    return page("ì£¼ë¬¸ ìì¸",'''<div class="panel"><h2>ì£¼ë¬¸ {{o['order_no']}}</h2><p><b>ìí</b> {{o['status']}}</p><p><b>ë°°ì¡ì§</b> {{o['recipient']}} Â· {{o['phone']}}<br>{{o['postcode']}} {{o['address1']}} {{o['address2']}}</p><hr>{% for x in items %}<p>{{x['title']}} Ã {{x['quantity']}} <b style="float:right">{{(x['price']*x['quantity'])|money}}ì</b></p>{% endfor %}<hr><h3 style="text-align:right">ì´ {{o['total']|money}}ì</h3></div>''',o=o,items=items)


@app.route("/password",methods=["GET","POST"])
@user_required
def change_password():
    if request.method=="POST":
        current=request.form.get("current",""); new=request.form.get("new","")
        conn=db(); u=conn.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone()
        if not check_password_hash(u["password_hash"],current): flash("íì¬ ë¹ë°ë²í¸ê° ë§ì§ ììµëë¤.")
        elif len(new)<6: flash("ì ë¹ë°ë²í¸ë 6ì ì´ìì´ì´ì¼ í©ëë¤.")
        else: conn.execute("UPDATE users SET password_hash=? WHERE id=?",(generate_password_hash(new),u["id"])); conn.commit(); flash("ë¹ë°ë²í¸ê° ë³ê²½ëììµëë¤.")
        conn.close()
    return page("ë¹ë°ë²í¸ ë³ê²½",'''<div class="form"><h2>ë¹ë°ë²í¸ ë³ê²½</h2><form method="post"><div class="field"><label>íì¬ ë¹ë°ë²í¸</label><input type="password" name="current" required></div><div class="field"><label>ì ë¹ë°ë²í¸</label><input type="password" name="new" minlength="6" required></div><button class="btn pink" style="width:100%">ë³ê²½</button></form></div>''')


@app.post("/withdraw")
@user_required
def withdraw():
    uid=session["user_id"]; conn=db(); conn.execute("DELETE FROM users WHERE id=?",(uid,)); conn.commit(); conn.close(); session.clear(); flash("íìíí´ê° ìë£ëììµëë¤."); return redirect(url_for("home"))


# ê°ê²© ë¹êµ
@app.route("/compare")
def compare():
    q=request.args.get("q","").strip(); conn=db()
    if q:
        like=f"%{q}%"; items=conn.execute("SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c WHERE c.title LIKE ? OR c.brand LIKE ? OR c.model_no LIKE ? ORDER BY c.id DESC",(like,like,like)).fetchall()
    else: items=conn.execute("SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c ORDER BY c.id DESC").fetchall()
    conn.close(); return page("ìµì ê° ì°¾ê¸°",'''<div class="section-head"><h2>ìµì ê° ì°¾ê¸°</h2></div><form class="compare-search"><input name="q" value="{{q}}" placeholder="ìíëª, ë¸ëë, ëª¨ë¸ë²í¸"><button>ê²ì</button></form><div class="compare-grid" style="margin-top:15px">{% for x in items %}<div class="compare-card"><div class="compare-img">ð</div><div class="compare-body"><b>{{x['title']}}</b><div class="muted">{{x['brand']}} {{x['model_no']}}</div><div class="lowest">{% if x['lowest'] %}{{x['lowest']|money}}ì~{% endif %}</div><a class="outline-btn" href="{{url_for('compare_detail',item_id=x['id'])}}">ë¹êµ ë³´ê¸°</a></div></div>{% endfor %}</div>''',items=items,q=q)


@app.route("/compare/<int:item_id>")
def compare_detail(item_id):
    conn=db(); item=conn.execute("SELECT * FROM compare_items WHERE id=?",(item_id,)).fetchone(); offers=conn.execute("SELECT *,price+shipping total FROM compare_offers WHERE item_id=? ORDER BY total ASC,id ASC",(item_id,)).fetchall(); conn.close()
    if not item:return "ìíì ì°¾ì ì ììµëë¤.",404
    best=offers[0]["total"] if offers else None
    return page(item["title"],'''<div class="section-head"><h2>{{item['title']}}</h2></div><div class="table"><div class="tr head"><div>íë§¤ì²</div><div>ìíê°</div><div>ë°°ì¡ë¹</div><div>ì¤êµ¬ë§¤ê°</div></div>{% for o in offers %}<div class="tr"><div><b>{{o['seller']}}</b>{% if o['total']==best %} <span class="tag">ìµì ê°</span>{% endif %}<div class="muted">{{o['note']}}</div></div><div>{{o['price']|money}}ì</div><div>{% if o['shipping'] %}{{o['shipping']|money}}ì{% else %}ë¬´ë£{% endif %}</div><div><b>{{o['total']|money}}ì</b></div></div>{% endfor %}</div>''',item=item,offers=offers,best=best)


# ê´ë¦¬ì
@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        conn=db(); a=conn.execute("SELECT * FROM admins WHERE username=?",(request.form.get("username",""),)).fetchone(); conn.close()
        if a and check_password_hash(a["password_hash"],request.form.get("password","")): session["admin"]=True; return redirect(url_for("admin_dashboard"))
        flash("ê´ë¦¬ì ìì´ë ëë ë¹ë°ë²í¸ê° ì¬ë°ë¥´ì§ ììµëë¤.")
    return page("ê´ë¦¬ì ë¡ê·¸ì¸",'''<div class="form"><h2>ê´ë¦¬ì ë¡ê·¸ì¸</h2><form method="post"><div class="field"><label>ìì´ë</label><input name="username"></div><div class="field"><label>ë¹ë°ë²í¸</label><input type="password" name="password"></div><button class="btn dark" style="width:100%">ë¡ê·¸ì¸</button></form></div>''')


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn=db(); usersn=conn.execute("SELECT COUNT(*)c FROM users").fetchone()["c"]; ordersn=conn.execute("SELECT COUNT(*)c FROM orders").fetchone()["c"]; productsn=conn.execute("SELECT COUNT(*)c FROM products").fetchone()["c"]; conn.close()
    return page("ê´ë¦¬ì",'''<div class="section-head"><h2>ë³´ì°ë¯¸ ê´ë¦¬ì</h2></div><div class="summary"><div class="panel">íì<strong>{{usersn}}</strong></div><div class="panel">ìí<strong>{{productsn}}</strong></div><div class="panel">ì£¼ë¬¸<strong>{{ordersn}}</strong></div></div><div class="panel" style="margin-top:15px"><a class="btn pink" href="{{url_for('admin_users')}}">íìê´ë¦¬</a> <a class="btn" href="{{url_for('shop')}}">ìíë³´ê¸°</a></div>''',usersn=usersn,ordersn=ordersn,productsn=productsn)


@app.route("/admin/users")
@admin_required
def admin_users():
    conn=db(); rows=conn.execute("SELECT u.*,(SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id) order_count FROM users u ORDER BY u.id DESC").fetchall(); conn.close()
    return page("íìê´ë¦¬",'''<div class="section-head"><h2>íìê´ë¦¬</h2></div><div class="table"><div class="tr head"><div>íì</div><div>ì´ë©ì¼</div><div>í´ëí°</div><div>ì£¼ë¬¸</div></div>{% for u in rows %}<div class="tr"><div><b>{{u['nickname']}}</b></div><div>{{u['email']}}</div><div>{{u['phone'] or '-'}}</div><div>{{u['order_count']}}ê±´</div></div>{% endfor %}</div>''',rows=rows)


if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")),debug=False)
