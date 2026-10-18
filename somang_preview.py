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
CSS="""<style>*{box-sizing:border-box}body{margin:0;font-family:Arial,'Apple SD Gothic Neo',sans-serif;background:#f7faf7;color:#204338}header{padding:18px 6%;background:#fff;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e0eae3}.brand{font-size:26px;font-weight:bold}a{color:#246b54;text-decoration:none}nav a{margin-left:18px}.hero{padding:65px 6%;background:linear-gradient(110deg,#e2f2e8,#fff9ee)}h1{font-size:clamp(34px,5vw,58px);margin:14px 0}main{max-width:1080px;margin:auto;padding:36px 20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.card{background:#fff;border:1px solid #dce7de;border-radius:15px;padding:22px;line-height:1.7}.card h3{margin:8px 0}.muted{color:#63766b}.tag{font-size:12px;color:#277458;font-weight:bold}button,.btn{display:inline-block;border:0;border-radius:8px;background:#267358;color:#fff;padding:11px 17px;cursor:pointer}input,select,textarea{border:1px solid #cddbd1;padding:11px;border-radius:7px;max-width:100%}label{display:block;margin:12px 0}footer{background:#204338;color:#fff;padding:25px 6%;line-height:1.8}footer a{color:#fff}.notice{background:#eaf3ec;padding:17px;border-radius:12px;line-height:1.8;margin:24px 0}.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.row form{display:inline}.danger{background:#9b514a}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}@media(max-width:600px){header{padding:14px}.brand{font-size:21px}nav a{margin-left:8px;font-size:12px}.hero{padding:50px 20px}}</style>"""
def page(body,title="소망약국"):
    return render_template_string("<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{{title}}</title>"+CSS+"</head><body><header><a class='brand' href='/'>✚ 소망약국</a><nav><a href='/#products'>스토어</a><a href='/#info'>약국 안내</a><a href='/admin'>관리자</a></nav></header>"+body+"<footer>소망약국 · 서울특별시 종로구 종로 335, 1층 (원풍빌딩)<br><a href='tel:027420075'>02-742-0075</a><br>온라인 판매 상품은 품목별 적법성 확인 후 제공됩니다.</footer></body></html>",title=title)
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
    body="""<section class='hero'><div class='tag'>SOMANG PHARMACY · 서울 종로</div><h1>건강한 일상에<br>소망을 더합니다.</h1><p>소망약국의 생활건강·뷰티 상품을 만나보세요.</p><a class='btn' href='#products'>상품 보기 →</a></section><main><h2 id='products'>온라인 스토어</h2><p class='muted'>승인된 온라인 판매 가능 상품만 노출됩니다.</p><div class='grid'>"""
    for p in items:
        from markupsafe import escape
        body+=f"<div class='card'><span class='tag'>{escape(p['category'])}</span><h3>{escape(p['name'])}</h3><p>{escape(p['description'])}</p><strong>{p['price']:,}원</strong><p class='muted'>재고 {p['stock']}개</p><p class='tag'>결제 연결 준비 중</p></div>"
    if not items: body+="<div class='card'>판매 자격과 상품별 적법성 검토를 마친 상품을 준비하고 있습니다.</div>"
    body+="""</div><h2 style='margin-top:45px'>입점 예정 상품군</h2><div class='grid'><div class='card'>🧴<h3>더마 화장품</h3><p>보습·클렌징</p></div><div class='card'>🌿<h3>두피·모발</h3><p>샴푸·토닉</p></div><div class='card'>🪮<h3>생활용품</h3><p>건강관리 액세서리</p></div><div class='card'>✨<h3>건강기능식품</h3><p>자격 확인 후 입점</p></div></div><div class='notice' id='info'><h2>소망약국 오시는 길</h2>대표약사 최연화<br>서울특별시 종로구 종로 335, 1층 (원풍빌딩)<br><a href='tel:027420075'>☎ 02-742-0075</a><br><a href='https://map.naver.com/p/search/%EC%86%8C%EB%A7%9D%EC%95%BD%EA%B5%AD%20%EC%A2%85%EB%A1%9C%20335'>지도 보기 ↗</a></div><p class='muted'>※ 일반의약품·전문의약품 온라인 판매 불가. 현재 결제·주문 접수 비활성화. 영업시간 확인 후 게시.</p></main>"""
    return page(body)
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
    body="<main><h2>상품·재고 관리</h2><p class='muted'>신규 상품은 비공개·미승인으로 저장됩니다. 별도의 적법성 검토 전 공개할 수 없습니다.</p><form method='post' action='/admin/products'><input type='hidden' name='csrf' value='"+csrf()+"'><label>상품명 <input name='name' required maxlength='100'></label><label>상품 분류 <select name='category'>"+''.join("<option>"+x+"</option>" for x in CATS)+"</select></label><label>가격(원) <input name='price' type='number' min='0' required></label><label>재고 <input name='stock' type='number' min='0' required></label><label>설명 <textarea name='description' maxlength='1000'></textarea></label><button>비공개 상품 등록</button></form><h2>등록 상품</h2><div class='grid'>"
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
    with db() as c:c.execute("UPDATE products SET stock=? WHERE id=?",(qty,pid))
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
