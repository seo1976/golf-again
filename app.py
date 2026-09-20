import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bojjimi-dev-change-this-key")
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "bojjimi.db"))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()

CATEGORIES = ["두피·헤어", "페이스", "바디", "천연오일", "세트"]
ORDER_STATUSES = ["주문접수", "입금확인", "상품준비", "배송중", "배송완료", "취소"]


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def now():
    return datetime.now().isoformat(timespec="minutes")


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
      role TEXT NOT NULL DEFAULT 'customer', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
      short_desc TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
      ingredients TEXT NOT NULL DEFAULT '', usage TEXT NOT NULL DEFAULT '',
      caution TEXT NOT NULL DEFAULT '', price INTEGER NOT NULL DEFAULT 0,
      sale_price INTEGER, stock INTEGER NOT NULL DEFAULT 0, image_url TEXT NOT NULL DEFAULT '',
      badge TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft',
      featured INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS orders(
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_no TEXT UNIQUE NOT NULL, user_id INTEGER,
      buyer_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
      postcode TEXT NOT NULL DEFAULT '', address1 TEXT NOT NULL, address2 TEXT NOT NULL DEFAULT '',
      memo TEXT NOT NULL DEFAULT '', payment_method TEXT NOT NULL DEFAULT 'bank',
      subtotal INTEGER NOT NULL, shipping_fee INTEGER NOT NULL, total INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT '주문접수', created_at TEXT NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS order_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
      product_name TEXT NOT NULL, unit_price INTEGER NOT NULL, quantity INTEGER NOT NULL,
      FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
      FOREIGN KEY(product_id) REFERENCES products(id)
    );
    """)
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        con.execute("""INSERT INTO products(
          name,category,short_desc,description,ingredients,usage,caution,price,sale_price,
          stock,image_url,badge,status,featured,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
          "RUBIE 보태니컬 두피 샴푸", "두피·헤어",
          "풍성한 거품과 부드러운 마무리를 연구 중인 루비에 첫 제품",
          "루비에의 첫 번째 두피·헤어 제품입니다. 현재 정식 판매 전 처방과 표시사항을 검토하고 있습니다.",
          "정식 처방 확정 후 공개 예정",
          "미온수로 두피와 모발을 적신 뒤 적당량을 거품 내어 마사지하고 깨끗하게 헹굽니다.",
          "사용 중 또는 사용 후 이상 증상이 있으면 사용을 중지하고 전문가와 상담하세요.",
          0, None, 0, "", "COMING SOON", "coming", 1, now(), now()
        ))
    con.commit()
    con.close()


init_db()


def won(value):
    return f"{int(value or 0):,}원"


app.jinja_env.filters["won"] = won


def current_user():
    if not session.get("user_id"):
        return None
    con = db()
    user = con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    con.close()
    return user


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("로그인이 필요합니다.")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user["role"] != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapped


def cart_data():
    raw = session.get("cart", {})
    cart = {str(k): max(1, int(v)) for k, v in raw.items() if str(k).isdigit()}
    if not cart:
        return [], 0, 0, 0
    ids = [int(i) for i in cart]
    con = db()
    products = con.execute(
        f"SELECT * FROM products WHERE id IN ({','.join('?' for _ in ids)}) AND status='active'", ids
    ).fetchall()
    con.close()
    items, subtotal = [], 0
    for product in products:
        quantity = min(cart[str(product["id"])], max(0, product["stock"]))
        if quantity < 1:
            continue
        unit_price = product["sale_price"] if product["sale_price"] is not None else product["price"]
        line_total = unit_price * quantity
        subtotal += line_total
        items.append({"product": product, "quantity": quantity, "unit_price": unit_price, "line_total": line_total})
    shipping = 0 if subtotal == 0 or subtotal >= 50000 else 3000
    return items, subtotal, shipping, subtotal + shipping


