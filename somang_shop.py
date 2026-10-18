"""Somang storefront: registration, member login, session cart, guest/member checkout preview.
No personal customer data or real payment is accepted until persistent DB and PG are configured.
"""
import os, sqlite3, secrets, hmac, re, html
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, session, redirect, abort, jsonify
shop=Blueprint("somang_shop",__name__)
DEMO_PRODUCTS=[{"id":900001,"name":"수분 보습 크림 50ml","category":"더마 화장품","description":"보습 크림 예시","price":18900,"stock":99,"emoji":"🧴"},{"id":900002,"name":"저자극 클렌징 젤 200ml","category":"더마 화장품","description":"세안 제품 예시","price":12900,"stock":99,"emoji":"🫧"},{"id":900003,"name":"두피 케어 샴푸 300ml","category":"두피·모발","description":"샴푸 예시","price":16900,"stock":99,"emoji":"🌿"},{"id":900004,"name":"헤어 트리트먼트 200ml","category":"두피·모발","description":"트리트먼트 예시","price":14900,"stock":99,"emoji":"✨"},{"id":900005,"name":"휴대용 손 세정제 100ml","category":"생활용품","description":"손 세정 제품 예시","price":4900,"stock":99,"emoji":"🧼"},{"id":900006,"name":"데일리 핸드크림 50ml","category":"화장품","description":"핸드크림 예시","price":7900,"stock":99,"emoji":"🤲"}]
DEMO_BY_ID={p["id"]:p for p in DEMO_PRODUCTS}
DB=os.environ.get("SOMANG_DB_PATH","/tmp/somang_preview.sqlite3")
def db():
    c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;return c
