import os
import sqlite3
from functools import wraps
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
        status TEXT DEFAULT '판매중',
        featured INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS compare_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        brand TEXT,
        model_no TEXT,
        category TEXT,
        image_url TEXT,
        description TEXT
    );

    CREATE TABLE IF NOT EXISTS compare_offers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        seller TEXT NOT NULL,
        price INTEGER NOT NULL,
        shipping INTEGER DEFAULT 0,
        buy_url TEXT NOT NULL,
        note TEXT,
        FOREIGN KEY(item_id) REFERENCES compare_items(id)
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
                ("공동구매","엄마장독","식품","참기름 300ml","고소한 집밥의 기본",29900,22900,"","#","엄마장독 참기름 공동구매 예시입니다.","공동구매","판매중",1),
                ("공동구매","엄마장독","식품","된장 1kg","구수하고 깊은 집된장",24900,18900,"","#","엄마장독 된장 공동구매 예시입니다.","공동구매","판매중",1),
                ("공동구매","RUBIE","뷰티","루비에 에센스 100ml","천연오일 기반 케어",59000,39900,"","#","RUBIE 공동구매 예시입니다.","공동구매","판매중",1),
                ("공동구매","RUBIE","뷰티","루비에 스틱 30포","데일리 케어",39900,28900,"","#","RUBIE 공동구매 예시입니다.","공동구매","판매중",1)
            ]
        )

    if conn.execute("SELECT COUNT(*) c FROM compare_items").fetchone()["c"] == 0:
        items = [
            ("다이슨 에어랩 컴플리트 롱","Dyson","HS05","뷰티가전","","판매처별 실구매가 비교"),
            ("Apple 에어팟 프로 2세대","Apple","MTJV3KH/A","가전","","판매처별 실구매가 비교"),
            ("삼성 55인치 4K TV","Samsung","KU55UC7000FXKR","가전","","판매처별 실구매가 비교"),
            ("LG 디오스 냉장고","LG","F874MTE111","가전","","판매처별 실구매가 비교")
        ]
        ids=[]
        for x in items:
            cur=conn.execute("INSERT INTO compare_items(title,brand,model_no,category,image_url,description) VALUES(?,?,?,?,?,?)",x)
            ids.append(cur.lastrowid)
        conn.executemany("INSERT INTO compare_offers(item_id,seller,price,shipping,buy_url,note) VALUES(?,?,?,?,?,?)",[
            (ids[0],"A몰",548000,0,"#","무료배송"),(ids[0],"B몰",555000,0,"#","카드할인 별도"),
            (ids[1],"A몰",269000,0,"#","무료배송"),(ids[1],"B몰",274000,2500,"#","일반배송"),
            (ids[2],"A몰",679000,0,"#","무료배송"),(ids[2],"B몰",688000,0,"#","설치비 별도"),
            (ids[3],"A몰",1290000,0,"#","무료배송"),(ids[3],"B몰",1310000,0,"#","설치 포함")
        ])

    if conn.execute("SELECT COUNT(*) c FROM vendors").fetchone()["c"] == 0:
        conn.executemany("INSERT INTO vendors(name,subtext,logo_text,url,sort_order,active) VALUES(?,?,?,?,?,?)",[
            ("쿠팡","다양한 상품을 빠르고 편리하게","coupang","#",1,1),
            ("네이버 쇼핑","네이버에서 찾은 스마트한 쇼핑","N","#",2,1),
            ("11번가","11번가에서 만나는 특별한 혜택","11","#",3,1),
            ("G마켓","대한민국 대표 온라인 쇼핑몰","G","#",4,1),
            ("옥션","다양한 상품과 합리적인 가격","A.","#",5,1),
            ("엄마장독 공식몰","엄마장독 공식 스토어","엄마장독","#",6,1),
            ("RUBIE 공식몰","RUBIE 공식 스토어","RUBIE","#",7,1)
        ])

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


def money(v):
    if v is None or v == "":
        return ""
    return f"{int(v):,}"

app.jinja_env.filters["money"] = money

