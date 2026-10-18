import os, sqlite3, secrets, hmac
from flask import Flask, request, session, redirect, abort, render_template_string, jsonify
app=Flask(__name__)
app.secret_key=os.environ.get("SOMANG_SECRET_KEY",secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=True)
DB=os.environ.get("SOMANG_DB_PATH","/tmp/somang_preview.sqlite3")
CATS=("화장품","일반 생활용품","건강기능식품","의약외품","의료기기")
def db():
    c=sqlite3.connect(DB,timeout=15)
    c.row_factory=sqlite3.Row
    return c
def setup():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,price INTEGER NOT NULL CHECK(price>=0),stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0),approved INTEGER NOT NULL DEFAULT 0,visible INTEGER NOT NULL DEFAULT 0,description TEXT NOT NULL DEFAULT '')")
        c.execute("CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL,quantity INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'draft',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
setup()
CSS="""<style>*{box-sizing:border-box}body{margin:0;font-family:Arial,'Apple SD Gothic Neo',sans-serif;background:#f7faf7;color:#204338}header{padding:18px 6%;background:#fff;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e0eae3}.brand{font-size:26px;font-weight:bold}a{color:#246b54;text-decoration:none}nav a{margin-left:18px}.hero{padding:65px 6%;background:linear-gradient(110deg,#e2f2e8,#fff9ee)}h1{font-size:clamp(34px,5vw,58px);margin:14px 0}main{max-width:1080px;margin:auto;padding:36px 20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.card{background:#fff;border:1px solid #dce7de;border-radius:15px;padding:22px;line-height:1.7}.card h3{margin:8px 0}.muted{color:#63766b}.tag{font-size:12px;color:#277458;font-weight:bold}button,.btn{display:inline-block;border:0;border-radius:8px;background:#267358;color:#fff;padding:11px 17px;cursor:pointer}input,select,textarea{border:1px solid #cddbd1;padding:11px;border-radius:7px;max-width:100%}label{display:block;margin:12px 0}footer{background:#204338;color:#fff;padding:25px 6%;line-height:1.8}footer a{color:#fff}.notice{background:#eaf3ec;padding:17px;border-radius:12px;line-height:1.8;margin:24px 0}.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.row form{display:inline}.danger{background:#9b514a}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}@media(max-width:600px){header{padding:14px}.brand{font-size:21px}nav a{margin-left:8px;font-size:12px}.hero{padding:50px 20px}}@media(max-width:600px){header{flex-wrap:wrap;gap:12px}nav{display:flex;flex-wrap:wrap;gap:12px}nav a{margin-left:0;font-size:14px}main{padding:24px 16px}main form>label{display:block;margin:14px 0;font-size:16px}main form>label>input,main form>label>select,main form>label>textarea{display:block;width:100%;max-width:100%;margin-top:7px;font-size:16px;min-height:46px}main form>button{min-height:46px;font-size:16px}footer{font-size:14px;overflow-wrap:anywhere}}.somang-hero{display:grid;grid-template-columns:1.1fr .9fr;align-items:center;gap:36px;padding:60px 6%;background:linear-gradient(100deg,#e7f0e9,#fff)}.somang-hero h1{font-size:clamp(34px,4.5vw,58px);line-height:1.25}.somang-hero p{line-height:1.8}.somang-photo-panel{height:350px;border-radius:20px;background:#e0ebe3;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;color:#236b51}.somang-photo-panel{width:100%;object-fit:cover}.somang-photo-panel span{font-size:40px;font-weight:800}.somang-photo-panel small{color:#627c70}@media(max-width:700px){.somang-hero{grid-template-columns:1fr;padding:36px 20px}.somang-photo-panel{height:240px}} .somang-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}.somang-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:11px 18px;border-radius:12px;background:#286f56;color:#fff;text-decoration:none;font-weight:700}.somang-actions a.secondary{background:#fff;color:#286f56;border:1px solid #286f56}.somang-categories{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.somang-category{border:1px solid #d9e6dc;background:#fff;border-radius:18px;padding:18px;min-height:145px}.somang-category .emoji{font-size:26px}.somang-category h3{font-size:20px;margin:12px 0 6px}.somang-category p{margin:0;color:#52675e}.somang-photo-panel{object-position:center 38%}@media(max-width:700px){.somang-categories{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.somang-category{padding:14px;min-height:126px}.somang-category h3{font-size:17px}.somang-category p{font-size:13px}.somang-actions a{flex:1 1 120px}.somang-photo-panel{object-fit:contain;background:#e6eee8;height:auto;max-height:430px}}.somang-photo-placeholder{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:linear-gradient(145deg,#e1eee5,#f5f9f5);color:#216b50;padding:22px}.somang-photo-placeholder .somang-photo-mark{font-size:52px;line-height:1}.somang-photo-placeholder strong{font-size:32px}.somang-photo-placeholder p{font-size:14px;margin:0;color:#567365}@media(max-width:700px){.somang-photo-placeholder{height:240px;min-height:240px}}.somang-photo-placeholder{background:radial-gradient(circle at 80% 20%,#fffdf1 0,#e5f0e8 45%,#d4e6da 100%);border:1px solid #c8ddce;box-shadow:0 12px 32px #1f53301a}.somang-photo-placeholder .somang-photo-mark{display:grid;place-items:center;width:92px;height:92px;border-radius:25px;background:#fff;color:#23805c;box-shadow:0 9px 25px #24664719;margin-bottom:8px}.somang-photo-placeholder strong{letter-spacing:-1px}.somang-photo-placeholder p{max-width:85%;line-height:1.6}@media(max-width:700px){.somang-photo-placeholder .somang-photo-mark{width:65px;height:65px;font-size:40px}.somang-photo-placeholder strong{font-size:29px}} .somang-mini-info{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:12px;padding:13px 10px;margin-top:25px;border-top:1px solid #e1e9e3;color:#66786d;font-size:13px}.somang-mini-info a{font-weight:600;font-size:13px}.somang-legal-note{font-size:11px;color:#78877c;text-align:center;margin:7px 0 0}footer{padding:14px 6%;font-size:12px;line-height:1.5} @media(max-width:600px){.somang-mini-info{gap:9px;font-size:12px}.somang-mini-info a{font-size:12px}footer{font-size:11px;padding:12px 5%}} .somang-mobile-nav{display:none}@media(max-width:700px){body{padding-bottom:64px}.somang-mobile-nav{display:grid;grid-template-columns:repeat(4,1fr);position:fixed;bottom:0;left:0;right:0;z-index:30;background:#fff;border-top:1px solid #d9e6dc;padding:6px 6px calc(6px + env(safe-area-inset-bottom));box-shadow:0 -4px 16px #173e3314}.somang-mobile-nav a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;font-size:11px;color:#285b47;min-height:46px}.somang-mobile-nav .ico{font-size:20px;line-height:1.2}} .somang-visit{margin:26px 0 10px;padding:22px;border-radius:18px;background:#eaf3ec}.somang-visit h2{margin:0 0 14px;font-size:23px}.somang-visit p{line-height:1.65;margin:8px 0}.somang-visit .somang-actions{margin-top:12px}@media(max-width:700px){.somang-visit{padding:17px}.somang-visit h2{font-size:20px}.somang-visit .somang-actions a{font-size:14px;min-height:42px}} .somang-visit{padding:0;background:#f1f7f2;border:1px solid #dfe9e0;margin:20px 0 5px}.somang-visit summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;font-size:14px;font-weight:700;list-style:none}.somang-visit summary::-webkit-details-marker{display:none}.somang-visit summary:after{content:'⌄';font-size:18px;color:#376b50}.somang-visit[open] summary:after{content:'⌃'}.somang-visit summary span{font-size:12px;font-weight:400;color:#607d6b}.somang-visit-detail{padding:0 16px 15px}.somang-visit-detail .somang-actions{margin:8px 0}.somang-visit-detail .somang-actions a{font-size:13px;min-height:40px}.somang-visit:target{scroll-margin-top:20px}  .somang-health-grid{margin-top:20px}.somang-health-grid .somang-category{min-height:195px}.somang-health-grid .somang-category p{line-height:1.65}.somang-health-note{margin:32px 0;padding:24px;border-radius:18px;background:#eaf3ec;line-height:1.8}.somang-store-link{margin:42px 0}.somang-store-link .somang-categories{margin-top:20px}.somang-store-link .somang-category{display:block;color:#204338;transition:transform .15s}.somang-store-link .somang-category:hover{transform:translateY(-3px)} </style>"""
def page(body,title="소망약국"):
    return render_template_string("<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='theme-color' content='#204338'><meta name='description' content='서울 종로구 창신동 소망약국 방문 안내. 종로 335, 1층. 전화 02-742-0075.'><title>{{title}}</title>"+CSS+"</head><body><header><a class='brand' href='/'>✚ 소망약국</a><nav><a href='/online-products'>온라인 상품</a><a href='/account'>회원 로그인</a><a href='/#info'>약국 안내</a><a href='/admin'>관리자</a></nav></header>"+body+"<footer>소망약국 · 서울특별시 종로구 종로 335, 1층 (원풍빌딩)<br><a href='tel:027420075'>02-742-0075</a><br>온라인 판매 상품은 품목별 적법성 확인 후 제공됩니다.</footer><nav class='somang-mobile-nav' aria-label='모바일 빠른 메뉴'><a href='/'><span class='ico' aria-hidden='true'>⌂</span>홈</a><a href='/online-products'><span class='ico' aria-hidden='true'>▦</span>온라인 상품</a><a href='/cart'><span class='ico' aria-hidden='true'>🛒</span>장바구니</a><a href='/account'><span class='ico' aria-hidden='true'>♙</span>마이페이지</a></nav></body></html>",title=title)
def csrf():
    if "csrf" not in session: session["csrf"]=secrets.token_urlsafe(32)
    return session["csrf"]
def verify():
    if not hmac.compare_digest(session.get("csrf",""),request.form.get("csrf","")) or not session.get("csrf"): abort(400)
def admin():
    if not os.environ.get("SOMANG_ADMIN_PASSWORD") or not os.environ.get("SOMANG_SECRET_KEY"): abort(503,"관리자 환경변수 설정 필요")
    if not session.get("admin"): abort(403)
@app.get("/")
def home():
    with db() as c: items=[dict(r) for r in c.execute("SELECT * FROM products WHERE approved=1 AND visible=1 AND stock>0 ORDER BY id DESC LIMIT 100")]
    body="""<section class='somang-hero'><div><div class='tag'>서울 종로구 창신동 · SOMANG PHARMACY</div><h1>건강한 일상을 위한<br>소망약국</h1><p>매일 실천할 수 있는 건강 관리 정보를 전합니다.<br>건강 상담과 의약품 문의는 약국에 방문하거나 전화해 주세요.</p><div class='somang-actions'><a href='#health'>오늘의 건강 안내</a><a class='secondary' href='#info' onclick="document.getElementById('info').open=true">약국 방문 안내</a></div></div><div class='somang-photo-panel somang-photo-placeholder' role='img' aria-label='소망약국 안내 일러스트'><div class='somang-photo-mark'>✚</div><strong>소망약국</strong><p>SOMANG PHARMACY · 건강한 일상의 가까운 이웃</p></div></section><main><section id='health'><h2>일상 건강 관리 가이드</h2><p class='muted'>누구나 실천할 수 있는 생활 속 건강 습관을 소개합니다.</p><div class='somang-categories somang-health-grid'><article class='somang-category'><span class='emoji'>💧</span><h3>수분 섭취</h3><p>갈증을 느끼기 전에도 조금씩 물을 마셔요. 심장·신장 질환으로 수분 제한이 있다면 의료진 지침을 따르세요.</p></article><article class='somang-category'><span class='emoji'>🚶</span><h3>가벼운 신체 활동</h3><p>오래 앉아 있었다면 잠깐 일어나 움직여 보세요. 자신의 체력과 건강 상태에 맞춰 무리하지 않는 것이 중요해요.</p></article><article class='somang-category'><span class='emoji'>🌙</span><h3>규칙적인 수면</h3><p>취침·기상 시간을 일정하게 유지하고 잠들기 전 밝은 화면과 카페인을 줄여 보세요.</p></article><article class='somang-category'><span class='emoji'>🧼</span><h3>손 위생</h3><p>식사 전과 외출 후, 기침·재채기 후에는 비누와 흐르는 물로 손을 충분히 씻으세요.</p></article></div></section><section class='somang-health-note'><h2>약 복용, 이렇게 확인하세요</h2><p>처방약과 일반의약품은 정해진 용법·용량을 확인하세요. 여러 약이나 건강기능식품을 함께 복용한다면 약사에게 상호작용을 상담하는 것이 좋아요.</p><p class='muted'>이 안내는 일반적인 건강 정보이며 개인별 진단·치료를 대신하지 않습니다. 심한 증상이나 응급 상황에는 즉시 의료기관에 도움을 요청하세요.</p><a class='btn' href='tel:027420075'>약국에 전화 문의</a></section><details class='somang-visit' id='info'><summary>소망약국 방문 안내 <span>주소 · 전화 · 길찾기</span></summary><div class='somang-visit-detail'><p>서울특별시 종로구 종로 335, 1층 (원풍빌딩)</p><p>대표약사 최연화 · 02-742-0075</p><div class='somang-actions'><a href='tel:027420075'>☎ 전화 걸기</a><a class='secondary' href='https://map.naver.com/p/search/%EC%86%8C%EB%A7%9D%EC%95%BD%EA%B5%AD%20%EC%A2%85%EB%A1%9C%20335' target='_blank' rel='noopener noreferrer'>지도·길찾기 ↗</a></div><p class='muted' style='font-size:12px'>영업시간은 전화로 확인해 주세요.</p></div></details><div class='somang-mini-info'><span>소망약국 · 종로 335, 1층</span><a href='tel:027420075'>전화</a><a href='https://map.naver.com/p/search/%EC%86%8C%EB%A7%9D%EC%95%BD%EA%B5%AD%20%EC%A2%85%EB%A1%9C%20335' target='_blank' rel='noopener noreferrer'>길찾기 ↗</a></div><p class='somang-legal-note'>의약품 온라인 판매 불가 · 현재 주문·결제 준비 중</p></main>"""
    return page(body)
@app.get("/online-products")
def online_products():
    body="""<main><p><a href='/'>← 소망약국 홈</a></p><h1 style='font-size:clamp(30px,4vw,44px)'>온라인 상품</h1><p class='muted'>소망약국 온라인 상품 안내와 쇼핑 체험을 모아 놓은 메뉴입니다.</p><section class='somang-store-link'><h2>상품은 온라인 스토어에서 확인하세요</h2><p class='muted'>더마 화장품, 두피·모발, 생활용품 등은 상품 페이지로 이동해 살펴볼 수 있어요. 현재는 체험용으로 실제 결제할 수 없습니다.</p><div class='somang-actions'><a href='/shop'>전체 상품 보기 →</a><a class='secondary' href='/cart'>장바구니</a></div><div class='somang-categories'><a class='somang-category' href='/shop?category=%EB%8D%94%EB%A7%88%20%ED%99%94%EC%9E%A5%ED%92%88'><span class='emoji'>🧴</span><h3>더마 화장품</h3><p>상품 페이지로 이동 ↗</p></a><a class='somang-category' href='/shop?category=%EB%91%90%ED%94%BC%C2%B7%EB%AA%A8%EB%B0%9C'><span class='emoji'>🌿</span><h3>두피·모발</h3><p>상품 페이지로 이동 ↗</p></a><a class='somang-category' href='/shop?category=%EC%83%9D%ED%99%9C%EC%9A%A9%ED%92%88'><span class='emoji'>🧼</span><h3>생활용품</h3><p>상품 페이지로 이동 ↗</p></a><a class='somang-category' href='/shop'><span class='emoji'>✨</span><h3>전체 상품</h3><p>판매 적법성 확인 후 순차 입점 ↗</p></a></div></section></main>"""
    return page(body,"온라인 상품 | 소망약국")
@app.route("/admin",methods=["GET","POST"])
def admin_panel():
    if not os.environ.get("SOMANG_ADMIN_PASSWORD") or not os.environ.get("SOMANG_SECRET_KEY"):
        return page("<main><h2>관리자 초기 설정 필요</h2><p>관리자 비밀번호 및 보안키를 서버 환경변수로 설정해야 합니다.</p></main>"),503
    if request.method=="POST":
        verify()
        if hmac.compare_digest(request.form.get("password",""),os.environ["SOMANG_ADMIN_PASSWORD"]):
            session.clear();session["admin"]=True
            return redirect("/admin")
        abort(403)
    if not session.get("admin"):
        return page("<main><h2>관리자 로그인</h2><form method='post'><input type='hidden' name='csrf' value='{{csrf}}'><label>비밀번호 <input type='password' name='password' required></label><button>로그인</button></form></main>".replace("{{csrf}}",csrf()))
    with db() as c: items=[dict(r) for r in c.execute("SELECT * FROM products ORDER BY id DESC LIMIT 100")]
    from markupsafe import escape
    body="<main><div class='notice'><strong>운영 메뉴</strong><p><a href='/admin/ops'>운영 대시보드</a> · <a href='/admin/ops/suppliers'>공급사·발주</a> · <a href='/admin/ops/stock'>재고</a> · <a href='/admin/ops/lots'>로트·유통기한</a> · <a href='/admin/ops/ledger'>장부</a> · <a href='/admin/reports/summary'>보고서</a> · <a href='/admin/members'>회원 관리</a> · <a href='/admin/returns'>반품·환불 관리</a> · <a href='/policy/returns'>반품 정책</a></p></div><h2>상품·재고 관리</h2><p class='muted'>신규 상품은 비공개·미승인으로 저장됩니다. 별도의 적법성 검토 전 공개할 수 없습니다.</p><form method='post' action='/admin/products'><input type='hidden' name='csrf' value='"+csrf()+"'><label>상품명 <input name='name' required maxlength='100'></label><label>상품 분류 <select name='category'>"+''.join("<option>"+x+"</option>" for x in CATS)+"</select></label><label>가격(원) <input name='price' type='number' min='0' required></label><label>재고 <input name='stock' type='number' min='0' required></label><label>설명 <textarea name='description' maxlength='1000'></textarea></label><button>비공개 상품 등록</button></form><h2>등록 상품</h2><div class='grid'>"
    for p in items:
        body+=f"<div class='card'><h3>{escape(p['name'])}</h3><p>{escape(p['category'])} · {p['price']:,}원</p><p>승인 {p['approved']} / 공개 {p['visible']}</p><form action='/admin/products/{p['id']}/stock' method='post'><input type='hidden' name='csrf' value='{csrf()}'><label>재고 <input name='stock' type='number' min='0' value='{p['stock']}'></label><button>재고 저장</button></form><form action='/admin/products/{p['id']}/hide' method='post'><input type='hidden' name='csrf' value='{csrf()}'><button class='danger'>상품 숨기기</button></form></div>"
    return page(body+"</div><p class='notice'>실제 주문·결제·환불은 PG 계약 및 영업 적법성 확인 후 별도 검증을 거쳐 연결합니다. 무료 임시 서버의 데이터는 재배포 시 사라질 수 있습니다.</p></main>")
@app.post("/admin/products")
def add():
    admin();verify()
    category=request.form.get("category","")
    if category not in CATS:abort(400)
    name=request.form.get("name","").strip()[:100]
    if not name:abort(400)
    try:price=int(request.form.get("price",""));stock=int(request.form.get("stock",""))
    except ValueError:abort(400)
    if price<0 or stock<0:abort(400)
    with db() as c:c.execute("INSERT INTO products(name,category,price,stock,description) VALUES(?,?,?,?,?)",(name,category,price,stock,request.form.get("description","")[:1000]))
    return redirect("/admin")
@app.post("/admin/products/<int:pid>/stock")
def stock(pid):
    admin();verify()
    try:qty=int(request.form.get("stock",""))
    except ValueError:abort(400)
    if qty<0:abort(400)
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        previous=c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()
        if previous is None:abort(404)
        delta=qty-previous["stock"]
        if delta:
            c.execute("UPDATE products SET stock=? WHERE id=?",(qty,pid))
            c.execute("INSERT INTO stock_movements(product_id,change_qty,reason) VALUES(?,?,?)",(pid,delta,"관리자 직접 재고 수정"))
            c.execute("INSERT INTO ops_audit(action,details) VALUES(?,?)",("stock.admin_update",f"product={pid},delta={delta}"))
    return redirect("/admin")
@app.post("/admin/products/<int:pid>/hide")
def hide(pid):
    admin();verify()
    with db() as c:c.execute("UPDATE products SET visible=0 WHERE id=?",(pid,))
    return redirect("/admin")
@app.get("/health")
def health():return jsonify(status="ok",payments_enabled=False,admin_configured=bool(os.environ.get("SOMANG_ADMIN_PASSWORD")))

# Isolated operations blueprint; uses the same admin session and demo database.
from somang_ops import ops
app.register_blueprint(ops)

from somang_shop import shop
app.register_blueprint(shop)

from somang_payment import payment
app.register_blueprint(payment)

from somang_launch import launch
app.register_blueprint(launch)

from somang_reports import reports
app.register_blueprint(reports)

from somang_management import manage
app.register_blueprint(manage)
