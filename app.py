import os
import sqlite3
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "bojjimi.db")

BRAND_NAME = "보찌미"
BRAND_EN = "BOJJIMI"
TAGLINE = "좋은 것만 골라 찜."

ADMIN_ID = os.environ.get("ADMIN_ID", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-1234")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bojjimi-change-this-secret")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_type TEXT NOT NULL DEFAULT '공동구매',
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
        end_date TEXT,
        status TEXT DEFAULT '판매중',
        featured INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    admin = conn.execute("SELECT * FROM admins WHERE username=?", (ADMIN_ID,)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO admins(username,password_hash) VALUES(?,?)",
            (ADMIN_ID, generate_password_hash(ADMIN_PASSWORD))
        )

    count = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if count == 0:
        samples = [
            ("자체브랜드", "엄마장독", "식품", "엄마장독 김치", "집밥이 생각나는 정성 가득 김치", 35000, 29900, "", "#", "엄마의 손맛을 담은 엄마장독 대표 상품입니다.", "대표상품", "", "판매중", 1),
            ("자체브랜드", "엄마장독", "식품", "엄마가 만든 조선간장", "깊고 깔끔한 전통 장맛", 25000, 22000, "", "#", "집밥의 기본이 되는 조선간장입니다.", "엄마장독", "", "판매중", 1),
            ("자체브랜드", "엄마장독", "식품", "엄마가 만든 된장", "구수하고 깊은 집된장", 28000, 25000, "", "#", "찌개와 무침에 잘 어울리는 된장입니다.", "엄마장독", "", "판매중", 0),
            ("자체브랜드", "RUBIE", "뷰티", "RUBIE 천연오일 케어", "루비에 브랜드 준비중", None, None, "", "#", "루비에 천연오일 기반 화장품 브랜드관입니다.", "COMING SOON", "", "준비중", 1),
            ("공동구매", "", "생활", "오늘의 생활용품 공구", "좋은 상품만 골라 소개합니다.", 19900, 12900, "", "#", "외부 공동구매 링크를 연결해 판매할 수 있습니다.", "오늘의 공구", "", "판매중", 1)
        ]
        conn.executemany("""
            INSERT INTO products(
                product_type,brand,category,title,subtitle,
                original_price,sale_price,image_url,buy_url,
                description,badge,end_date,status,featured
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, samples)

    conn.commit()
    conn.close()


init_db()


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("관리자 로그인이 필요합니다.")
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper


BASE_HTML = r'''
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | {{ brand_name }}</title>
<style>
*{box-sizing:border-box}
:root{--navy:#192436;--orange:#ff7a32;--bg:#f7f7f5;--line:#e8e7e3;--text:#20242a;--muted:#747b82}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR",Arial,sans-serif}
a{text-decoration:none;color:inherit}
header{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:30}
.nav{max-width:1180px;margin:auto;padding:14px 18px;display:flex;align-items:center;gap:16px}
.logo{font-size:26px;font-weight:950;color:var(--navy);letter-spacing:-1px;white-space:nowrap}.logo span{color:var(--orange)}
.navlinks{margin-left:auto;display:flex;gap:14px;align-items:center;font-size:14px}.navlinks a:hover{color:var(--orange)}
.wrap{max-width:1180px;margin:auto;padding:25px 18px 70px}
.flash{background:#fff4cd;border:1px solid #ecd986;padding:11px 13px;border-radius:10px;margin-bottom:14px}
.hero{background:linear-gradient(135deg,#192436,#334763);color:#fff;border-radius:26px;padding:50px 40px;display:grid;grid-template-columns:1.25fr .75fr;align-items:center;overflow:hidden}
.hero h1{font-size:42px;margin:0 0 12px;letter-spacing:-2px}.hero p{margin:0;line-height:1.7;opacity:.9}.hero-mark{font-size:110px;text-align:center}
.hero-actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:24px}
.btn{display:inline-block;border:1px solid var(--line);background:#fff;border-radius:11px;padding:10px 14px;font-weight:800;cursor:pointer}.btn.orange{background:var(--orange);color:#fff;border-color:var(--orange)}.btn.dark{background:var(--navy);color:#fff;border-color:var(--navy)}.btn.danger{background:#fff0f0;color:#a43c3c;border-color:#efcccc}
.section{margin-top:38px}.section-title{display:flex;justify-content:space-between;gap:12px;align-items:end;margin-bottom:15px}.section-title h2{margin:0;font-size:25px}.section-title p{margin:4px 0 0;color:var(--muted);font-size:13px}
.categories{display:flex;gap:8px;overflow:auto;padding-bottom:4px}.categories a{white-space:nowrap;background:#fff;border:1px solid var(--line);border-radius:20px;padding:8px 12px;font-size:13px}.categories a.on{background:var(--navy);color:#fff}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.card{background:#fff;border:1px solid var(--line);border-radius:17px;overflow:hidden}.image{aspect-ratio:1/1;background:linear-gradient(145deg,#f3efe9,#e9e7e2);display:flex;align-items:center;justify-content:center;font-size:64px;overflow:hidden;position:relative}.image img{width:100%;height:100%;object-fit:cover}.badge{position:absolute;top:10px;left:10px;background:var(--orange);color:#fff;border-radius:8px;padding:5px 8px;font-size:11px;font-weight:900}
.card-body{padding:14px}.brand{color:var(--orange);font-size:12px;font-weight:900}.title{font-weight:900;margin-top:6px;line-height:1.35}.subtitle{color:var(--muted);font-size:12px;margin-top:6px;min-height:32px}.price{margin-top:10px;font-size:19px;font-weight:950}.original{color:#a0a4a7;font-size:12px;text-decoration:line-through;margin-left:5px}.meta{color:var(--muted);font-size:11px;margin-top:7px}
.brand-strip{display:grid;grid-template-columns:1fr 1fr;gap:15px}.brand-box{min-height:210px;border-radius:22px;padding:26px;display:flex;flex-direction:column;justify-content:flex-end}.brand-box.mom{background:linear-gradient(135deg,#7a4e2e,#b77a47);color:#fff}.brand-box.rubie{background:linear-gradient(135deg,#334b3a,#719176);color:#fff}.brand-box h2{font-size:28px;margin:0 0 6px}.brand-box p{margin:0 0 16px;opacity:.9}
.detail{display:grid;grid-template-columns:1fr 1fr;gap:25px}.detail-image{background:#eeeae4;border-radius:22px;min-height:470px;display:flex;align-items:center;justify-content:center;overflow:hidden;font-size:90px}.detail-image img{width:100%;height:100%;object-fit:cover}.panel{background:#fff;border:1px solid var(--line);border-radius:22px;padding:26px}.panel h1{font-size:28px;margin:8px 0}.desc{white-space:pre-wrap;line-height:1.8;color:#4f565c}
.form{max-width:760px;margin:auto;background:#fff;border:1px solid var(--line);border-radius:20px;padding:25px}.field{margin:15px 0}.field label{display:block;font-size:13px;font-weight:900;margin-bottom:7px}.field input,.field select,.field textarea{width:100%;padding:12px;border:1px solid #d7d8d4;border-radius:9px;font:inherit}.field textarea{min-height:170px;resize:vertical}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.admin-table{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden}.admin-row{display:grid;grid-template-columns:100px 1fr 120px 150px;gap:10px;padding:13px 15px;border-bottom:1px solid var(--line);align-items:center}.admin-row:last-child{border-bottom:0}.empty{background:#fff;border-radius:16px;padding:45px 20px;text-align:center;color:var(--muted)}
footer{margin-top:60px;padding:32px 18px;background:var(--navy);color:#dce1e7;text-align:center;font-size:12px}
@media(max-width:850px){.navlinks a:nth-child(2),.navlinks a:nth-child(3){display:none}.hero{grid-template-columns:1fr;padding:34px 23px}.hero h1{font-size:31px}.hero-mark{font-size:70px;margin-top:20px}.grid{grid-template-columns:repeat(2,1fr);gap:10px}.brand-strip{grid-template-columns:1fr}.detail{grid-template-columns:1fr}.detail-image{min-height:330px}.row{grid-template-columns:1fr}.admin-row{grid-template-columns:80px 1fr}.admin-row>div:nth-child(3),.admin-row>div:nth-child(4){display:none}}
</style>
</head>
<body>
<header><div class="nav"><a class="logo" href="{{ url_for('home') }}">보<span>찌미</span></a><div class="navlinks"><a href="{{ url_for('shop') }}">쇼핑</a><a href="{{ url_for('brand_page', brand='엄마장독') }}">엄마장독</a><a href="{{ url_for('brand_page', brand='RUBIE') }}">RUBIE</a>{% if session.get('admin') %}<a href="{{ url_for('admin_dashboard') }}">관리자</a>{% else %}<a href="{{ url_for('admin_login') }}">관리자</a>{% endif %}</div></div></header>
<div class="wrap">{% with messages=get_flashed_messages() %}{% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}{% endwith %}{{ content|safe }}</div>
<footer><b>{{ brand_name }} · {{ brand_en }}</b><br>{{ tagline }}<br><br>© 2026 BOJJIMI</footer>
</body>
</html>
'''


def page(title, body, **context):
    content = render_template_string(body, **context)
    return render_template_string(BASE_HTML, title=title, content=content, brand_name=BRAND_NAME, brand_en=BRAND_EN, tagline=TAGLINE)


def money(value):
    if value is None:
        return ""
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


app.jinja_env.filters["money"] = money


def product_card(p):
    image = f'<img src="{p["image_url"]}" alt="">' if p["image_url"] else "🎁"
    badge = f'<div class="badge">{p["badge"]}</div>' if p["badge"] else ""
    original = f'<span class="original">{money(p["original_price"])}원</span>' if p["original_price"] else ""
    sale = f'{money(p["sale_price"])}원' if p["sale_price"] else "가격문의"
    brand = p["brand"] or p["product_type"]
    return f'''<a class="card" href="{url_for("product_detail", product_id=p["id"])}"><div class="image">{badge}{image}</div><div class="card-body"><div class="brand">{brand}</div><div class="title">{p["title"]}</div><div class="subtitle">{p["subtitle"] or ""}</div><div class="price">{sale}{original}</div><div class="meta">{p["category"]} · {p["status"]}</div></div></a>'''


@app.route("/")
def home():
    conn = db()
    featured = conn.execute("SELECT * FROM products WHERE featured=1 ORDER BY id DESC LIMIT 8").fetchall()
    groupbuys = conn.execute("SELECT * FROM products WHERE product_type='공동구매' ORDER BY id DESC LIMIT 8").fetchall()
    conn.close()
    return page("홈", r'''
    <section class="hero"><div><div style="font-weight:900;letter-spacing:2px;margin-bottom:8px">BOJJIMI</div><h1>좋은 것만 골라, 찜.</h1><p>엄마장독부터 RUBIE, 생활용품과 오늘의 공동구매까지.<br>보찌미가 좋은 것만 골라 한곳에 담았습니다.</p><div class="hero-actions"><a class="btn orange" href="{{ url_for('shop') }}">쇼핑 둘러보기</a><a class="btn" href="{{ url_for('brand_page', brand='엄마장독') }}">엄마장독</a><a class="btn" href="{{ url_for('brand_page', brand='RUBIE') }}">RUBIE</a></div></div><div class="hero-mark">🎁</div></section>
    <section class="section"><div class="section-title"><div><h2>오늘의 찜 🔥</h2><p>보찌미가 골라낸 추천 상품</p></div><a href="{{ url_for('shop') }}">전체보기 →</a></div>{% if featured %}<div class="grid">{% for p in featured %}{{ product_card(p)|safe }}{% endfor %}</div>{% else %}<div class="empty">등록된 추천 상품이 없습니다.</div>{% endif %}</section>
    <section class="section"><div class="section-title"><div><h2>보찌미 브랜드</h2><p>보찌미에서 만나는 자체 브랜드</p></div></div><div class="brand-strip"><a class="brand-box mom" href="{{ url_for('brand_page', brand='엄마장독') }}"><h2>엄마장독 🏺</h2><p>김치 · 조선간장 · 된장</p><span><b>브랜드관 보기 →</b></span></a><a class="brand-box rubie" href="{{ url_for('brand_page', brand='RUBIE') }}"><h2>RUBIE 🌿</h2><p>천연오일 기반 라이프 뷰티</p><span><b>브랜드관 보기 →</b></span></a></div></section>
    <section class="section"><div class="section-title"><div><h2>공동구매</h2><p>외부 구매링크와 연결되는 공구 상품</p></div></div>{% if groupbuys %}<div class="grid">{% for p in groupbuys %}{{ product_card(p)|safe }}{% endfor %}</div>{% else %}<div class="empty">진행 중인 공동구매가 없습니다.</div>{% endif %}</section>
    ''', featured=featured, groupbuys=groupbuys, product_card=product_card)


@app.route("/shop")
def shop():
    category = request.args.get("category", "").strip()
    product_type = request.args.get("type", "").strip()
    conn = db()
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if category:
        sql += " AND category=?"; params.append(category)
    if product_type:
        sql += " AND product_type=?"; params.append(product_type)
    sql += " ORDER BY id DESC"
    products = conn.execute(sql, params).fetchall()
    conn.close()
    categories = ["식품","생활","주방","뷰티","패션","가전","반려동물","취미/레저","골프","기타"]
    return page("쇼핑", r'''
    <div class="section-title"><div><h2>보찌미 쇼핑</h2><p>상품 제한 없이 좋은 것만 골라 담았습니다.</p></div>{% if session.get('admin') %}<a class="btn orange" href="{{ url_for('admin_product_new') }}">+ 상품 등록</a>{% endif %}</div>
    <div class="categories"><a class="{% if not category and not product_type %}on{% endif %}" href="{{ url_for('shop') }}">전체</a><a class="{% if product_type=='공동구매' %}on{% endif %}" href="{{ url_for('shop', type='공동구매') }}">공동구매</a><a class="{% if product_type=='자체브랜드' %}on{% endif %}" href="{{ url_for('shop', type='자체브랜드') }}">자체브랜드</a>{% for c in categories %}<a class="{% if category==c %}on{% endif %}" href="{{ url_for('shop', category=c) }}">{{ c }}</a>{% endfor %}</div><div style="height:16px"></div>
    {% if products %}<div class="grid">{% for p in products %}{{ product_card(p)|safe }}{% endfor %}</div>{% else %}<div class="empty">등록된 상품이 없습니다.</div>{% endif %}
    ''', products=products, categories=categories, category=category, product_type=product_type, product_card=product_card)


@app.route("/brand/<brand>")
def brand_page(brand):
    conn = db(); products = conn.execute("SELECT * FROM products WHERE brand=? ORDER BY id DESC", (brand,)).fetchall(); conn.close()
    if brand == "엄마장독": title, copy = "엄마장독 🏺", "엄마가 만든 김치 · 조선간장 · 된장"
    elif brand == "RUBIE": title, copy = "RUBIE 🌿", "천연오일을 기반으로 준비하는 라이프 뷰티 브랜드"
    else: title, copy = brand, ""
    return page(brand, r'''<section class="hero" style="padding:36px 30px"><div><h1>{{ title }}</h1><p>{{ copy }}</p></div><div class="hero-mark">✨</div></section><section class="section">{% if products %}<div class="grid">{% for p in products %}{{ product_card(p)|safe }}{% endfor %}</div>{% else %}<div class="empty">준비 중입니다.</div>{% endif %}</section>''', title=title, copy=copy, products=products, product_card=product_card)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = db(); p = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone(); conn.close()
    if not p: return "상품을 찾을 수 없습니다.", 404
    return page(p["title"], r'''
    <div class="detail"><div class="detail-image">{% if p['image_url'] %}<img src="{{ p['image_url'] }}" alt="">{% else %}🎁{% endif %}</div><div class="panel">{% if p['badge'] %}<div class="brand">{{ p['badge'] }}</div>{% endif %}<h1>{{ p['title'] }}</h1><div class="subtitle" style="font-size:14px">{{ p['subtitle'] or '' }}</div><div class="price" style="font-size:28px">{% if p['sale_price'] %}{{ p['sale_price']|money }}원{% else %}가격문의{% endif %}{% if p['original_price'] %}<span class="original">{{ p['original_price']|money }}원</span>{% endif %}</div><div class="meta">{{ p['brand'] or p['product_type'] }} · {{ p['category'] }}</div>{% if p['end_date'] %}<p><b>공구 마감</b> {{ p['end_date'] }}</p>{% endif %}<hr style="border:0;border-top:1px solid #eee;margin:20px 0"><div class="desc">{{ p['description'] or '상품 설명이 없습니다.' }}</div><div style="margin-top:24px">{% if p['buy_url'] and p['buy_url'] != '#' %}<a class="btn orange" style="width:100%;text-align:center;padding:14px" href="{{ p['buy_url'] }}" target="_blank" rel="noopener">구매하러 가기 →</a>{% else %}<div class="btn" style="width:100%;text-align:center;padding:14px">구매링크 준비중</div>{% endif %}</div>{% if session.get('admin') %}<div style="display:flex;gap:8px;margin-top:12px"><a class="btn" href="{{ url_for('admin_product_edit', product_id=p['id']) }}">수정</a><form method="post" action="{{ url_for('admin_product_delete', product_id=p['id']) }}" onsubmit="return confirm('삭제할까요?')"><button class="btn danger" type="submit">삭제</button></form></div>{% endif %}</div></div>
    ''', p=p)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip(); password = request.form.get("password", "")
        conn = db(); admin = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone(); conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin"] = True; session["admin_name"] = username; flash("관리자로 로그인했습니다."); return redirect(url_for("admin_dashboard"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.")
    return page("관리자 로그인", r'''<div class="form"><h2>관리자 로그인</h2><form method="post"><div class="field"><label>아이디</label><input name="username" required></div><div class="field"><label>비밀번호</label><input type="password" name="password" required></div><button class="btn dark" style="width:100%" type="submit">로그인</button></form></div>''')


@app.route("/admin/logout")
def admin_logout():
    session.clear(); return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = db(); products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall(); conn.close()
    return page("관리자", r'''<div class="section-title"><div><h2>보찌미 관리자</h2><p>상품 등록 · 수정 · 판매상태 관리</p></div><div><a class="btn orange" href="{{ url_for('admin_product_new') }}">+ 상품 등록</a> <a class="btn" href="{{ url_for('admin_logout') }}">로그아웃</a></div></div><div class="admin-table">{% for p in products %}<div class="admin-row"><div><b>{{ p['id'] }}</b></div><div><a href="{{ url_for('product_detail', product_id=p['id']) }}"><b>{{ p['title'] }}</b></a><div class="meta">{{ p['brand'] or p['product_type'] }} · {{ p['category'] }}</div></div><div>{{ p['status'] }}</div><div><a href="{{ url_for('admin_product_edit', product_id=p['id']) }}">수정</a></div></div>{% endfor %}</div>''', products=products)


PRODUCT_TYPES = ["공동구매", "자체브랜드", "추천상품"]
CATEGORIES = ["식품","생활","주방","뷰티","패션","가전","반려동물","취미/레저","골프","기타"]


def product_form(p=None):
    return page("상품 등록" if p is None else "상품 수정", r'''
    <div class="form"><h2>{{ '상품 등록' if not p else '상품 수정' }}</h2><form method="post">
    <div class="row"><div class="field"><label>상품 유형</label><select name="product_type">{% for x in product_types %}<option value="{{ x }}" {% if p and p['product_type']==x %}selected{% endif %}>{{ x }}</option>{% endfor %}</select></div><div class="field"><label>카테고리</label><select name="category">{% for x in categories %}<option value="{{ x }}" {% if p and p['category']==x %}selected{% endif %}>{{ x }}</option>{% endfor %}</select></div></div>
    <div class="field"><label>브랜드</label><input name="brand" value="{{ p['brand'] if p else '' }}" placeholder="예: 엄마장독, RUBIE"></div><div class="field"><label>상품명</label><input name="title" required value="{{ p['title'] if p else '' }}"></div><div class="field"><label>한줄 설명</label><input name="subtitle" value="{{ p['subtitle'] if p else '' }}"></div>
    <div class="row"><div class="field"><label>정상가</label><input type="number" name="original_price" value="{{ p['original_price'] if p and p['original_price'] else '' }}"></div><div class="field"><label>판매가 / 공구가</label><input type="number" name="sale_price" value="{{ p['sale_price'] if p and p['sale_price'] else '' }}"></div></div>
    <div class="field"><label>대표 이미지 URL</label><input name="image_url" value="{{ p['image_url'] if p else '' }}" placeholder="https://..."></div><div class="field"><label>구매 링크</label><input name="buy_url" value="{{ p['buy_url'] if p else '' }}" placeholder="https://..."></div>
    <div class="row"><div class="field"><label>배지</label><input name="badge" value="{{ p['badge'] if p else '' }}" placeholder="오늘의 공구 / BEST"></div><div class="field"><label>공구 마감일</label><input type="date" name="end_date" value="{{ p['end_date'] if p else '' }}"></div></div>
    <div class="row"><div class="field"><label>판매 상태</label><select name="status">{% for x in ['판매중','준비중','품절','종료'] %}<option value="{{ x }}" {% if p and p['status']==x %}selected{% endif %}>{{ x }}</option>{% endfor %}</select></div><div class="field"><label>메인 추천</label><select name="featured"><option value="0" {% if not p or not p['featured'] %}selected{% endif %}>아니오</option><option value="1" {% if p and p['featured'] %}selected{% endif %}>예</option></select></div></div>
    <div class="field"><label>상품 설명</label><textarea name="description">{{ p['description'] if p else '' }}</textarea></div><button class="btn orange" style="width:100%" type="submit">{{ '등록하기' if not p else '수정 저장' }}</button></form></div>
    ''', p=p, product_types=PRODUCT_TYPES, categories=CATEGORIES)


@app.route("/admin/product/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        conn = db(); conn.execute("""INSERT INTO products(product_type,brand,category,title,subtitle,original_price,sale_price,image_url,buy_url,description,badge,end_date,status,featured) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            request.form.get("product_type", "공동구매"), request.form.get("brand", "").strip(), request.form.get("category", "기타"), request.form.get("title", "").strip(), request.form.get("subtitle", "").strip(), int(request.form["original_price"]) if request.form.get("original_price") else None, int(request.form["sale_price"]) if request.form.get("sale_price") else None, request.form.get("image_url", "").strip(), request.form.get("buy_url", "").strip(), request.form.get("description", "").strip(), request.form.get("badge", "").strip(), request.form.get("end_date", "").strip(), request.form.get("status", "판매중"), int(request.form.get("featured", "0"))
        )); conn.commit(); conn.close(); flash("상품이 등록되었습니다."); return redirect(url_for("admin_dashboard"))
    return product_form()