BASE_HTML = r'''
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | 보찌미</title>
<style>
*{box-sizing:border-box}:root{--pink:#ff2f78;--pink2:#ff6a93;--line:#ececef;--muted:#757b82;--bg:#fafafa}
body{margin:0;background:var(--bg);color:#1f2328;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR",Arial,sans-serif}a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}
.top{background:#fff;border-bottom:1px solid var(--line)}.top-inner{max-width:1500px;margin:auto;min-height:82px;padding:15px 22px;display:grid;grid-template-columns:240px minmax(320px,1fr) 300px;gap:22px;align-items:center}
.logo-wrap{display:flex;align-items:center;gap:10px}.logo-icon{width:42px;height:42px;border:2px solid var(--pink);border-radius:13px;display:flex;align-items:center;justify-content:center;color:var(--pink);font-size:22px}.logo{color:var(--pink);font-size:30px;font-weight:950}.logo-sub{font-size:12px;font-weight:700;white-space:nowrap}
.search-main{display:flex;height:48px;border:1.5px solid #dcdce2;border-radius:8px;overflow:hidden;background:#fff}.search-main input{flex:1;border:0;outline:0;padding:0 16px}.search-main button{width:55px;border:0;background:linear-gradient(135deg,var(--pink),var(--pink2));color:#fff;font-size:20px}
.quick-icons{display:flex;justify-content:flex-end;gap:26px}.quick-icons a{text-align:center;font-size:12px;font-weight:700}.quick-icons b{display:block;font-size:23px;margin-bottom:3px;font-weight:500}
.navbar{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:40}.navbar-inner{max-width:1500px;margin:auto;display:flex;align-items:center;min-height:54px;padding:0 20px;overflow-x:auto}.navbar-inner a{padding:18px 19px;font-size:14px;font-weight:850;white-space:nowrap}.navbar-inner a:first-child,.navbar-inner a:hover{color:var(--pink)}
.flash{max-width:1500px;margin:14px auto 0;background:#fff7d8;border:1px solid #eedf94;padding:10px 13px;border-radius:8px}.page{max-width:1500px;margin:auto;padding:22px 20px 60px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:22px;align-items:start}.sidebar{position:sticky;top:76px}
.hero{min-height:330px;border-radius:12px;background:linear-gradient(135deg,#fff7f9,#ffeef4);border:1px solid #ffe0ea;padding:42px 48px;display:grid;grid-template-columns:1.15fr .85fr;align-items:center}.hero h1{margin:0;font-size:46px;line-height:1.35;letter-spacing:-2px}.hero h1 strong{color:var(--pink)}.hero p{font-size:18px;color:#5a5d63;line-height:1.65;margin:22px 0}.hero-btn{display:inline-block;background:var(--pink);color:#fff;font-weight:900;border-radius:7px;padding:13px 20px}
.hero-art{height:245px;display:flex;align-items:center;justify-content:center;gap:14px}.bag{width:160px;height:190px;background:linear-gradient(135deg,#ef91b0,#da5e89);border-radius:6px 6px 12px 12px;color:#fff;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:950;box-shadow:0 18px 40px rgba(224,80,125,.22)}.product-mock{display:flex;align-items:end;gap:7px}.bottle{width:45px;border-radius:14px 14px 6px 6px;background:#fff;border:1px solid #e6e6e6;box-shadow:0 10px 25px rgba(0,0,0,.08)}.bottle.one{height:100px}.bottle.two{height:130px;background:#4b2b22}.jar{width:95px;height:70px;border-radius:15px 15px 8px 8px;background:#9a633b;border:5px solid #d7b08d;box-shadow:0 10px 25px rgba(0,0,0,.08)}
.shortcuts{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:18px}.shortcut{background:#fff;border:1px solid var(--line);border-radius:10px;min-height:118px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:8px;text-align:center;font-weight:900}.ico{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:25px}.i1{background:#ffe8f0;color:var(--pink)}.i2{background:#e8f8ed}.i3{background:#f0e8ff}.i4{background:#e7f2ff}.i5{background:#fff0df}
.section{margin-top:34px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:14px}.section-head h2{margin:0;font-size:25px}.section-head a{font-size:13px;font-weight:800}.product-grid,.compare-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card,.compare-card{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}.card-img{aspect-ratio:1/1;background:#f4f1ee;position:relative;display:flex;align-items:center;justify-content:center;font-size:55px;overflow:hidden}.card-img img,.compare-img img{width:100%;height:100%;object-fit:cover}.timer{position:absolute;top:10px;left:10px;background:#ff5e73;color:#fff;font-size:11px;font-weight:900;border-radius:6px;padding:6px 8px}.card-body,.compare-body{padding:13px}.tag{display:inline-block;padding:4px 6px;border-radius:5px;background:#ffe4ee;color:var(--pink);font-size:10px;font-weight:900}.card-title,.compare-title{font-size:14px;font-weight:900;line-height:1.4}.sale,.lowest{color:var(--pink);font-size:18px;font-weight:950;margin-top:8px}.original{color:#9ca0a5;font-size:12px;text-decoration:line-through;margin-top:4px}
.compare-search{display:flex;border:1.5px solid #ffd4e2;border-radius:9px;overflow:hidden;background:#fff;height:48px}.compare-search input{flex:1;border:0;outline:0;padding:0 14px}.compare-search button{width:145px;border:0;background:linear-gradient(135deg,var(--pink),var(--pink2));color:#fff;font-weight:900}.compare-img{aspect-ratio:1.35/1;background:#f6f6f6;display:flex;align-items:center;justify-content:center;font-size:48px}.outline-btn{display:block;margin-top:10px;border:1px solid var(--pink);color:var(--pink);border-radius:6px;padding:9px;text-align:center;font-weight:900;font-size:12px}
.vendor-box{background:#fff;border:2px solid var(--pink);border-radius:10px;overflow:hidden}.vendor-head{padding:16px 17px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.vendor-head h3{margin:0;font-size:17px}.vendor-item{display:grid;grid-template-columns:58px 1fr;gap:12px;padding:15px 14px;border-bottom:1px solid var(--line);align-items:center}.vendor-logo{width:58px;height:58px;border-radius:10px;background:#f6f6f8;display:flex;align-items:center;justify-content:center;font-weight:950;font-size:18px}.vendor-item h4{margin:0 0 5px;font-size:14px}.vendor-item p{margin:0;font-size:11px;color:var(--muted);line-height:1.45}.vendor-link{display:inline-block;margin-top:7px;background:#ff738b;color:#fff;border-radius:5px;padding:6px 14px;font-size:11px;font-weight:900}.side-card{margin-top:14px;background:#fff;border:1px solid var(--line);border-radius:10px;padding:17px}.partner{background:linear-gradient(135deg,#fff5f8,#ffe8f0)}.kakao{background:linear-gradient(135deg,#fffbea,#fff1a8)}
.form{max-width:820px;margin:auto;background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px}.field{margin:14px 0}.field label{display:block;font-size:13px;font-weight:900;margin-bottom:7px}.field input,.field select,.field textarea{width:100%;padding:12px;border:1px solid #dadbe0;border-radius:8px}.field textarea{min-height:150px}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.btn{display:inline-block;border:1px solid var(--line);background:#fff;border-radius:7px;padding:10px 14px;font-weight:900;cursor:pointer}.btn.pink{background:var(--pink);border-color:var(--pink);color:#fff}.btn.dark{background:#222;border-color:#222;color:#fff}
.offer-table{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}.offer-row{display:grid;grid-template-columns:1.2fr .8fr .8fr .8fr 100px;gap:10px;padding:14px;border-bottom:1px solid var(--line);align-items:center}.offer-row.head{background:#f6f6f8;font-weight:900}.offer-row.best{background:#fff5f8}.best-tag{display:inline-block;background:var(--pink);color:#fff;font-size:10px;font-weight:900;padding:4px 6px;border-radius:5px}
footer{background:#1c1c1d;color:#d7d7da;margin-top:55px}.footer-inner{max-width:1500px;margin:auto;padding:34px 22px;display:grid;grid-template-columns:1.4fr repeat(3,1fr);gap:30px;font-size:12px;line-height:1.8}.footer-brand{font-size:21px;font-weight:950;color:#fff}.copyright{text-align:center;border-top:1px solid #333;padding:14px;font-size:11px;color:#999}
@media(max-width:1180px){.top-inner{grid-template-columns:220px 1fr}.quick-icons{display:none}.layout{grid-template-columns:1fr}.sidebar{position:static}.vendor-box{display:grid;grid-template-columns:repeat(2,1fr)}.vendor-head{grid-column:1/-1}}
@media(max-width:760px){.top-inner{grid-template-columns:1fr;padding:12px 14px}.logo-wrap{justify-content:center}.logo-sub{display:none}.navbar-inner{padding:0 6px}.navbar-inner a{padding:16px 12px;font-size:13px}.page{padding:14px 12px 40px}.hero{grid-template-columns:1fr;padding:30px 24px;min-height:auto}.hero h1{font-size:32px}.hero p{font-size:15px}.hero-art{height:180px;margin-top:18px}.bag{width:115px;height:135px;font-size:22px}.shortcuts{grid-template-columns:repeat(5,125px);overflow-x:auto}.product-grid,.compare-grid{grid-template-columns:repeat(2,1fr)}.vendor-box{display:block}.footer-inner{grid-template-columns:1fr 1fr}.row{grid-template-columns:1fr}.offer-row{grid-template-columns:1fr 1fr}.offer-row.head{display:none}.offer-row>div:nth-child(4),.offer-row>div:nth-child(5){display:none}}
</style></head><body>
<div class="top"><div class="top-inner"><div class="logo-wrap"><div class="logo-icon">♡</div><a class="logo" href="{{url_for('home')}}">보찌미</a><span class="logo-sub">좋은 제품을 좋은 가격에</span></div><form class="search-main" action="{{url_for('compare')}}"><input name="q" placeholder="상품명, 브랜드, 모델명을 검색해보세요"><button>⌕</button></form><div class="quick-icons"><a href="{{url_for('admin_login')}}"><b>♙</b>로그인</a><a href="#"><b>♡</b>찜 목록</a><a href="#"><b>🛒</b>장바구니</a></div></div></div>
<div class="navbar"><div class="navbar-inner"><a href="{{url_for('home')}}">보찌미 홈</a><a href="{{url_for('shop')}}">오늘의 찜 / 공동구매</a><a href="{{url_for('brand_page',brand='엄마장독')}}">엄마장독 브랜드관</a><a href="{{url_for('brand_page',brand='RUBIE')}}">RUBIE 브랜드관</a><a href="{{url_for('shop')}}">전체 카테고리⌄</a><a href="{{url_for('compare')}}">최저가 찾기</a><a href="#vendors">연결 벤더</a><a href="#">고객센터</a></div></div>
{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
<div class="page">{{content|safe}}</div>
<footer><div class="footer-inner"><div><div class="footer-brand">보찌미</div>좋은 제품을 좋은 사람들과<br>좋은 가격에 함께합니다.</div><div><b>회사 정보</b><br>회사소개<br>이용약관<br>개인정보처리방침<br>제휴 문의</div><div><b>고객센터</b><br>공지사항<br>1:1 문의<br>자주 묻는 질문<br>이용안내</div><div><b>파트너</b><br>판매자(벤더) 제휴<br>입점 안내<br>광고 문의</div></div><div class="copyright">© 2026 BOJJIMI. All rights reserved.</div></footer></body></html>
'''