BASE = """
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="RUBIE 자연유래 화장품을 만나는 보찌미 공식몰"><title>{{title}} | BOJJIMI</title>
<style>
*{box-sizing:border-box}:root{--rose:#a44b64;--deep:#4d2934;--blush:#f8edf0;--cream:#fffaf6;--line:#eadde0;--ink:#30272a;--muted:#74686c;--white:#fff}
html{scroll-behavior:smooth}body{margin:0;background:var(--cream);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif;line-height:1.58}a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}
.announcement{background:var(--deep);color:#fff;text-align:center;padding:8px 16px;font-size:12px}.top{position:sticky;top:0;z-index:30;background:#fffdfacc;border-bottom:1px solid var(--line);backdrop-filter:blur(14px)}.topin{max-width:1180px;height:74px;margin:auto;padding:0 22px;display:flex;align-items:center;gap:24px}.logo{font-family:Georgia,serif;font-weight:700;font-size:26px;letter-spacing:3px;color:var(--deep)}.logo small{display:block;font:600 9px Arial,sans-serif;letter-spacing:2.4px;color:var(--rose);text-align:center}.nav{margin-left:auto;display:flex;align-items:center;gap:22px;font-size:14px;font-weight:700}.cart-count{background:var(--rose);color:#fff;border-radius:99px;padding:1px 6px;font-size:11px}
.page{max-width:1180px;margin:auto;padding:34px 22px 84px}.flash{max-width:1180px;margin:12px auto 0;padding:12px 18px;background:#fff;border:1px solid #e5c7cf;border-radius:12px;color:var(--deep)}
.hero{min-height:560px;border-radius:32px;padding:64px;display:grid;grid-template-columns:1.08fr .92fr;align-items:center;gap:42px;background:radial-gradient(circle at 80% 20%,#f5dce3 0 14%,transparent 15%),linear-gradient(135deg,#fff 0%,#f9e8ed 58%,#ead4ca 100%);overflow:hidden}.eyebrow{font-size:12px;font-weight:900;letter-spacing:2px;color:var(--rose)}h1,h2,h3{line-height:1.2;letter-spacing:-.5px}.hero h1{font-family:Georgia,"Noto Serif KR",serif;font-size:58px;margin:13px 0 20px;color:var(--deep)}.hero p{font-size:18px;color:var(--muted);max-width:580px}.hero-art{aspect-ratio:1;border-radius:50% 50% 42% 58%;background:linear-gradient(145deg,#a44b64,#d8a9b6);display:grid;place-items:center;box-shadow:0 32px 70px #6e34464a;color:#fff;text-align:center}.hero-art b{font-family:Georgia,serif;font-size:52px;letter-spacing:6px}.hero-art span{display:block;font-size:12px;letter-spacing:3px;margin-top:8px}
.btn{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:999px;padding:13px 21px;background:var(--rose);color:#fff;font-weight:800;cursor:pointer}.btn.ghost{background:#fff;color:var(--deep);border:1px solid var(--line)}.btn.dark{background:var(--deep)}.btn.small{padding:9px 14px;font-size:13px}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:25px}
.section{padding:58px 0}.section-head{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:24px}.section h2{font-family:Georgia,"Noto Serif KR",serif;font-size:36px;margin:6px 0}.lead{color:var(--muted);margin:0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.card{background:#fff;border:1px solid var(--line);border-radius:22px;overflow:hidden}.product-visual{aspect-ratio:1;background:linear-gradient(145deg,#f8e9ed,#e9d7ce);display:grid;place-items:center;position:relative}.product-visual img{width:100%;height:100%;object-fit:cover}.bottle{width:34%;height:62%;border-radius:28px 28px 16px 16px;background:linear-gradient(120deg,#653e49,#a45a6d);box-shadow:0 18px 34px #6d3a4933;display:grid;place-items:center;color:#fff;font-family:Georgia,serif;letter-spacing:3px}.badge{position:absolute;top:15px;left:15px;padding:6px 10px;border-radius:999px;background:#fff;color:var(--rose);font-size:11px;font-weight:900}.card-body{padding:20px}.category{font-size:12px;color:var(--rose);font-weight:800}.card h3{margin:7px 0;font-size:20px}.price{font-size:20px;font-weight:900;margin-top:14px}.old-price{text-decoration:line-through;color:#aaa;font-size:13px;margin-left:5px}.muted{color:var(--muted)}
.values{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.value{background:#fff;border:1px solid var(--line);border-radius:20px;padding:25px}.value .num{color:var(--rose);font:700 30px Georgia,serif}.value h3{margin:8px 0}.story{background:var(--deep);color:#fff;border-radius:28px;padding:46px;display:grid;grid-template-columns:1fr 1fr;gap:38px}.story p{color:#e9dfe2}.story-note{border:1px solid #ffffff2e;background:#ffffff0d;border-radius:20px;padding:22px}
.shopbar{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:22px}.filters{display:flex;gap:8px;flex-wrap:wrap}.pill{padding:9px 14px;border-radius:999px;border:1px solid var(--line);background:#fff;font-size:13px}.pill.active{background:var(--deep);color:#fff;border-color:var(--deep)}
.detail{display:grid;grid-template-columns:1fr 1fr;gap:48px}.detail .product-visual{border-radius:28px}.detail h1{font-family:Georgia,"Noto Serif KR",serif;font-size:42px}.detail-price{font-size:28px;font-weight:900}.info-table{border-top:1px solid var(--line);margin-top:24px}.info-row{display:grid;grid-template-columns:130px 1fr;padding:15px 0;border-bottom:1px solid var(--line);gap:12px}.qty{width:82px;padding:10px;border:1px solid var(--line);border-radius:10px}
.formbox{max-width:760px;margin:auto;background:#fff;border:1px solid var(--line);border-radius:24px;padding:30px}.field{margin-bottom:16px}.field label{display:block;font-weight:800;font-size:13px;margin-bottom:7px}.field input,.field select,.field textarea{width:100%;padding:13px;border:1px solid #dbcdd1;border-radius:11px;background:#fff}.field textarea{min-height:110px;resize:vertical}.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.notice{background:var(--blush);border-left:4px solid var(--rose);padding:14px 16px;border-radius:10px;color:var(--deep)}
.cart-row{display:grid;grid-template-columns:86px 1fr 100px 120px auto;gap:16px;align-items:center;background:#fff;border-bottom:1px solid var(--line);padding:18px}.thumb{width:86px;height:86px;border-radius:15px;background:linear-gradient(145deg,#f8e9ed,#e9d7ce);display:grid;place-items:center;color:var(--rose);font:700 12px Georgia,serif}.summary{margin-left:auto;max-width:420px;background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px}.summary-line{display:flex;justify-content:space-between;padding:8px 0}.summary-line.total{border-top:1px solid var(--line);margin-top:8px;padding-top:15px;font-size:20px;font-weight:900}
.order-card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:20px;margin-bottom:14px}.order-head{display:flex;justify-content:space-between;gap:15px}.status{padding:5px 10px;background:#edf4ee;color:#4f6d57;border-radius:999px;font-size:12px;font-weight:900}table{width:100%;border-collapse:collapse;background:#fff;border-radius:16px;overflow:hidden}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);font-size:13px}th{background:var(--blush)}.admin-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}.kpi{background:#fff;border:1px solid var(--line);border-radius:18px;padding:20px}.kpi b{display:block;font-size:28px;color:var(--deep)}
footer{background:#2e2025;color:#d9ccd0;padding:46px 22px}.footerin{max-width:1180px;margin:auto;display:flex;justify-content:space-between;gap:34px}.footer-logo{color:#fff;font:700 24px Georgia,serif;letter-spacing:3px}.small{font-size:12px}.center{text-align:center}.empty{padding:52px 20px;text-align:center;background:#fff;border:1px solid var(--line);border-radius:20px}.mobile-nav{display:none}
@media(max-width:820px){.topin{height:64px;padding:0 15px}.nav a.hide-m{display:none}.hero{min-height:auto;grid-template-columns:1fr;padding:34px 24px;border-radius:22px}.hero h1{font-size:42px}.hero-art{max-width:360px;margin:auto;width:100%}.grid,.values{grid-template-columns:repeat(2,1fr)}.story,.detail{grid-template-columns:1fr}.page{padding:22px 14px 105px}.section{padding:40px 0}.section h2{font-size:30px}.row{grid-template-columns:1fr}.cart-row{grid-template-columns:70px 1fr auto}.cart-row .cart-price,.cart-row .cart-qty{grid-column:2}.cart-row .thumb{width:70px;height:70px}.admin-grid{grid-template-columns:repeat(2,1fr)}.footerin{display:block}table{display:block;overflow-x:auto}.mobile-nav{display:flex;position:fixed;left:12px;right:12px;bottom:10px;z-index:40;background:#fff;border:1px solid var(--line);box-shadow:0 10px 30px #301d2633;border-radius:18px;padding:9px;justify-content:space-around;font-size:12px;font-weight:800}.mobile-nav a{text-align:center}.mobile-nav span{display:block;font-size:18px}}
@media(max-width:520px){.grid,.values{grid-template-columns:1fr}.hero h1{font-size:36px}.hero-art b{font-size:42px}.detail h1{font-size:34px}.section-head{align-items:start;flex-direction:column}.formbox{padding:22px 18px}}
</style></head><body>
<div class="announcement">자연에서 찾은 균형 · 정직하게 확인된 정보만 전합니다</div>
<header class="top"><div class="topin"><a class="logo" href="{{url_for('home')}}">BOJJIMI<small>RUBIE COSMETICS</small></a><nav class="nav"><a class="hide-m" href="{{url_for('shop')}}">제품</a><a class="hide-m" href="{{url_for('brand')}}">브랜드</a>{% if user %}<a class="hide-m" href="{{url_for('mypage')}}">마이페이지</a>{% if user['role']=='admin' %}<a href="{{url_for('admin')}}">관리자</a>{% endif %}<a class="hide-m" href="{{url_for('logout')}}">로그아웃</a>{% else %}<a class="hide-m" href="{{url_for('login')}}">로그인</a>{% endif %}<a href="{{url_for('cart')}}">장바구니 <span class="cart-count">{{cart_count}}</span></a></nav></div></header>
{% with messages=get_flashed_messages() %}{% for message in messages %}<div class="flash">{{message}}</div>{% endfor %}{% endwith %}<main class="page">{{body|safe}}</main>
<footer><div class="footerin"><div><div class="footer-logo">BOJJIMI</div><p class="small">RUBIE의 자연유래 화장품을 소개하는 공식 온라인 스토어</p></div><div class="small">고객센터·사업자정보·통신판매업 정보는 판매 개시 전 확정해 표시하세요.<br>© 2026 BOJJIMI. All rights reserved.</div></div></footer>
<nav class="mobile-nav"><a href="{{url_for('home')}}"><span>⌂</span>홈</a><a href="{{url_for('shop')}}"><span>◫</span>제품</a><a href="{{url_for('cart')}}"><span>🛒</span>장바구니</a><a href="{{url_for('mypage') if user else url_for('login')}}"><span>○</span>마이</a></nav></body></html>
"""


