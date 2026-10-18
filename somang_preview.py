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
CSS="""<style>*{box-sizing:border-box}body{margin:0;font-family:Arial,'Apple SD Gothic Neo',sans-serif;background:#f7faf7;color:#204338}header{padding:18px 6%;background:#fff;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e0eae3}.brand{font-size:26px;font-weight:bold}a{color:#246b54;text-decoration:none}nav a{margin-left:18px}.hero{padding:65px 6%;background:linear-gradient(110deg,#e2f2e8,#fff9ee)}h1{font-size:clamp(34px,5vw,58px);margin:14px 0}main{max-width:1080px;margin:auto;padding:36px 20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.card{background:#fff;border:1px solid #dce7de;border-radius:15px;padding:22px;line-height:1.7}.card h3{margin:8px 0}.muted{color:#63766b}.tag{font-size:12px;color:#277458;font-weight:bold}button,.btn{display:inline-block;border:0;border-radius:8px;background:#267358;color:#fff;padding:11px 17px;cursor:pointer}input,select,textarea{border:1px solid #cddbd1;padding:11px;border-radius:7px;max-width:100%}label{display:block;margin:12px 0}footer{background:#204338;color:#fff;padding:25px 6%;line-height:1.8}footer a{color:#fff}.notice{background:#eaf3ec;padding:17px;border-radius:12px;line-height:1.8;margin:24px 0}.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.row form{display:inline}.danger{background:#9b514a}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}@media(max-width:600px){header{padding:14px}.brand{font-size:21px}nav a{margin-left:8px;font-size:12px}.hero{padding:50px 20px}}@media(max-width:600px){header{flex-wrap:wrap;gap:12px}nav{display:flex;flex-wrap:wrap;gap:12px}nav a{margin-left:0;font-size:14px}main{padding:24px 16px}main form>label{display:block;margin:14px 0;font-size:16px}main form>label>input,main form>label>select,main form>label>textarea{display:block;width:100%;max-width:100%;margin-top:7px;font-size:16px;min-height:46px}main form>button{min-height:46px;font-size:16px}footer{font-size:14px;overflow-wrap:anywhere}}.somang-hero{display:grid;grid-template-columns:1.1fr .9fr;align-items:center;gap:36px;padding:60px 6%;background:linear-gradient(100deg,#e7f0e9,#fff)}.somang-hero h1{font-size:clamp(34px,4.5vw,58px);line-height:1.25}.somang-hero p{line-height:1.8}.somang-photo-panel{height:350px;border-radius:20px;background:#e0ebe3;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;color:#236b51}.somang-photo-panel{width:100%;object-fit:cover}.somang-photo-panel span{font-size:40px;font-weight:800}.somang-photo-panel small{color:#627c70}@media(max-width:700px){.somang-hero{grid-template-columns:1fr;padding:36px 20px}.somang-photo-panel{height:240px}} .somang-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}.somang-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:11px 18px;border-radius:12px;background:#286f56;color:#fff;text-decoration:none;font-weight:700}.somang-actions a.secondary{background:#fff;color:#286f56;border:1px solid #286f56}.somang-categories{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.somang-category{border:1px solid #d9e6dc;background:#fff;border-radius:18px;padding:18px;min-height:145px}.somang-category .emoji{font-size:26px}.somang-category h3{font-size:20px;margin:12px 0 6px}.somang-category p{margin:0;color:#52675e}.somang-photo-panel{object-position:center 38%}@media(max-width:700px){.somang-categories{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.somang-category{padding:14px;min-height:126px}.somang-category h3{font-size:17px}.somang-category p{font-size:13px}.somang-actions a{flex:1 1 120px}.somang-photo-panel{object-fit:contain;background:#e6eee8;height:auto;max-height:430px}}</style>"""
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
    body="""<section class='somang-hero'><div><div class='tag'>서울 종로구 창신동 · SOMANG PHARMACY</div><h1>우리 동네 가까운 약국,<br>소망약국</h1><p>종로 335, 1층에 위치한 소망약국입니다.<br>방문 전 약국 정보를 확인하세요.</p><div class='somang-actions'><a href='#info'>방문 안내</a><a class='secondary' href='tel:027420075'>전화 문의</a></div></div><img class='somang-photo-panel' src='data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDADIiJSwlHzIsKSw4NTI7S31RS0VFS5ltc1p9tZ++u7Kfr6zI4f/zyNT/16yv+v/9////////wfD/////////////2wBDATU4OEtCS5NRUZP/zq/O////////////////////////////////////////////////////////////////////wAARCACRAGYDASIAAhEBAxEB/8QAGQAAAwEBAQAAAAAAAAAAAAAAAAEDAgQF/8QAMBAAAgIABAMHBAEFAQAAAAAAAAECEQMhMUEEElETIlJhcYGRFCMyoZIkM0JjscH/xAAWAQEBAQAAAAAAAAAAAAAAAAAAAQL/xAAYEQEBAQEBAAAAAAAAAAAAAAAAEQECIf/aAAwDAQACEQMRAD8A78TiMLDlyzkr6DWJhyVxp+h5Lk5Scnm3mCbTtOvQD1+eHT9CvC8C+DzocTiR1akvMtHiov8AJOP7A67w/Cvgd4fhXwQjOM/xkmaTArcOn6C4eFfBOxgb+34V8C+34F8CQtwNVheCP8QrC8Ef4mRAWTTWQElKgA8ZYq3RpTi9zPJ0kn7icGtgK2MhytaWjSlJb36gVKQxsSOkrXnmc6xHvH4NLEXWvUDsjxXij8F4Y2HPJSV9HkecmMD1KFuedDEnD8ZNFYcZJPvRT/QHYBKPFYUtW4vzN8yf4tNAaAzYAeFF2bTa0ZIotAKKb6jvyRiKbzSYwNZBl1GppYco8qd77om2BvlW36H3lo/kVJYab1enmDySabzAfPJaoO0W9ozb6pib6r4YVTnT3GpNZxbRFuLeteplxdXeXkwjsjxOJHdP1A46lswAXZu818G4wdLJk3tRaOWCnvbAcYSjOqbp7FnF1kznlKSxJVJpgsaaT7z+QLKOck0mYnFeGivatYEZSSlY5KMlfKgNQhGWElzqL8yn0+FONOcLvbIvgq8FOlVBcZJpxjpd1uQcsuFVJRkm1+yGJgSUVltmdOJyJS7qvajljCbk82ks3mVa58SLWI0bUaws9eY7YTw4ZxS9TmXfi23/AJNlRhKVeQFHfKkpK/UBEcr0RaDbwWl7kbyotg5wkRTxUlNtb2Y5orUpPOXt/wCIhLNEHVhyw4pOa5ssv2O8o5VZG+7ArBOUYtt5Okipr0OHf9OvcjdNqyvDv7GvUnNNzbSddSNYhJ3vfmEY80mk1pRqEeV5pamoS5uIlSqqKtmRjEi44Mlskc2Gl2au9djr4hPsJ7Wc+Clp0Rpgqi+vwBSMe0m1HYCo49iuBSUr6G3DBg1/clavVI3HkWmG/dmGk1C5K+g+xXUrf+uP/TfM1pGPwBJYVpVTrI1FOCSZVYk+plty1YRbCxIxw3E3JVH82/YjCfKkktB87eWQjVYnNXlbJYc+TFm5OubRsu4mXhJiIxjt9lm7TexOFKBqeHyZq3WxNuMtVTNc54zur8Mqi2BnDxFGNPICg5MkuioagVSVsNDLTHINRNiCE45DUUtwf4jIoyQW+gWgsB5sK6sVsKbKB10v1McsG+/H3RRRGkkETnh4UdQLWtwCpLVgC/JmlRAkJXbo3ktjMZa+oA1Sti3dDm+6zUM17AY5WtTSSG80CzAEGgOlnYW9kAV0FaD1AAtgFgBO+8bjqXxeEbnzQaz2Ylws92gJSMwTbZ0/Ty8h9hLyA53C1VjiqVdC3YT2cRPhpt6p+rAjzdMwV3nl6Fvpp9UD4ab3iBGkC6Fvpp9UD4afWNgS1EW+mn1XyH00+qAjTYHXhYKhnKmwAqAAAAAAAAAAAAAAAAAAAAAAB//Z' alt='소망약국 실제 외관 사진'></section><main><h2 id='products'>온라인 스토어</h2><p class='muted'>승인된 온라인 판매 가능 상품만 노출됩니다.</p><div class='grid'>"""
    for p in items:
        from markupsafe import escape
        body+=f"<div class='card'><span class='tag'>{escape(p['category'])}</span><h3>{escape(p['name'])}</h3><p>{escape(p['description'])}</p><strong>{p['price']:,}원</strong><p class='muted'>재고 {p['stock']}개</p><p class='tag'>결제 연결 준비 중</p></div>"
    if not items: body+="<div class='card'>판매 자격과 상품별 적법성 검토를 마친 상품을 준비하고 있습니다.</div>"
    body+="""</div><h2 style='margin-top:36px'>입점 예정 상품군</h2><div class='somang-categories'><div class='somang-category'><span class='emoji'>🧴</span><h3>더마 화장품</h3><p>보습·클렌징</p></div><div class='somang-category'><span class='emoji'>🌿</span><h3>두피·모발</h3><p>샴푸·토닉</p></div><div class='somang-category'><span class='emoji'>🪮</span><h3>생활용품</h3><p>건강관리 액세서리</p></div><div class='somang-category'><span class='emoji'>✨</span><h3>건강기능식품</h3><p>자격 확인 후 입점</p></div></div><div class='notice' id='info'><h2>소망약국 오시는 길</h2>대표약사 최연화<br>서울특별시 종로구 종로 335, 1층 (원풍빌딩)<br><div class='somang-actions'><a href='tel:027420075'>☎ 전화 걸기</a><a class='secondary' href='https://map.naver.com/p/search/%EC%86%8C%EB%A7%9D%EC%95%BD%EA%B5%AD%20%EC%A2%85%EB%A1%9C%20335' target='_blank' rel='noopener noreferrer'>지도·길찾기 ↗</a></div></div><p class='muted'>※ 일반의약품·전문의약품 온라인 판매 불가. 현재 결제·주문 접수 비활성화. 영업시간 확인 후 게시.</p></main>"""
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
    body="<main><div class='notice'><strong>운영 메뉴</strong><p><a href='/admin/ops'>운영 대시보드</a> · <a href='/admin/ops/suppliers'>공급사·발주</a> · <a href='/admin/ops/stock'>재고</a> · <a href='/admin/ops/lots'>로트·유통기한</a> · <a href='/admin/ops/ledger'>장부</a> · <a href='/admin/reports/summary'>보고서</a></p></div><h2>상품·재고 관리</h2><p class='muted'>신규 상품은 비공개·미승인으로 저장됩니다. 별도의 적법성 검토 전 공개할 수 없습니다.</p><form method='post' action='/admin/products'><input type='hidden' name='csrf' value='"+csrf()+"'><label>상품명 <input name='name' required maxlength='100'></label><label>상품 분류 <select name='category'>"+''.join("<option>"+x+"</option>" for x in CATS)+"</select></label><label>가격(원) <input name='price' type='number' min='0' required></label><label>재고 <input name='stock' type='number' min='0' required></label><label>설명 <textarea name='description' maxlength='1000'></textarea></label><button>비공개 상품 등록</button></form><h2>등록 상품</h2><div class='grid'>"
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