def page(title, body, **ctx):
    content = render_template_string(body, **ctx)
    return render_template_string(BASE_HTML, title=title, content=content)


def product_card(p):
    img = f'<img src="{p["image_url"]}" alt="">' if p["image_url"] else "🎁"
    sale = f'{money(p["sale_price"])}원' if p["sale_price"] else "가격문의"
    original = f'<div class="original">정상가 {money(p["original_price"])}원</div>' if p["original_price"] else ""
    return f'''<a class="card" href="{url_for("product_detail",product_id=p["id"])}"><div class="card-img"><div class="timer">마감까지 2일 05:34:21</div>{img}</div><div class="card-body"><span class="tag">{p["brand"] or p["product_type"]}</span><div class="card-title">{p["title"]}</div><div class="sale">공구가 {sale}</div>{original}<div style="font-size:11px;color:#777;margin-top:7px">판매량 128개</div></div></a>'''


def compare_card(x):
    img = f'<img src="{x["image_url"]}" alt="">' if x["image_url"] else "🔎"
    low = f'{money(x["lowest"])}원~' if x["lowest"] is not None else "가격 준비중"
    return f'''<div class="compare-card"><div class="compare-img">{img}</div><div class="compare-body"><div class="compare-title">{x["title"]}</div><div class="lowest">최저가 {low}</div><a class="outline-btn" href="{url_for("compare_detail",item_id=x["id"])}">최저가 보기</a></div></div>'''