def page(title, body, **context):
    cart_count = sum(int(v) for v in session.get("cart", {}).values())
    return render_template_string(BASE, title=title, body=body, user=current_user(), cart_count=cart_count, **context)


@app.route("/")
def home():
    con = db()
    products = con.execute("SELECT * FROM products WHERE status IN ('active','coming') ORDER BY featured DESC,id DESC LIMIT 6").fetchall()
    con.close()
    body = render_template_string("""
    <section class="hero"><div><div class="eyebrow">BOJJIMI × RUBIE</div><h1>나를 위한<br>정직한 아름다움</h1><p>자연유래 원료의 장점과 편안한 사용감을 함께 고민합니다. 과장된 약속 대신 확인된 정보와 섬세한 제품 경험을 전합니다.</p><div class="actions"><a class="btn" href="{{url_for('shop')}}">제품 만나보기</a><a class="btn ghost" href="{{url_for('brand')}}">루비에 이야기</a></div></div><div class="hero-art"><div><b>RUBIE</b><span>NATURAL BALANCE</span></div></div></section>
    <section class="section"><div class="section-head"><div><div class="eyebrow">OUR PRODUCTS</div><h2>루비에 제품</h2><p class="lead">두피부터 피부까지, 매일 편안하게 사용할 제품을 준비합니다.</p></div><a class="btn ghost small" href="{{url_for('shop')}}">전체 보기</a></div>
    {% if products %}<div class="grid">{% for p in products %}<a class="card" href="{{url_for('product_detail',product_id=p['id'])}}"><div class="product-visual">{% if p['image_url'] %}<img src="{{p['image_url']}}" alt="{{p['name']}}">{% else %}<div class="bottle">R</div>{% endif %}{% if p['badge'] %}<span class="badge">{{p['badge']}}</span>{% endif %}</div><div class="card-body"><div class="category">{{p['category']}}</div><h3>{{p['name']}}</h3><p class="muted">{{p['short_desc']}}</p>{% if p['status']=='active' %}<div class="price">{{(p['sale_price'] if p['sale_price'] is not none else p['price'])|won}}{% if p['sale_price'] is not none %}<span class="old-price">{{p['price']|won}}</span>{% endif %}</div>{% else %}<div class="price" style="color:var(--rose)">출시 준비 중</div>{% endif %}</div></a>{% endfor %}</div>{% else %}<div class="empty">첫 제품을 준비하고 있습니다.</div>{% endif %}</section>
    <section class="section"><div class="values"><div class="value"><div class="num">01</div><h3>확인된 정보</h3><p class="muted">근거 없이 효능을 과장하지 않고 제품의 실제 역할을 분명하게 안내합니다.</p></div><div class="value"><div class="num">02</div><h3>편안한 사용감</h3><p class="muted">매일 손이 가는 향, 제형과 마무리감을 중요하게 생각합니다.</p></div><div class="value"><div class="num">03</div><h3>책임 있는 판매</h3><p class="muted">전성분, 사용법과 주의사항을 투명하게 공개합니다.</p></div></div></section>
    <section class="section story"><div><div class="eyebrow" style="color:#e8b7c4">RUBIE STORY</div><h2>좋은 원료만큼<br>중요한 것은 균형입니다.</h2><p>루비에는 자연유래 원료를 맹목적으로 강조하지 않습니다. 안전성, 안정성, 사용감과 필요한 기능이 조화를 이루는 제품을 지향합니다.</p></div><div class="story-note"><b>현재 준비 중인 첫 제품</b><h3>보태니컬 두피 샴푸</h3><p>풍성한 거품과 만족스러운 향은 살리고, 세정 후 뻣뻣함을 줄이는 방향으로 정식 제품화를 준비하고 있습니다.</p></div></section>
    """, products=products)
    return page("루비에 공식 화장품몰", body)


