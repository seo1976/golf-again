import os, sqlite3
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bojjimi.db')
ADMIN_ID = os.environ.get('ADMIN_ID', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-me-1234')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'bojjimi-change-this-secret')


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript('''
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
      FOREIGN KEY(item_id) REFERENCES compare_items(id)
    );
    ''')
    if not conn.execute('SELECT 1 FROM admins WHERE username=?', (ADMIN_ID,)).fetchone():
        conn.execute('INSERT INTO admins(username,password_hash) VALUES(?,?)',
                     (ADMIN_ID, generate_password_hash(ADMIN_PASSWORD)))
    if conn.execute('SELECT COUNT(*) c FROM products').fetchone()['c'] == 0:
        conn.executemany('''INSERT INTO products(product_type,brand,category,title,subtitle,original_price,sale_price,buy_url,description,badge,status,featured)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', [
            ('자체브랜드','엄마장독','식품','엄마장독 김치','정성 가득 집김치',35000,29900,'#','엄마장독 대표 상품입니다.','대표상품','판매중',1),
            ('자체브랜드','엄마장독','식품','엄마가 만든 조선간장','깊고 깔끔한 장맛',25000,22000,'#','집밥의 기본이 되는 조선간장입니다.','엄마장독','판매중',1),
            ('자체브랜드','RUBIE','뷰티','RUBIE 천연오일 케어','루비에 브랜드 준비중',None,None,'#','RUBIE 브랜드관입니다.','COMING SOON','준비중',1)
        ])
    if conn.execute('SELECT COUNT(*) c FROM compare_items').fetchone()['c'] == 0:
        cur = conn.execute('''INSERT INTO compare_items(title,brand,model_no,category,description)
                              VALUES(?,?,?,?,?)''',
                           ('가격비교 테스트 상품','테스트브랜드','TEST-001','생활','같은 상품의 판매처별 가격을 비교하는 예시입니다.'))
        item_id = cur.lastrowid
        conn.executemany('''INSERT INTO compare_offers(item_id,seller,price,shipping,buy_url,note)
                            VALUES(?,?,?,?,?,?)''', [
            (item_id,'A 쇼핑몰',15900,3000,'#','일반배송'),
            (item_id,'B 쇼핑몰',16900,0,'#','무료배송'),
            (item_id,'C 쇼핑몰',14900,2500,'#','회원가입 불필요')
        ])
    conn.commit(); conn.close()


init_db()


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            flash('관리자 로그인이 필요합니다.')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


def money(v):
    return '' if v in (None, '') else f'{int(v):,}'

app.jinja_env.filters['money'] = money

BASE = '''
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} | 보찌미</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f7f5;color:#20242a;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}a{text-decoration:none;color:inherit}
header{background:#fff;border-bottom:1px solid #e8e7e3;position:sticky;top:0;z-index:30}.nav{max-width:1180px;margin:auto;padding:14px 18px;display:flex;align-items:center;gap:16px}.logo{font-size:27px;font-weight:950;color:#182436}.logo span{color:#ff7b36}.navlinks{margin-left:auto;display:flex;gap:14px;font-size:14px}.wrap{max-width:1180px;margin:auto;padding:25px 18px 70px}.flash{background:#fff3c8;border:1px solid #ecd783;padding:11px 13px;border-radius:10px;margin-bottom:14px}
.hero{background:linear-gradient(135deg,#182436,#334866);color:#fff;border-radius:26px;padding:48px 38px;display:grid;grid-template-columns:1.3fr .7fr;align-items:center}.hero h1{font-size:42px;margin:0 0 12px}.hero-mark{text-align:center;font-size:100px}.btn{display:inline-block;border:1px solid #e8e7e3;background:#fff;border-radius:11px;padding:10px 14px;font-weight:850;cursor:pointer}.orange{background:#ff7b36!important;border-color:#ff7b36!important;color:#fff}.green{background:#14875d!important;border-color:#14875d!important;color:#fff}.dark{background:#182436!important;border-color:#182436!important;color:#fff}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}.section{margin-top:38px}.section-title{display:flex;justify-content:space-between;align-items:end;gap:10px;margin-bottom:15px}.section-title h2{margin:0}.muted{color:#737980;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.card{background:#fff;border:1px solid #e8e7e3;border-radius:17px;overflow:hidden}.image{aspect-ratio:1/1;background:#ece9e3;display:flex;align-items:center;justify-content:center;font-size:60px;overflow:hidden}.image img{width:100%;height:100%;object-fit:cover}.card-body{padding:14px}.brand{font-size:12px;font-weight:900;color:#ff7b36}.title{font-weight:900;margin-top:6px}.price{font-size:19px;font-weight:950;margin-top:10px}.original{text-decoration:line-through;color:#9da2a6;font-size:12px;margin-left:5px}
.compare-search{background:#fff;border:1px solid #e8e7e3;border-radius:16px;padding:15px;display:flex;gap:8px}.compare-search input{flex:1;border:1px solid #d7d8d4;border-radius:9px;padding:12px;font:inherit}.compare-list{display:grid;gap:12px}.compare-card{background:#fff;border:1px solid #e8e7e3;border-radius:16px;padding:17px;display:grid;grid-template-columns:90px 1fr auto;gap:15px;align-items:center}.compare-thumb{width:90px;height:90px;border-radius:13px;background:#eeeae5;display:flex;align-items:center;justify-content:center;font-size:38px;overflow:hidden}.compare-thumb img{width:100%;height:100%;object-fit:cover}.offer-table{background:#fff;border:1px solid #e8e7e3;border-radius:16px;overflow:hidden}.offer-row{display:grid;grid-template-columns:1.1fr .8fr .8fr .8fr 110px;gap:10px;padding:14px 15px;border-bottom:1px solid #e8e7e3;align-items:center}.offer-row.head{background:#f0f3f5;font-weight:900}.offer-row.best{background:#fff7ef}.best-tag{display:inline-block;background:#ff7b36;color:#fff;font-size:11px;font-weight:900;padding:4px 7px;border-radius:7px}
.form{max-width:780px;margin:auto;background:#fff;border:1px solid #e8e7e3;border-radius:20px;padding:25px}.field{margin:15px 0}.field label{display:block;font-size:13px;font-weight:900;margin-bottom:7px}.field input,.field select,.field textarea{width:100%;padding:12px;border:1px solid #d7d8d4;border-radius:9px;font:inherit}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.admin-box{border:1px solid #e8e7e3;border-radius:16px;overflow:hidden}.admin-row{display:grid;grid-template-columns:70px 1fr 120px 140px;gap:10px;background:#fff;border-bottom:1px solid #e8e7e3;padding:13px 15px;align-items:center}.empty{background:#fff;border-radius:16px;padding:40px;text-align:center;color:#737980}footer{background:#182436;color:#dfe4e9;text-align:center;padding:30px;font-size:12px;margin-top:60px}
@media(max-width:800px){.navlinks a:nth-child(3),.navlinks a:nth-child(4){display:none}.hero{grid-template-columns:1fr;padding:32px 22px}.hero h1{font-size:31px}.hero-mark{font-size:65px}.grid{grid-template-columns:repeat(2,1fr);gap:10px}.row{grid-template-columns:1fr}.compare-card{grid-template-columns:70px 1fr}.compare-thumb{width:70px;height:70px}.compare-card>div:last-child{grid-column:1/-1}.offer-row{grid-template-columns:1fr 1fr}.offer-row>div:nth-child(4),.offer-row>div:nth-child(5){display:none}.offer-row.head{display:none}.admin-row{grid-template-columns:60px 1fr}.admin-row>div:nth-child(3),.admin-row>div:nth-child(4){display:none}}
</style></head><body>
<header><div class="nav"><a class="logo" href="{{url_for('home')}}">보<span>찌미</span></a><div class="navlinks"><a href="{{url_for('shop')}}">쇼핑</a><a href="{{url_for('compare')}}">최저가 찾기</a><a href="{{url_for('brand_page',brand='엄마장독')}}">엄마장독</a><a href="{{url_for('brand_page',brand='RUBIE')}}">RUBIE</a>{% if session.get('admin') %}<a href="{{url_for('admin_dashboard')}}">관리자</a>{% else %}<a href="{{url_for('admin_login')}}">관리자</a>{% endif %}</div></div></header>
<div class="wrap">{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}{{content|safe}}</div>
<footer><b>보찌미 · BOJJIMI</b><br>좋은 것만 골라 찜.<br><br>© 2026 BOJJIMI</footer></body></html>
'''


def page(title, body, **ctx):
    return render_template_string(BASE, title=title, content=render_template_string(body, **ctx))


def product_card(p):
    img = f'<img src="{p["image_url"]}" alt="">' if p['image_url'] else '🎁'
    original = f'<span class="original">{money(p["original_price"])}원</span>' if p['original_price'] else ''
    sale = f'{money(p["sale_price"])}원' if p['sale_price'] else '가격문의'
    return f'''<a class="card" href="{url_for('product_detail',product_id=p['id'])}"><div class="image">{img}</div><div class="card-body"><div class="brand">{p['brand'] or p['product_type']}</div><div class="title">{p['title']}</div><div class="muted">{p['subtitle'] or ''}</div><div class="price">{sale}{original}</div></div></a>'''


@app.route('/')
def home():
    conn=db(); featured=conn.execute('SELECT * FROM products WHERE featured=1 ORDER BY id DESC LIMIT 8').fetchall(); conn.close()
    return page('홈','''<section class="hero"><div><div style="font-weight:900;letter-spacing:2px">BOJJIMI</div><h1>좋은 것만 골라, 찜.</h1><p>엄마장독 · RUBIE · 공동구매 · 판매처별 최저가 비교까지.<br>보찌미에서 사고 싶은 것을 더 쉽게 찾으세요.</p><div class="actions"><a class="btn orange" href="{{url_for('shop')}}">쇼핑 둘러보기</a><a class="btn green" href="{{url_for('compare')}}">🔎 최저가 찾기</a></div></div><div class="hero-mark">🎁</div></section><section class="section"><div class="section-title"><div><h2>오늘의 찜 🔥</h2><div class="muted">보찌미 추천 상품</div></div></div><div class="grid">{% for p in featured %}{{product_card(p)|safe}}{% endfor %}</div></section>''',featured=featured,product_card=product_card)


@app.route('/shop')
def shop():
    conn=db(); products=conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); conn.close()
    return page('쇼핑','''<div class="section-title"><div><h2>보찌미 쇼핑</h2><div class="muted">상품 제한 없이 좋은 것만</div></div></div><div class="grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div>''',products=products,product_card=product_card)


@app.route('/brand/<brand>')
def brand_page(brand):
    conn=db(); products=conn.execute('SELECT * FROM products WHERE brand=? ORDER BY id DESC',(brand,)).fetchall(); conn.close()
    return page(brand,'''<section class="hero" style="padding:34px 28px"><div><h1>{{brand}}</h1><p>{% if brand=='엄마장독' %}김치 · 조선간장 · 된장{% else %}RUBIE 브랜드관{% endif %}</p></div><div class="hero-mark">✨</div></section><section class="section"><div class="grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div></section>''',brand=brand,products=products,product_card=product_card)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn=db(); p=conn.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone(); conn.close()
    if not p: return '상품을 찾을 수 없습니다.',404
    return page(p['title'],'''<div class="form"><div class="brand">{{p['brand'] or p['product_type']}}</div><h1>{{p['title']}}</h1><div class="price">{% if p['sale_price'] %}{{p['sale_price']|money}}원{% else %}가격문의{% endif %}</div><p>{{p['description'] or ''}}</p>{% if p['buy_url'] and p['buy_url']!='#' %}<a class="btn orange" href="{{p['buy_url']}}" target="_blank">구매하러 가기 →</a>{% endif %}</div>''',p=p)


@app.route('/compare')
def compare():
    q=request.args.get('q','').strip(); conn=db()
    if q:
        like=f'%{q}%'; items=conn.execute('''SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c WHERE c.title LIKE ? OR c.brand LIKE ? OR c.model_no LIKE ? ORDER BY c.id DESC''',(like,like,like)).fetchall()
    else:
        items=conn.execute('''SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c ORDER BY c.id DESC''').fetchall()
    conn.close()
    return page('최저가 찾기','''<div class="section-title"><div><h2>🔎 최저가 찾기</h2><div class="muted">상품가 + 배송비 기준</div></div></div><form class="compare-search"><input name="q" value="{{q}}" placeholder="상품명 · 브랜드 · 모델번호 검색"><button class="btn green">검색</button></form><div style="height:18px"></div>{% if items %}<div class="compare-list">{% for x in items %}<a class="compare-card" href="{{url_for('compare_detail',item_id=x['id'])}}"><div class="compare-thumb">🔎</div><div><div class="brand">{{x['brand'] or '가격비교'}}</div><div class="title">{{x['title']}}</div><div class="muted">{{x['model_no'] or ''}}</div></div><div>{% if x['lowest'] is not none %}<div class="muted">최저 실구매가</div><div class="price">{{x['lowest']|money}}원</div>{% else %}가격 준비중{% endif %}</div></a>{% endfor %}</div>{% else %}<div class="empty">검색 결과가 없습니다.</div>{% endif %}''',items=items,q=q)


@app.route('/compare/<int:item_id>')
def compare_detail(item_id):
    conn=db(); item=conn.execute('SELECT * FROM compare_items WHERE id=?',(item_id,)).fetchone(); offers=conn.execute('''SELECT *,(price+shipping) total FROM compare_offers WHERE item_id=? ORDER BY total ASC,id ASC''',(item_id,)).fetchall(); conn.close()
    if not item: return '상품을 찾을 수 없습니다.',404
    best=offers[0]['total'] if offers else None
    return page(item['title'],'''<div class="section-title"><div><h2>{{item['title']}}</h2><div class="muted">{{item['brand'] or ''}} · {{item['model_no'] or ''}}</div></div></div>{% if offers %}<div class="offer-table"><div class="offer-row head"><div>판매처</div><div>상품가</div><div>배송비</div><div>실구매가</div><div></div></div>{% for o in offers %}<div class="offer-row {% if o['total']==best %}best{% endif %}"><div><b>{{o['seller']}}</b>{% if o['total']==best %} <span class="best-tag">최저가</span>{% endif %}<div class="muted">{{o['note'] or ''}}</div></div><div>{{o['price']|money}}원</div><div>{% if o['shipping'] %}{{o['shipping']|money}}원{% else %}무료{% endif %}</div><div><b>{{o['total']|money}}원</b></div><div>{% if o['buy_url']!='#' %}<a class="btn orange" href="{{o['buy_url']}}" target="_blank">구매</a>{% else %}<span class="muted">테스트</span>{% endif %}</div></div>{% endfor %}</div><p class="muted">※ 쿠폰·카드할인·회원등급에 따라 실제 결제금액은 달라질 수 있습니다.</p>{% else %}<div class="empty">판매처 가격이 없습니다.</div>{% endif %}''',item=item,offers=offers,best=best)


@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        conn=db(); a=conn.execute('SELECT * FROM admins WHERE username=?',(request.form.get('username',''),)).fetchone(); conn.close()
        if a and check_password_hash(a['password_hash'],request.form.get('password','')):
            session['admin']=True; return redirect(url_for('admin_dashboard'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return page('관리자 로그인','''<div class="form"><h2>관리자 로그인</h2><form method="post"><div class="field"><label>아이디</label><input name="username" required></div><div class="field"><label>비밀번호</label><input type="password" name="password" required></div><button class="btn dark" style="width:100%">로그인</button></form></div>''')


@app.route('/admin/logout')
def admin_logout(): session.clear(); return redirect(url_for('home'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    conn=db(); items=conn.execute('''SELECT c.*,(SELECT COUNT(*) FROM compare_offers o WHERE o.item_id=c.id) offer_count FROM compare_items c ORDER BY c.id DESC''').fetchall(); conn.close()
    return page('관리자','''<div class="section-title"><div><h2>보찌미 관리자</h2><div class="muted">최저가 비교 상품 관리</div></div><div><a class="btn green" href="{{url_for('admin_compare_new')}}">+ 비교상품 등록</a> <a class="btn" href="{{url_for('admin_logout')}}">로그아웃</a></div></div><div class="admin-box">{% for x in items %}<div class="admin-row"><div>{{x['id']}}</div><div><b>{{x['title']}}</b><div class="muted">판매처 {{x['offer_count']}}개</div></div><div>{{x['model_no'] or ''}}</div><div><a href="{{url_for('admin_offer_new',item_id=x['id'])}}">+ 가격추가</a></div></div>{% endfor %}</div>''',items=items)


@app.route('/admin/compare/new',methods=['GET','POST'])
@admin_required
def admin_compare_new():
    if request.method=='POST':
        conn=db(); conn.execute('INSERT INTO compare_items(title,brand,model_no,category,image_url,description) VALUES(?,?,?,?,?,?)',(request.form['title'],request.form.get('brand',''),request.form.get('model_no',''),request.form.get('category',''),request.form.get('image_url',''),request.form.get('description',''))); conn.commit(); conn.close(); return redirect(url_for('admin_dashboard'))
    return page('비교상품 등록','''<div class="form"><h2>최저가 비교 상품 등록</h2><form method="post"><div class="field"><label>상품명</label><input name="title" required></div><div class="row"><div class="field"><label>브랜드</label><input name="brand"></div><div class="field"><label>모델번호</label><input name="model_no"></div></div><div class="field"><label>카테고리</label><input name="category"></div><div class="field"><label>이미지 URL</label><input name="image_url"></div><div class="field"><label>설명</label><textarea name="description"></textarea></div><button class="btn green" style="width:100%">등록</button></form></div>''')


@app.route('/admin/compare/<int:item_id>/offer/new',methods=['GET','POST'])
@admin_required
def admin_offer_new(item_id):
    conn=db(); item=conn.execute('SELECT * FROM compare_items WHERE id=?',(item_id,)).fetchone(); conn.close()
    if not item: return '상품 없음',404
    if request.method=='POST':
        conn=db(); conn.execute('INSERT INTO compare_offers(item_id,seller,price,shipping,buy_url,note) VALUES(?,?,?,?,?,?)',(item_id,request.form['seller'],int(request.form['price']),int(request.form.get('shipping') or 0),request.form['buy_url'],request.form.get('note',''))); conn.commit(); conn.close(); return redirect(url_for('compare_detail',item_id=item_id))
    return page('판매처 가격 추가','''<div class="form"><h2>{{item['title']}} · 판매처 가격 추가</h2><form method="post"><div class="field"><label>판매처</label><input name="seller" required placeholder="예: 쿠팡"></div><div class="row"><div class="field"><label>상품가</label><input type="number" name="price" required></div><div class="field"><label>배송비</label><input type="number" name="shipping" value="0"></div></div><div class="field"><label>구매 링크</label><input name="buy_url" required placeholder="https://..."></div><div class="field"><label>메모</label><input name="note" placeholder="무료배송 / 회원가 등"></div><button class="btn green" style="width:100%">가격 등록</button></form></div>''',item=item)


if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=False)