@app.route("/")
def home():
    conn=db()
    featured=conn.execute("SELECT * FROM products WHERE featured=1 ORDER BY id DESC LIMIT 4").fetchall()
    compares=conn.execute("SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c ORDER BY c.id DESC LIMIT 4").fetchall()
    vendors=conn.execute("SELECT * FROM vendors WHERE active=1 ORDER BY sort_order,id").fetchall()
    conn.close()
    return page("홈", r'''
    <div class="layout"><main>
    <section class="hero"><div><h1>좋은 제품을<br><strong>좋은 사람들과</strong><br>좋은 가격에</h1><p>보찌미가 엄선한 제품을<br>공동구매로 더 저렴하게!</p><a class="hero-btn" href="{{url_for('shop')}}">오늘의 찜 보러가기</a></div><div class="hero-art"><div class="product-mock"><div class="bottle one"></div><div class="bottle two"></div><div class="jar"></div></div><div class="bag">보찌미</div></div></section>
    <div class="shortcuts"><a class="shortcut" href="{{url_for('shop')}}"><div class="ico i1">🏷</div>오늘의 찜<br><small>특가 공동구매</small></a><a class="shortcut" href="{{url_for('brand_page',brand='엄마장독')}}"><div class="ico i2">🌿</div>엄마장독<br><small>브랜드관</small></a><a class="shortcut" href="{{url_for('brand_page',brand='RUBIE')}}"><div class="ico i3">♦</div>RUBIE<br><small>브랜드관</small></a><a class="shortcut" href="{{url_for('shop')}}"><div class="ico i4">🛍</div>전체<br><small>상품보기</small></a><a class="shortcut" href="{{url_for('compare')}}"><div class="ico i5">⌕</div>최저가 찾기<br><small>가격비교</small></a></div>
    <section class="section"><div class="section-head"><h2>오늘의 찜 / 공동구매</h2><a href="{{url_for('shop')}}">전체 보기 ›</a></div><div class="product-grid">{% for p in featured %}{{product_card(p)|safe}}{% endfor %}</div></section>
    <section class="section"><div class="section-head"><h2>최저가 찾기</h2><a href="{{url_for('compare')}}">전체 보기 ›</a></div><form class="compare-search" action="{{url_for('compare')}}"><input name="q" placeholder="상품명, 브랜드, 모델명으로 최저가를 찾아보세요!"><button>검색</button></form><div class="compare-grid">{% for x in compares %}{{compare_card(x)|safe}}{% endfor %}</div></section>
    </main><aside class="sidebar" id="vendors"><div class="vendor-box"><div class="vendor-head"><h3>보찌미 연결 벤더</h3><span>전체 보기 ›</span></div>{% for v in vendors %}<div class="vendor-item"><div class="vendor-logo">{{v['logo_text']}}</div><div><h4>{{v['name']}}</h4><p>{{v['subtext']}}</p><a class="vendor-link" href="{{v['url']}}" target="_blank">바로가기</a></div></div>{% endfor %}</div><div class="side-card partner"><h3 style="color:var(--pink)">판매자(벤더) 제휴 문의</h3><div style="font-size:13px">보찌미와 함께 성장할 벤더를 모집합니다!</div><a class="vendor-link" href="#">제휴 문의하기</a></div><div class="side-card"><h3>고객센터</h3><div style="font-size:13px;line-height:2">♡ 1:1 문의<br>♧ 공지사항<br>ⓘ 이용안내<br>? 자주 묻는 질문</div></div><div class="side-card kakao"><h3>카카오톡 채널</h3><div style="font-size:13px">보찌미 카카오톡으로 빠른 상담!</div><a class="btn" style="margin-top:10px;background:#ffe345" href="#">채널 추가</a></div></aside></div>
    ''',featured=featured,compares=compares,vendors=vendors,product_card=product_card,compare_card=compare_card)