@app.route("/shop")
def shop():
    category, query = request.args.get("category", "").strip(), request.args.get("q", "").strip()
    sql, params = "SELECT * FROM products WHERE status IN ('active','coming')", []
    if category in CATEGORIES:
        sql += " AND category=?"; params.append(category)
    if query:
        sql += " AND (name LIKE ? OR short_desc LIKE ? OR description LIKE ?)"; params.extend([f"%{query}%"]*3)
    con = db(); products = con.execute(sql + " ORDER BY featured DESC,id DESC", params).fetchall(); con.close()
    body = render_template_string("""
    <section class="section" style="padding-top:12px"><div class="eyebrow">RUBIE SHOP</div><h2>제품</h2><div class="shopbar"><div class="filters"><a class="pill {{'active' if not category else ''}}" href="{{url_for('shop')}}">전체</a>{% for c in categories %}<a class="pill {{'active' if category==c else ''}}" href="{{url_for('shop',category=c)}}">{{c}}</a>{% endfor %}</div><form><input name="q" value="{{query}}" placeholder="제품 검색" style="padding:10px 13px;border:1px solid var(--line);border-radius:999px"><button class="btn small">검색</button></form></div>
    {% if products %}<div class="grid">{% for p in products %}<a class="card" href="{{url_for('product_detail',product_id=p['id'])}}"><div class="product-visual">{% if p['image_url'] %}<img src="{{p['image_url']}}" alt="{{p['name']}}">{% else %}<div class="bottle">R</div>{% endif %}{% if p['badge'] %}<span class="badge">{{p['badge']}}</span>{% endif %}</div><div class="card-body"><div class="category">{{p['category']}}</div><h3>{{p['name']}}</h3><p class="muted">{{p['short_desc']}}</p>{% if p['status']=='active' %}<div class="price">{{(p['sale_price'] if p['sale_price'] is not none else p['price'])|won}}</div>{% else %}<div class="price" style="color:var(--rose)">출시 준비 중</div>{% endif %}</div></a>{% endfor %}</div>{% else %}<div class="empty">조건에 맞는 제품이 없습니다.</div>{% endif %}</section>
    """, products=products, categories=CATEGORIES, category=category, query=query)
    return page("제품", body)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    con = db(); product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone(); con.close()
    user = current_user()
    if not product or (product["status"] == "draft" and (not user or user["role"] != "admin")):
        abort(404)
    body = render_template_string("""
    <section class="detail"><div class="product-visual">{% if p['image_url'] %}<img src="{{p['image_url']}}" alt="{{p['name']}}">{% else %}<div class="bottle">R</div>{% endif %}{% if p['badge'] %}<span class="badge">{{p['badge']}}</span>{% endif %}</div><div><div class="category">{{p['category']}}</div><h1>{{p['name']}}</h1><p class="lead">{{p['short_desc']}}</p>{% if p['status']=='active' %}<p class="detail-price">{{(p['sale_price'] if p['sale_price'] is not none else p['price'])|won}}</p><form method="post" action="{{url_for('add_cart',product_id=p['id'])}}"><input class="qty" type="number" name="quantity" value="1" min="1" max="{{p['stock']}}"><button class="btn dark" {% if p['stock']<1 %}disabled{% endif %}>{{'장바구니 담기' if p['stock']>0 else '품절'}}</button></form>{% else %}<div class="notice" style="margin-top:24px">정식 판매 전 처방·표시사항·품질 검토 단계입니다. 판매가 시작되면 가격과 전성분을 공개합니다.</div>{% endif %}
    <div class="info-table"><div class="info-row"><b>제품 설명</b><span>{{p['description'] or '상세정보 준비 중'}}</span></div><div class="info-row"><b>전성분</b><span>{{p['ingredients'] or '정식 처방 확정 후 공개 예정'}}</span></div><div class="info-row"><b>사용법</b><span>{{p['usage']}}</span></div><div class="info-row"><b>주의사항</b><span>{{p['caution']}}</span></div><div class="info-row"><b>배송</b><span>5만원 이상 무료배송 · 기본 배송비 3,000원</span></div></div></div></section>
    """, p=product)
    return page(product["name"], body)