@app.route("/admin/product/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    conn = db(); p = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not p: conn.close(); return "상품을 찾을 수 없습니다.", 404
    if request.method == "POST":
        conn.execute("""UPDATE products SET product_type=?,brand=?,category=?,title=?,subtitle=?,original_price=?,sale_price=?,image_url=?,buy_url=?,description=?,badge=?,end_date=?,status=?,featured=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (
            request.form.get("product_type", "공동구매"), request.form.get("brand", "").strip(), request.form.get("category", "기타"), request.form.get("title", "").strip(), request.form.get("subtitle", "").strip(), int(request.form["original_price"]) if request.form.get("original_price") else None, int(request.form["sale_price"]) if request.form.get("sale_price") else None, request.form.get("image_url", "").strip(), request.form.get("buy_url", "").strip(), request.form.get("description", "").strip(), request.form.get("badge", "").strip(), request.form.get("end_date", "").strip(), request.form.get("status", "판매중"), int(request.form.get("featured", "0")), product_id
        )); conn.commit(); conn.close(); flash("상품이 수정되었습니다."); return redirect(url_for("product_detail", product_id=product_id))
    conn.close(); return product_form(p)


@app.post("/admin/product/<int:product_id>/delete")
@admin_required
def admin_product_delete(product_id):
    conn = db(); conn.execute("DELETE FROM products WHERE id=?", (product_id,)); conn.commit(); conn.close(); flash("상품이 삭제되었습니다."); return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