@app.route("/shop")
def shop():
    conn=db(); products=conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall(); conn.close()
    return page("쇼핑",'<div class="section-head"><h2>보찌미 쇼핑</h2></div><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div>',products=products,product_card=product_card)


@app.route("/brand/<brand>")
def brand_page(brand):
    conn=db(); products=conn.execute("SELECT * FROM products WHERE brand=? ORDER BY id DESC",(brand,)).fetchall(); conn.close()
    return page(brand,'<section class="hero" style="min-height:230px"><div><h1>{{brand}}</h1><p>{% if brand==\'엄마장독\' %}김치 · 조선간장 · 된장{% else %}RUBIE 라이프 뷰티 브랜드{% endif %}</p></div><div class="hero-art"><div class="bag" style="height:140px">{{brand}}</div></div></section><section class="section"><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div></section>',brand=brand,products=products,product_card=product_card)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn=db(); p=conn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone(); conn.close()
    if not p:return "상품을 찾을 수 없습니다.",404
    return page(p["title"],'<div class="row"><div class="card-img" style="border-radius:12px;min-height:420px">{% if p[\'image_url\'] %}<img src="{{p[\'image_url\']}}">{% else %}🎁{% endif %}</div><div class="form" style="max-width:none;margin:0"><span class="tag">{{p[\'brand\']}}</span><h1>{{p[\'title\']}}</h1><div class="sale" style="font-size:30px">{% if p[\'sale_price\'] %}{{p[\'sale_price\']|money}}원{% else %}가격문의{% endif %}</div><p>{{p[\'subtitle\']}}</p><div style="white-space:pre-wrap;line-height:1.8">{{p[\'description\']}}</div></div></div>',p=p)