@app.route("/brand")
def brand():
    body = """<section class="section" style="padding-top:12px"><div class="eyebrow">ABOUT RUBIE</div><h2>루비에가 지키는 기준</h2><p class="lead">수제 경험에서 출발하되, 판매 제품은 정식 제조·품질관리와 표시기준을 거쳐 완성합니다.</p></section><section class="story"><div><h2>자연유래 원료를<br>정직하게 사용합니다.</h2><p>‘천연’이라는 단어만 앞세우지 않고 원료의 목적, 함량 근거, 제품 안정성과 실제 사용감을 함께 확인합니다.</p></div><div class="story-note"><b>표현 원칙</b><p>기능성화장품으로 정식 보고되지 않은 제품에는 기능성 효능을 표시하지 않습니다. 객관적으로 확인 가능한 정보만 제품 페이지와 광고에 사용합니다.</p></div></section><section class="section"><div class="values"><div class="value"><div class="num">01</div><h3>처방</h3><p class="muted">원료 하나보다 전체 처방의 안정성과 균형을 봅니다.</p></div><div class="value"><div class="num">02</div><h3>경험</h3><p class="muted">향, 거품, 발림성과 마무리감까지 반복해서 평가합니다.</p></div><div class="value"><div class="num">03</div><h3>정보</h3><p class="muted">전성분과 사용법, 주의사항을 숨김없이 전달합니다.</p></div></div></section>"""
    return page("브랜드", body)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        role = "admin" if ADMIN_EMAIL and email == ADMIN_EMAIL else "customer"
        try:
            con = db(); cur = con.execute("INSERT INTO users(email,password_hash,name,phone,role,created_at) VALUES(?,?,?,?,?,?)", (email, generate_password_hash(request.form["password"]), request.form["name"].strip(), request.form.get("phone", "").strip(), role, now())); con.commit(); user_id = cur.lastrowid; con.close()
            session["user_id"] = user_id; flash("보찌미 회원가입이 완료되었습니다."); return redirect(url_for("mypage"))
        except sqlite3.IntegrityError:
            flash("이미 가입된 이메일입니다.")
    return page("회원가입", """<div class="formbox"><div class="eyebrow">JOIN BOJJIMI</div><h2>회원가입</h2><form method="post"><div class="field"><label>이름</label><input name="name" required></div><div class="field"><label>이메일</label><input type="email" name="email" required></div><div class="field"><label>휴대전화</label><input name="phone" required></div><div class="field"><label>비밀번호</label><input type="password" name="password" minlength="8" required></div><button class="btn dark">가입하기</button></form><p class="muted small">가입하면 주문내역과 배송상태를 확인할 수 있습니다.</p></div>""")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        con = db(); user = con.execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)).fetchone(); con.close()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session["user_id"] = user["id"]; flash(f"{user['name']}님, 반갑습니다."); return redirect(request.args.get("next") or url_for("mypage"))
        flash("이메일 또는 비밀번호를 확인해 주세요.")
    return page("로그인", """<div class="formbox"><div class="eyebrow">WELCOME BACK</div><h2>로그인</h2><form method="post"><div class="field"><label>이메일</label><input type="email" name="email" required></div><div class="field"><label>비밀번호</label><input type="password" name="password" required></div><button class="btn dark">로그인</button> <a class="btn ghost" href="/register">회원가입</a></form></div>""")


@app.route("/logout")
def logout():
    session.pop("user_id", None); flash("로그아웃되었습니다."); return redirect(url_for("home"))


@app.post("/cart/add/<int:product_id>")
def add_cart(product_id):
    con = db(); product = con.execute("SELECT * FROM products WHERE id=? AND status='active'", (product_id,)).fetchone(); con.close()
    if not product or product["stock"] < 1:
        flash("현재 구매할 수 없는 제품입니다."); return redirect(url_for("shop"))
    quantity = max(1, min(int(request.form.get("quantity", 1)), product["stock"]))
    cart = session.get("cart", {}); cart[str(product_id)] = min(int(cart.get(str(product_id), 0)) + quantity, product["stock"]); session["cart"] = cart
    flash("장바구니에 담았습니다."); return redirect(url_for("cart"))


