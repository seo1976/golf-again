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
    return "<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+esc(title)+" | 소망약국</title><style>body{font-family:system-ui,sans-serif;margin:0;background:#f5faf6;color:#214435}header{background:white;padding:18px 5%;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}a{color:#287054}main{max-width:800px;margin:30px auto;padding:16px}.card{background:white;padding:23px;margin:16px 0;border:1px solid #dbe8df;border-radius:14px}label{display:block;margin:14px 0}input{padding:10px;border:1px solid #cadad0;border-radius:7px;max-width:90%}button,.btn{background:#267257;color:white;border:0;padding:11px 15px;border-radius:8px;cursor:pointer;display:inline-block;text-decoration:none}small{color:#68776e}.warning{background:#fff1d9;padding:15px;border-radius:10px}form{margin:10px 0}.demo-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.product-card{padding:0;overflow:hidden;margin:0}.product-art{height:110px;background:#e9f3eb;display:grid;place-items:center;font-size:48px}.product-info{padding:15px}.product-info h2{font-size:18px}.product-info p{font-size:13px}.product-info input{width:70px}.product-info button{width:100%}@media(max-width:520px){main{margin:8px auto;padding:12px}.demo-grid{gap:8px}.product-art{height:85px;font-size:39px}.product-info{padding:10px}.product-info h2{font-size:15px}.product-info p{font-size:12px}} .cart-line{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid #e5eee7}.cart-line p{margin:5px 0;font-size:13px}.cart-controls{display:flex;align-items:end;gap:8px}.cart-controls form{display:flex;align-items:end;gap:6px}.cart-controls label{font-size:12px;margin:0}.cart-controls input{width:62px}.cart-controls button{padding:9px}.cart-controls .subtle{background:#f0f3f0;color:#355e48}@media(max-width:550px){.cart-line{align-items:stretch;flex-direction:column}.cart-controls{justify-content:space-between}} .shop-search{display:flex;flex-wrap:wrap;gap:10px;align-items:end;background:white;padding:14px;border-radius:12px;border:1px solid #dbe8df;margin:14px 0}.shop-search label{margin:0;flex:1 1 140px;font-size:13px}.shop-search input,.shop-search select{display:block;width:100%;max-width:none;margin-top:6px;min-height:40px}.shop-search button{min-height:40px}.shop-search a{padding:10px} .review-table{border-collapse:collapse;width:100%;margin:12px 0}.review-table td,.review-table th{border-bottom:1px solid #e1eae4;padding:12px 6px;text-align:left;font-size:14px}.review-table td:last-child,.review-table th:last-child{text-align:right;white-space:nowrap}.review-totals{padding:10px 0}.review-totals p{display:flex;justify-content:space-between;gap:12px}.review-grand{border-top:1px solid #dce8de;padding-top:13px}.review-actions{display:flex;gap:12px;flex-wrap:wrap}.review-actions button:disabled{background:#a5b5ac;cursor:not-allowed;opacity:.85} .account-shortcuts{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.account-shortcuts a{flex:1 1 145px;text-align:center}.account-shortcuts a:nth-child(2){background:#1f5945}.account-shortcuts a:nth-child(3){background:#527b62} /* Consistent mobile storefront and checkout preview */
*{box-sizing:border-box}body{line-height:1.5}a{text-decoration:none}a:hover{text-decoration:underline}
header{align-items:center;border-bottom:1px solid #dce8df}header strong a{font-size:23px;font-weight:800}header nav{display:flex;gap:8px;flex-wrap:wrap;align-items:center}header nav a{padding:8px 10px;border-radius:9px;font-size:14px}header nav a:first-child{background:#e1f0e6;color:#15563d;font-weight:800}
main{margin:18px auto;padding:18px}main>h1{font-size:clamp(28px,5vw,38px);line-height:1.25;letter-spacing:-.8px;margin:12px 0 24px}
.card{box-shadow:0 2px 12px rgba(26,69,47,.035)}.warning{font-size:14px;line-height:1.65}
.demo-grid{align-items:stretch;gap:14px}.product-card{display:flex;flex-direction:column;min-width:0}.product-art{height:130px;flex:none}.product-info{display:flex;flex-direction:column;flex:1;gap:8px;padding:16px}.product-info small{line-height:1.4}.product-info h2{font-size:18px;line-height:1.35;margin:0;min-height:49px;overflow-wrap:anywhere}.product-info p{margin:0;color:#65786b;line-height:1.45;min-height:19px}.product-info strong{font-size:20px}.product-info form{margin-top:auto;display:flex;flex-direction:column;gap:10px}.product-info label{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0;font-size:13px}.product-info input{width:70px;max-width:70px;min-height:40px;font-size:16px}.product-info button{min-height:44px;font-weight:700}
.shop-search{gap:12px}.shop-search label{min-width:0}.shop-search input,.shop-search select{font-size:16px;background:#fff}.shop-search button{min-height:44px}
.empty-cart{max-width:550px;margin:18px auto;padding:26px 20px;text-align:center}.empty-cart strong{display:block;font-size:20px}.empty-cart .btn{margin-top:10px}
@media(max-width:550px){header{padding:15px 16px;gap:9px}header nav{gap:3px 5px}header nav a{font-size:12px;padding:7px 6px}main{padding:14px;margin:8px auto}main>h1{font-size:30px;margin:12px 0 20px}.warning{padding:13px}.demo-grid{gap:10px}.product-art{height:96px;font-size:38px}.product-info{padding:12px;gap:7px}.product-info h2{font-size:15px;min-height:41px}.product-info p{font-size:12px}.product-info strong{font-size:17px}.product-info input{width:58px;max-width:58px}.product-info button{font-size:12px;padding:10px 5px}.shop-search{padding:12px;gap:10px}.shop-search label{flex:1 1 100%;font-size:13px}.shop-search input,.shop-search select{min-height:44px}.empty-cart{padding:20px 14px}}
</style><header><strong><a href='/'>✚ 소망약국</a></strong><nav><a href='/online-products'>온라인 상품</a>　<a href='/cart'>장바구니 ("+str(cart_count())+")</a>　<a href='/policy/returns'>반품·환불 안내</a>　<a href='/account'>"+("마이페이지" if session.get("member_id") or session.get("demo_member") else "로그인 · 회원가입")+"</a></nav></header><main><h1>"+esc(title)+"</h1>"+body+"</main>"
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
    body="<div class='warning'>체험용 장바구니 · 실제 결제 불가</div><p><a href='/shop'>← 상품 더 보기</a></p>"+("<div class='card'>" if rows else "<div class='card empty-cart'>")
    for p in rows:
        body+="<div class='cart-line'><div><strong>"+esc(p["name"])+"</strong><p>단가 "+f'{p["price"]:,}'+"원 · 소계 "+f'{p["price"]*p["quantity"]:,}'+"원</p></div><div class='cart-controls'><form action='/cart/update' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><label>수량 <input type='number' name='quantity' min='0' max='20' value='"+str(p["quantity"])+"'></label><button>변경</button></form><form action='/cart/remove' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><button class='subtle'>삭제</button></form></div></div>"
    body+="<h2>예상 상품 합계 "+f'{total:,}'+"원</h2><p><small>배송비 미포함 · 실제 판매가가 아닙니다.</small></p>"+("<a class='btn' href='/checkout'>결제 전 주문 확인 →</a>" if rows else "<strong>장바구니가 비어 있습니다.</strong><p>관심 있는 상품을 둘러보고 담아보세요.</p><a class='btn' href='/shop'>상품 둘러보기 →</a>")+"</div>"
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
@shop.get("/account")
def account():
    if session.get("demo_member"):
        return page("내 계정 · 체험 회원","<div class='warning'>체험용 회원 상태입니다. 실제 회원가입·개인정보 저장은 하지 않습니다.</div><div class='card'><h2>체험 회원으로 로그인 중</h2><p>환영합니다! 소망약국 상품 체험을 계속 이용할 수 있어요.</p><div class='account-shortcuts'><a class='btn' href='/shop'>상품 둘러보기</a><a class='btn' href='/cart'>내 장바구니 ("+str(cart_count())+")</a><a class='btn' href='/checkout'>결제 전 확인</a></div><p><small>체험 계정은 실제 회원 계정이 아니며 주문 내역을 저장하지 않습니다.</small></p><form action='/demo/logout' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><button>체험 로그아웃</button></form></div>")
    if session.get("member_id"):
        with db() as c:
            state=c.execute("SELECT suspended FROM shop_member_controls WHERE member_id=?",(session["member_id"],)).fetchone()
        if state and state["suspended"]:
            session.pop("member_id",None)
            return redirect("/account")
        return page("내 계정","<div class='card'>로그인 상태입니다.<form method='post' action='/logout'><input type='hidden' name='csrf' value='"+csrf()+"'><button>로그아웃</button></form></div>")
    body="<div class='warning'>현재는 미리보기 사이트입니다. 실제 고객 회원가입·로그인은 영구 데이터베이스와 개인정보 보호 준비 전까지 비활성화됩니다.</div><div class='card'><h2>회원 로그인 체험</h2><p>개인정보 입력 없이 회원 화면과 장바구니 연결을 체험해 보세요.</p><form method='post' action='/demo/login'><input type='hidden' name='csrf' value='"+csrf()+"'><button>체험 회원으로 로그인</button></form></div>"
    if os.environ.get("SOMANG_ENABLE_DEMO_REGISTRATION")=="1":
        body+="<div class='card'><h2>테스트 회원가입</h2>"+auth_form("/register","테스트 가입")+"</div><div class='card'><h2>테스트 회원 로그인</h2>"+auth_form("/login","테스트 로그인")+"</div>"
    else:
        body+="<div class='card'><h2>정식 회원 로그인 · 회원가입</h2><p>서비스 오픈 준비 중입니다. 실제 이메일이나 비밀번호를 입력하지 마세요.</p><button type='button' disabled>회원 로그인 (준비 중)</button> <button type='button' disabled>회원가입 (준비 중)</button></div>"
    return page("회원 로그인 · 회원가입",body)
@shop.post("/demo/login")
def demo_login():
    check()
    session["demo_member"]=True
    return redirect("/account")
@shop.post("/demo/logout")
def demo_logout():
    check()
    session.pop("demo_member",None)
    return redirect("/account")
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
    if r:
        with db() as c:
            blocked=c.execute("SELECT suspended FROM shop_member_controls WHERE member_id=?",(r["id"],)).fetchone()
        if blocked and blocked["suspended"]:
            return page("로그인 제한","<div class='card'>관리자에 의해 테스트 계정 이용이 중지되었습니다. <a href='/account'>돌아가기</a></div>"),403
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
    body="<div class='warning'>결제 전 마지막 확인 · 체험용 화면입니다. 주문 접수·실제 결제·배송은 진행되지 않습니다. 개인정보를 입력하지 마세요.</div><div class='card'><h2>주문 상품 확인</h2><table class='review-table'><thead><tr><th>상품</th><th>수량</th><th>금액</th></tr></thead><tbody>"
    for p in rows:
        body+="<tr><td>"+esc(p["name"])+"</td><td>"+str(p["quantity"])+"개</td><td>"+f'{p["price"]*p["quantity"]:,}'+"원</td></tr>"
    body+="</tbody></table><div class='review-totals'><p>상품 합계 <strong>"+f'{total:,}'+"원</strong></p><p>배송비 <strong>미정</strong></p><p class='review-grand'>최종 결제금액 <strong>배송 정책 확정 후 표시</strong></p></div><p><small>예시 상품과 예시 가격이며, 실제 판매 상품이나 결제금액이 아닙니다.</small></p><div class='review-actions'><a class='btn' href='/cart'>← 수량·상품 수정</a><button type='button' disabled title='실제 결제는 준비 중입니다'>결제하기 (준비 중)</button></div></div>"
    return page("결제 전 주문 확인",body)
@shop.get("/payment/status")
def payment_status():
    return jsonify(provider="not_configured",payments_enabled=False,real_orders_enabled=False,message="PG 계약·키·웹훅 검증 및 영구 저장소 설정 전 결제 차단")