@app.route("/compare")
def compare():
    q=request.args.get("q","").strip(); conn=db()
    if q:
        like=f"%{q}%"; items=conn.execute("SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c WHERE c.title LIKE ? OR c.brand LIKE ? OR c.model_no LIKE ? ORDER BY c.id DESC",(like,like,like)).fetchall()
    else:
        items=conn.execute("SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c ORDER BY c.id DESC").fetchall()
    conn.close()
    return page("최저가 찾기",'<div class="section-head"><h2>최저가 찾기</h2></div><form class="compare-search"><input name="q" value="{{q}}" placeholder="상품명, 브랜드, 모델명을 입력하세요"><button>검색</button></form><div class="compare-grid">{% for x in items %}{{compare_card(x)|safe}}{% endfor %}</div>',items=items,q=q,compare_card=compare_card)


@app.route("/compare/<int:item_id>")
def compare_detail(item_id):
    conn=db(); item=conn.execute("SELECT * FROM compare_items WHERE id=?",(item_id,)).fetchone(); offers=conn.execute("SELECT *,price+shipping total FROM compare_offers WHERE item_id=? ORDER BY total ASC,id ASC",(item_id,)).fetchall(); conn.close()
    if not item:return "상품을 찾을 수 없습니다.",404
    best=offers[0]["total"] if offers else None
    return page(item["title"],'<div class="section-head"><h2>{{item[\'title\']}}</h2></div><div class="offer-table"><div class="offer-row head"><div>판매처</div><div>상품가</div><div>배송비</div><div>실구매가</div><div></div></div>{% for o in offers %}<div class="offer-row {% if o[\'total\']==best %}best{% endif %}"><div><b>{{o[\'seller\']}}</b>{% if o[\'total\']==best %} <span class="best-tag">최저가</span>{% endif %}<div style="font-size:11px;color:#777">{{o[\'note\']}}</div></div><div>{{o[\'price\']|money}}원</div><div>{% if o[\'shipping\'] %}{{o[\'shipping\']|money}}원{% else %}무료{% endif %}</div><div><b>{{o[\'total\']|money}}원</b></div><div></div></div>{% endfor %}</div>',item=item,offers=offers,best=best)


@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        conn=db(); a=conn.execute("SELECT * FROM admins WHERE username=?",(request.form.get("username",""),)).fetchone(); conn.close()
        if a and check_password_hash(a["password_hash"],request.form.get("password","")):
            session["admin"]=True; return redirect(url_for("admin_dashboard"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.")
    return page("관리자 로그인",'<div class="form"><h2>관리자 로그인</h2><form method="post"><div class="field"><label>아이디</label><input name="username" required></div><div class="field"><label>비밀번호</label><input type="password" name="password" required></div><button class="btn dark" style="width:100%">로그인</button></form></div>')


@app.route("/admin")
@admin_required
def admin_dashboard():
    return page("관리자",'<div class="form"><h2>보찌미 관리자</h2><p>상품·가격비교·벤더 관리 기능은 다음 단계에서 이 화면에 묶어서 확장하면 됩니다.</p><a class="btn pink" href="{{url_for(\'home\')}}">홈으로</a></div>')


if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")),debug=False)