@app.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        values = session.get("cart", {})
        for key in list(values):
            if request.form.get(f"qty_{key}") is not None:
                qty = max(0, int(request.form[f"qty_{key}"]))
                if qty == 0: values.pop(key, None)
                else: values[key] = qty
        session["cart"] = values; flash("장바구니가 수정되었습니다."); return redirect(url_for("cart"))
    items, subtotal, shipping, total = cart_data()
    body = render_template_string("""
    <section class="section" style="padding-top:12px"><div class="eyebrow">YOUR BAG</div><h2>장바구니</h2>{% if items %}<form method="post">{% for item in items %}<div class="cart-row"><div class="thumb">RUBIE</div><div><b>{{item.product['name']}}</b><div class="muted small">{{item.product['category']}}</div></div><div class="cart-price">{{item.unit_price|won}}</div><div class="cart-qty"><input class="qty" type="number" min="0" max="{{item.product['stock']}}" name="qty_{{item.product['id']}}" value="{{item.quantity}}"></div><b>{{item.line_total|won}}</b></div>{% endfor %}<div class="actions"><button class="btn ghost">수량 변경</button></div></form><div class="summary"><div class="summary-line"><span>상품금액</span><b>{{subtotal|won}}</b></div><div class="summary-line"><span>배송비</span><b>{{shipping|won}}</b></div><div class="summary-line total"><span>총 결제금액</span><span>{{total|won}}</span></div><a class="btn dark" style="width:100%;margin-top:15px" href="{{url_for('checkout')}}">주문하기</a></div>{% else %}<div class="empty"><h3>장바구니가 비어 있습니다.</h3><a class="btn" href="{{url_for('shop')}}">제품 보러가기</a></div>{% endif %}</section>
    """, items=items, subtotal=subtotal, shipping=shipping, total=total)
    return page("장바구니", body)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, subtotal, shipping, total = cart_data()
    if not items:
        flash("장바구니가 비어 있습니다."); return redirect(url_for("shop"))
    user = current_user()
    if request.method == "POST":
        order_no = datetime.now().strftime("BJ%Y%m%d") + secrets.token_hex(3).upper()
        con = db()
        try:
            cur = con.execute("""INSERT INTO orders(order_no,user_id,buyer_name,email,phone,postcode,address1,address2,memo,payment_method,subtotal,shipping_fee,total,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (order_no, user["id"] if user else None, request.form["buyer_name"].strip(), request.form["email"].strip().lower(), request.form["phone"].strip(), request.form.get("postcode", "").strip(), request.form["address1"].strip(), request.form.get("address2", "").strip(), request.form.get("memo", "").strip(), "bank", subtotal, shipping, total, "주문접수", now()))
            order_id = cur.lastrowid
            for item in items:
                latest = con.execute("SELECT stock,status FROM products WHERE id=?", (item["product"]["id"],)).fetchone()
                if not latest or latest["status"] != "active" or latest["stock"] < item["quantity"]: raise ValueError(f"{item['product']['name']}의 재고가 부족합니다.")
                con.execute("INSERT INTO order_items(order_id,product_id,product_name,unit_price,quantity) VALUES(?,?,?,?,?)", (order_id, item["product"]["id"], item["product"]["name"], item["unit_price"], item["quantity"]))
                con.execute("UPDATE products SET stock=stock-?,updated_at=? WHERE id=?", (item["quantity"], now(), item["product"]["id"]))
            con.commit()
        except Exception as exc:
            con.rollback(); con.close(); flash(str(exc)); return redirect(url_for("cart"))
        con.close(); session["cart"] = {}; session["last_order_no"] = order_no
        return redirect(url_for("order_complete", order_no=order_no))
    body = render_template_string("""
    <div class="formbox"><div class="eyebrow">CHECKOUT</div><h2>{{'회원 주문' if user else '비회원 주문'}}</h2>{% if not user %}<div class="notice">회원가입 없이도 주문할 수 있습니다. 주문번호를 꼭 보관해 주세요.</div>{% endif %}<form method="post"><div class="row"><div class="field"><label>주문자명</label><input name="buyer_name" value="{{user['name'] if user else ''}}" required></div><div class="field"><label>휴대전화</label><input name="phone" value="{{user['phone'] if user else ''}}" required></div></div><div class="field"><label>이메일</label><input type="email" name="email" value="{{user['email'] if user else ''}}" required></div><div class="row"><div class="field"><label>우편번호</label><input name="postcode"></div><div class="field"><label>배송 요청사항</label><input name="memo"></div></div><div class="field"><label>주소</label><input name="address1" required></div><div class="field"><label>상세주소</label><input name="address2"></div><div class="notice">현재 주문 접수형 결제 단계입니다. 실제 카드결제는 PG사 계약과 결제키 등록 후 활성화됩니다.</div><div class="summary-line total"><span>주문금액</span><span>{{total|won}}</span></div><button class="btn dark" style="width:100%;margin-top:16px">주문 접수하기</button></form></div>
    """, user=user, total=total)
    return page("주문/결제", body)


@app.route("/order/complete/<order_no>")
def order_complete(order_no):
    if session.get("last_order_no") != order_no and not session.get("user_id"): abort(403)
    con = db(); order = con.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone(); con.close()
    if not order: abort(404)
    body = render_template_string("""<div class="formbox center"><div class="eyebrow">ORDER COMPLETE</div><h2>주문이 접수되었습니다.</h2><p>주문번호</p><p style="font-size:26px;font-weight:900;color:var(--rose)">{{o['order_no']}}</p><p class="muted">결제 및 배송 안내는 입력하신 연락처로 전달됩니다.</p><div class="summary-line total"><span>주문금액</span><span>{{o['total']|won}}</span></div><a class="btn dark" href="{{url_for('mypage') if user else url_for('home')}}">{{'주문내역 보기' if user else '홈으로'}}</a></div>""", o=order, user=current_user())
    return page("주문 완료", body)


@app.route("/mypage")
@login_required
def mypage():
    user = current_user(); con = db(); orders = con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall(); con.close()
    body = render_template_string("""<section class="section" style="padding-top:12px"><div class="eyebrow">MY BOJJIMI</div><h2>{{user['name']}}님의 주문</h2>{% if orders %}{% for o in orders %}<a class="order-card" style="display:block" href="{{url_for('member_order',order_no=o['order_no'])}}"><div class="order-head"><div><b>{{o['order_no']}}</b><div class="muted small">{{o['created_at']}}</div></div><span class="status">{{o['status']}}</span></div><div class="summary-line"><span>결제금액</span><b>{{o['total']|won}}</b></div></a>{% endfor %}{% else %}<div class="empty"><p>아직 주문내역이 없습니다.</p><a class="btn" href="{{url_for('shop')}}">제품 둘러보기</a></div>{% endif %}</section>""", user=user, orders=orders)
    return page("마이페이지", body)


@app.route("/mypage/order/<order_no>")
@login_required
def member_order(order_no):
    user = current_user(); con = db(); order = con.execute("SELECT * FROM orders WHERE order_no=? AND user_id=?", (order_no, user["id"])).fetchone()
    if not order: con.close(); abort(404)
    items = con.execute("SELECT * FROM order_items WHERE order_id=?", (order["id"],)).fetchall(); con.close()
    body = render_template_string("""<div class="formbox"><div class="order-head"><div><div class="eyebrow">ORDER DETAIL</div><h2>{{o['order_no']}}</h2></div><span class="status">{{o['status']}}</span></div>{% for item in items %}<div class="summary-line"><span>{{item['product_name']}} × {{item['quantity']}}</span><b>{{(item['unit_price']*item['quantity'])|won}}</b></div>{% endfor %}<div class="summary-line total"><span>총 결제금액</span><span>{{o['total']|won}}</span></div><p class="muted small">배송지: {{o['address1']}} {{o['address2']}}</p></div>""", o=order, items=items)
    return page("주문 상세", body)


@app.route("/admin")
@admin_required
def admin():
    con = db()
    stats = {"products": con.execute("SELECT COUNT(*) FROM products").fetchone()[0], "active": con.execute("SELECT COUNT(*) FROM products WHERE status='active'").fetchone()[0], "orders": con.execute("SELECT COUNT(*) FROM orders").fetchone()[0], "sales": con.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE status!='취소'").fetchone()[0]}
    products = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall(); orders = con.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 30").fetchall(); con.close()
    body = render_template_string("""
    <section class="section" style="padding-top:12px"><div class="eyebrow">STORE ADMIN</div><h2>보찌미 관리자</h2><div class="admin-grid"><div class="kpi">전체 제품<b>{{s.products}}</b></div><div class="kpi">판매 중<b>{{s.active}}</b></div><div class="kpi">전체 주문<b>{{s.orders}}</b></div><div class="kpi">주문 합계<b style="font-size:20px">{{s.sales|won}}</b></div></div><div class="section-head"><h3>제품 관리</h3><a class="btn small" href="{{url_for('admin_product_new')}}">제품 추가</a></div><table><tr><th>ID</th><th>제품명</th><th>상태</th><th>가격</th><th>재고</th><th></th></tr>{% for p in products %}<tr><td>{{p['id']}}</td><td>{{p['name']}}</td><td>{{p['status']}}</td><td>{{p['price']|won}}</td><td>{{p['stock']}}</td><td><a href="{{url_for('admin_product_edit',product_id=p['id'])}}">수정</a></td></tr>{% endfor %}</table></section><section class="section"><h3>최근 주문</h3><table><tr><th>주문번호</th><th>주문자</th><th>금액</th><th>상태</th><th></th></tr>{% for o in orders %}<tr><td>{{o['order_no']}}</td><td>{{o['buyer_name']}}</td><td>{{o['total']|won}}</td><td>{{o['status']}}</td><td><a href="{{url_for('admin_order_edit',order_id=o['id'])}}">처리</a></td></tr>{% endfor %}</table></section>
    """, s=type("Stats", (), stats), products=products, orders=orders)
    return page("관리자", body)


def product_form(product=None):
    return render_template_string("""
    <div class="formbox"><div class="eyebrow">PRODUCT ADMIN</div><h2>{{'제품 수정' if p else '제품 추가'}}</h2><form method="post"><div class="field"><label>제품명</label><input name="name" value="{{p['name'] if p else ''}}" required></div><div class="row"><div class="field"><label>카테고리</label><select name="category">{% for c in categories %}<option {{'selected' if p and p['category']==c else ''}}>{{c}}</option>{% endfor %}</select></div><div class="field"><label>상태</label><select name="status"><option value="draft" {{'selected' if p and p['status']=='draft' else ''}}>비공개</option><option value="coming" {{'selected' if p and p['status']=='coming' else ''}}>출시 준비</option><option value="active" {{'selected' if p and p['status']=='active' else ''}}>판매 중</option></select></div></div><div class="field"><label>한줄 설명</label><input name="short_desc" value="{{p['short_desc'] if p else ''}}"></div><div class="field"><label>상세 설명</label><textarea name="description">{{p['description'] if p else ''}}</textarea></div><div class="field"><label>전성분</label><textarea name="ingredients">{{p['ingredients'] if p else ''}}</textarea></div><div class="row"><div class="field"><label>정가</label><input type="number" min="0" name="price" value="{{p['price'] if p else 0}}"></div><div class="field"><label>판매가</label><input type="number" min="0" name="sale_price" value="{{p['sale_price'] if p and p['sale_price'] is not none else ''}}"></div></div><div class="row"><div class="field"><label>재고</label><input type="number" min="0" name="stock" value="{{p['stock'] if p else 0}}"></div><div class="field"><label>배지</label><input name="badge" value="{{p['badge'] if p else ''}}"></div></div><div class="field"><label>이미지 URL</label><input type="url" name="image_url" value="{{p['image_url'] if p else ''}}"></div><div class="field"><label>사용법</label><textarea name="usage">{{p['usage'] if p else ''}}</textarea></div><div class="field"><label>주의사항</label><textarea name="caution">{{p['caution'] if p else ''}}</textarea></div><label><input type="checkbox" name="featured" value="1" {{'checked' if p and p['featured'] else ''}}> 메인 추천제품</label><div class="actions"><button class="btn dark">저장</button><a class="btn ghost" href="{{url_for('admin')}}">취소</a></div></form></div>
    """, p=product, categories=CATEGORIES)


def product_payload():
    sale_price = request.form.get("sale_price", "").strip()
    return (request.form["name"].strip(), request.form["category"], request.form.get("short_desc", "").strip(), request.form.get("description", "").strip(), request.form.get("ingredients", "").strip(), request.form.get("usage", "").strip(), request.form.get("caution", "").strip(), max(0, int(request.form.get("price") or 0)), int(sale_price) if sale_price else None, max(0, int(request.form.get("stock") or 0)), request.form.get("image_url", "").strip(), request.form.get("badge", "").strip(), request.form.get("status", "draft"), 1 if request.form.get("featured") else 0)


@app.route("/admin/product/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        con = db(); con.execute("""INSERT INTO products(name,category,short_desc,description,ingredients,usage,caution,price,sale_price,stock,image_url,badge,status,featured,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", product_payload() + (now(), now())); con.commit(); con.close(); flash("제품이 추가되었습니다."); return redirect(url_for("admin"))
    return page("제품 추가", product_form())


@app.route("/admin/product/<int:product_id>", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    con = db(); product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product: con.close(); abort(404)
    if request.method == "POST":
        con.execute("""UPDATE products SET name=?,category=?,short_desc=?,description=?,ingredients=?,usage=?,caution=?,price=?,sale_price=?,stock=?,image_url=?,badge=?,status=?,featured=?,updated_at=? WHERE id=?""", product_payload() + (now(), product_id)); con.commit(); con.close(); flash("제품 정보가 수정되었습니다."); return redirect(url_for("admin"))
    con.close(); return page("제품 수정", product_form(product))


@app.route("/admin/order/<int:order_id>", methods=["GET", "POST"])
@admin_required
def admin_order_edit(order_id):
    con = db(); order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order: con.close(); abort(404)
    if request.method == "POST":
        status = request.form["status"]
        if status not in ORDER_STATUSES: abort(400)
        con.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id)); con.commit(); con.close(); flash("주문상태가 변경되었습니다."); return redirect(url_for("admin"))
    items = con.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall(); con.close()
    body = render_template_string("""<div class="formbox"><div class="eyebrow">ORDER ADMIN</div><h2>{{o['order_no']}}</h2><p>{{o['buyer_name']}} · {{o['phone']}} · {{o['email']}}</p><p class="muted">{{o['address1']}} {{o['address2']}}</p>{% for item in items %}<div class="summary-line"><span>{{item['product_name']}} × {{item['quantity']}}</span><b>{{(item['unit_price']*item['quantity'])|won}}</b></div>{% endfor %}<div class="summary-line total"><span>합계</span><span>{{o['total']|won}}</span></div><form method="post"><div class="field"><label>주문상태</label><select name="status">{% for status in statuses %}<option {{'selected' if status==o['status'] else ''}}>{{status}}</option>{% endfor %}</select></div><button class="btn dark">상태 저장</button></form></div>""", o=order, items=items, statuses=ORDER_STATUSES)
    return page("주문 처리", body)


@app.errorhandler(404)
def not_found(_error):
    return page("페이지 없음", '<div class="empty"><h2>페이지를 찾을 수 없습니다.</h2><a class="btn" href="/">홈으로</a></div>'), 404


@app.errorhandler(403)
def forbidden(_error):
    return page("접근 제한", '<div class="empty"><h2>접근 권한이 없습니다.</h2><a class="btn" href="/">홈으로</a></div>'), 403


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