def init():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS shop_members(id INTEGER PRIMARY KEY,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS shop_order_previews(id INTEGER PRIMARY KEY,mode TEXT NOT NULL,total INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS shop_order_preview_items(order_id INTEGER,product_id INTEGER,quantity INTEGER,unit_price INTEGER)")
init()
def esc(s):return html.escape(str(s),quote=True)
def csrf():
    if "csrf" not in session:session["csrf"]=secrets.token_urlsafe(32)
    return session["csrf"]
def check():
    if not session.get("csrf") or not hmac.compare_digest(session["csrf"],request.form.get("csrf","")):abort(400)
def cart_count():
    count=0
    for v in session.get("cart",{}).values():
        try:count+=max(0,min(20,int(v)))
        except (TypeError,ValueError):continue
    return min(count,1000)
def page(title,body):
    return "<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+esc(title)+" | 소망약국</title><style>body{font-family:system-ui,sans-serif;margin:0;background:#f5faf6;color:#214435}header{background:white;padding:18px 5%;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}a{color:#287054}main{max-width:800px;margin:30px auto;padding:16px}.card{background:white;padding:23px;margin:16px 0;border:1px solid #dbe8df;border-radius:14px}label{display:block;margin:14px 0}input{padding:10px;border:1px solid #cadad0;border-radius:7px;max-width:90%}button,.btn{background:#267257;color:white;border:0;padding:11px 15px;border-radius:8px;cursor:pointer;display:inline-block;text-decoration:none}small{color:#68776e}.warning{background:#fff1d9;padding:15px;border-radius:10px}form{margin:10px 0}.demo-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.product-card{padding:0;overflow:hidden;margin:0}.product-art{height:110px;background:#e9f3eb;display:grid;place-items:center;font-size:48px}.product-info{padding:15px}.product-info h2{font-size:18px}.product-info p{font-size:13px}.product-info input{width:70px}.product-info button{width:100%}@media(max-width:520px){main{margin:8px auto;padding:12px}.demo-grid{gap:8px}.product-art{height:85px;font-size:39px}.product-info{padding:10px}.product-info h2{font-size:15px}.product-info p{font-size:12px}} .cart-line{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid #e5eee7}.cart-line p{margin:5px 0;font-size:13px}.cart-controls{display:flex;align-items:end;gap:8px}.cart-controls form{display:flex;align-items:end;gap:6px}.cart-controls label{font-size:12px;margin:0}.cart-controls input{width:62px}.cart-controls button{padding:9px}.cart-controls .subtle{background:#f0f3f0;color:#355e48}@media(max-width:550px){.cart-line{align-items:stretch;flex-direction:column}.cart-controls{justify-content:space-between}} .shop-search{display:flex;flex-wrap:wrap;gap:10px;align-items:end;background:white;padding:14px;border-radius:12px;border:1px solid #dbe8df;margin:14px 0}.shop-search label{margin:0;flex:1 1 140px;font-size:13px}.shop-search input,.shop-search select{display:block;width:100%;max-width:none;margin-top:6px;min-height:40px}.shop-search button{min-height:40px}.shop-search a{padding:10px} </style><header><strong><a href='/'>✚ 소망약국</a></strong><nav><a href='/shop'>상품</a>　<a href='/cart'>장바구니 ("+str(cart_count())+")</a>　<a href='/account'>회원</a></nav></header><main><h1>"+esc(title)+"</h1>"+body+"</main>"
def product_rows():
    with db() as c:return [dict(r) for r in c.execute("SELECT id,name,category,description,price,stock FROM products WHERE approved=1 AND visible=1 AND stock>0 ORDER BY id DESC LIMIT 100")]
@shop.get("/shop")
def catalog():
    keyword=request.args.get("q","").strip()[:60]
    category=request.args.get("category","").strip()[:60]
    all_products=DEMO_PRODUCTS+product_rows()
    categories=sorted(set(p["category"] for p in all_products))
    if category and category not in categories:category=""
    selected=[p for p in all_products if (not category or p["category"]==category) and (not keyword or keyword.casefold() in (p["name"]+" "+p["description"]+" "+p["category"]).casefold())]
    body="<div class='warning'>체험용 가상 상품입니다. 가격은 예시이며 실제 주문·결제는 불가능합니다.</div><form method='get' action='/shop' class='shop-search'><label>상품 검색 <input type='search' name='q' value='"+esc(keyword)+"' placeholder='예: 보습, 샴푸'></label><label>카테고리 <select name='category'><option value=''>전체 상품</option>"
    for c in categories:
        body+="<option value='"+esc(c)+"'"+(" selected" if c==category else "")+">"+esc(c)+"</option>"
    body+="</select></label><button>검색</button><a href='/shop'>초기화</a></form><p><small>검색 결과 "+str(len(selected))+"개 · <a href='/cart'>장바구니 보기 →</a></small></p><div class='demo-grid'>"
    for p in selected:
        body+="<article class='card product-card'><div class='product-art'>"+p.get("emoji","🛍️")+"</div><div class='product-info'><small>"+esc(p["category"])+" · "+("체험 상품" if p["id"] in DEMO_BY_ID else "등록 상품")+"</small><h2>"+esc(p["name"])+"</h2><p>"+esc(p["description"])+"</p><strong>"+f'{p["price"]:,}'+"원</strong><form action='/cart/add' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><label>수량 <input type='number' name='quantity' min='1' max='20' value='1'></label><button>장바구니 담기</button></form></div></article>"
    if not selected:body+="<p>조건에 맞는 상품이 없습니다. <a href='/shop'>전체 상품 보기</a></p>"
    body+="</div><p><a class='btn' href='/cart'>장바구니 확인 →</a></p>"
    return page("상품 둘러보기",body)
@shop.post("/cart/add")
def add():
    check()
    try:pid=int(request.form.get("product_id",""));qty=int(request.form.get("quantity","1"))
    except ValueError:abort(400)
    if qty<1 or qty>20:abort(400)
    if pid in DEMO_BY_ID:p=DEMO_BY_ID[pid]
    else:
        with db() as c:p=c.execute("SELECT stock FROM products WHERE id=? AND approved=1 AND visible=1",(pid,)).fetchone()
    if not p:abort(404)
    cart=dict(session.get("cart",{}))
    cart[str(pid)]=min(20,p["stock"],int(cart.get(str(pid),0))+qty)
    session["cart"]=cart
    return redirect("/cart")
def contents():
    cart=session.get("cart",{})
    rows=[];total=0
    with db() as c:
        for k,v in list(cart.items())[:50]:
            try:pid=int(k);qty=int(v)
            except (ValueError,TypeError):continue
            if pid in DEMO_BY_ID:p=DEMO_BY_ID[pid]
            else:p=c.execute("SELECT id,name,price,stock FROM products WHERE id=? AND approved=1 AND visible=1 AND stock>0",(pid,)).fetchone()
            if p and qty>0:
                qty=min(qty,p["stock"],20);row=dict(p);row["quantity"]=qty;rows.append(row);total+=row["price"]*qty
    return rows,total
@shop.get("/cart")
def cart():
    rows,total=contents()
    body="<div class='warning'>체험용 장바구니 · 실제 결제 불가</div><p><a href='/shop'>← 상품 더 보기</a></p><div class='card'>"
    for p in rows:
        body+="<div class='cart-line'><div><strong>"+esc(p["name"])+"</strong><p>단가 "+f'{p["price"]:,}'+"원 · 소계 "+f'{p["price"]*p["quantity"]:,}'+"원</p></div><div class='cart-controls'><form action='/cart/update' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><label>수량 <input type='number' name='quantity' min='0' max='20' value='"+str(p["quantity"])+"'></label><button>변경</button></form><form action='/cart/remove' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><button class='subtle'>삭제</button></form></div></div>"
    body+="<h2>예상 상품 합계 "+f'{total:,}'+"원</h2><p><small>배송비 미포함 · 실제 판매가가 아닙니다.</small></p>"+("<a class='btn' href='/checkout'>결제 전 주문 확인 →</a>" if rows else "<p>장바구니가 비어 있습니다.</p><a class='btn' href='/shop'>상품 둘러보기</a>")+"</div>"
    return page("장바구니",body)
@shop.post("/cart/update")
def update_cart():
    check()
    try:pid=int(request.form.get("product_id",""));qty=int(request.form.get("quantity",""))
    except (ValueError,TypeError):abort(400)
    if qty<0 or qty>20:abort(400)
    cart=dict(session.get("cart",{}))
    if str(pid) not in cart:abort(404)
    if qty==0:cart.pop(str(pid),None)
    else:
        if pid in DEMO_BY_ID:stock=DEMO_BY_ID[pid]["stock"]
        else:
            with db() as c:p=c.execute("SELECT stock FROM products WHERE id=? AND approved=1 AND visible=1",(pid,)).fetchone()
            if p is None:abort(404)
            stock=p["stock"]
        cart[str(pid)]=min(qty,stock)
    session["cart"]=cart
    return redirect("/cart")
@shop.post("/cart/remove")
def remove():
    check();cart=dict(session.get("cart",{}));cart.pop(request.form.get("product_id",""),None);session["cart"]=cart
    return redirect("/cart")
@shop.route("/account",methods=["GET","POST"])
def account():
    if session.get("member_id"):
        return page("내 계정","<div class='card'>로그인 상태입니다.<form method='post' action='/logout'><input type='hidden' name='csrf' value='"+csrf()+"'><button>로그아웃</button></form></div>")
    if os.environ.get("SOMANG_ENABLE_DEMO_REGISTRATION")!="1":return page("회원가입 · 로그인","<div class=\'warning\'>회원가입과 로그인은 영구 데이터베이스 및 개인정보 보호 준비 전까지 비활성화되어 있습니다. 비회원 장바구니는 미리 볼 수 있습니다.</div>")
    return page("회원가입 · 로그인","<div class='warning'>현재는 개발 테스트 단계입니다. 실제 이메일이나 평소 사용하는 비밀번호를 입력하지 마세요. 무료 서버 재배포 시 회원 데이터가 삭제될 수 있습니다.</div><div class='card'><h2>회원가입</h2>"+auth_form("/register","가입하기")+"</div><div class='card'><h2>로그인</h2>"+auth_form("/login","로그인")+"</div>")
def auth_form(action,label):
    return "<form action='"+action+"' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><label>테스트 이메일 <input type='email' name='email' maxlength='150' required></label><label>비밀번호 (12자 이상) <input type='password' name='password' minlength='12' required></label><button>"+label+"</button></form>"
def credentials():
    email=request.form.get("email","").strip().lower()[:150]
    pw=request.form.get("password","")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or len(pw)<12 or len(pw)>200:abort(400)
    return email,pw
@shop.post("/register")
def register():
    if os.environ.get("SOMANG_ENABLE_DEMO_REGISTRATION")!="1":abort(503,"회원가입은 영구 DB 준비 후 활성화합니다.")
    check();email,pw=credentials()
    try:
        with db() as c:
            cur=c.execute("INSERT INTO shop_members(email,password_hash) VALUES(?,?)",(email,generate_password_hash(pw)))
            member_id=cur.lastrowid
    except sqlite3.IntegrityError:
        return page("가입 불가","<div class='card'>이미 등록된 테스트 이메일입니다. <a href='/account'>돌아가기</a></div>"),409
    cart=session.get("cart",{})
    session.clear();session["member_id"]=member_id;session["cart"]=cart
    return redirect("/account")
@shop.post("/login")
def login():
    if os.environ.get("SOMANG_ENABLE_DEMO_REGISTRATION")!="1":abort(503,"회원 로그인은 영구 DB 준비 후 활성화합니다.")
    check();email,pw=credentials()
    with db() as c:r=c.execute("SELECT id,password_hash FROM shop_members WHERE email=?",(email,)).fetchone()
    if not r or not check_password_hash(r["password_hash"],pw):
        return page("로그인 실패","<div class='card'>계정 정보가 올바르지 않습니다. <a href='/account'>다시 시도</a></div>"),403
    cart=session.get("cart",{})
    session.clear();session["member_id"]=r["id"];session["cart"]=cart
    return redirect("/account")
@shop.post("/logout")
def logout():
    check();session.clear();return redirect("/account")
@shop.get("/checkout")
def checkout():
    rows,total=contents()
    if not rows:return redirect("/cart")
    mode="회원" if session.get("member_id") else "비회원"
    body="<div class='warning'>현재는 주문 시뮬레이션 단계입니다. 결제·주문 접수·배송을 진행하지 않습니다. 실제 주소·연락처를 입력하지 마세요.</div><div class='card'><h2>"+mode+" 주문 내용 미리보기</h2>"
    for p in rows:body+="<p>"+esc(p["name"])+" × "+str(p["quantity"])+" = "+f'{p["price"]*p["quantity"]:,}'+"원</p>"
    body+="<h2>상품 합계 "+f'{total:,}'+"원</h2><p>배송비 및 최종 결제금액은 추후 배송 정책 확정 후 산정됩니다.</p><p>결제 전 상품·수량·금액 확인 완료 · 실제 결제는 비활성화</p><a href='/cart'>장바구니로 돌아가기</a></div>"
    return page("결제 전 주문 확인",body)
@shop.get("/payment/status")
def payment_status():
    return jsonify(provider="not_configured",payments_enabled=False,real_orders_enabled=False,message="PG 계약·키·웹훅 검증 및 영구 저장소 설정 전 결제 차단")
