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
    return "<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+esc(title)+" | 소망약국</title><style>body{font-family:system-ui,sans-serif;margin:0;background:#f5faf6;color:#214435}header{background:white;padding:18px 5%;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}a{color:#287054}main{max-width:800px;margin:30px auto;padding:16px}.card{background:white;padding:23px;margin:16px 0;border:1px solid #dbe8df;border-radius:14px}label{display:block;margin:14px 0}input{padding:10px;border:1px solid #cadad0;border-radius:7px;max-width:90%}button,.btn{background:#267257;color:white;border:0;padding:11px 15px;border-radius:8px;cursor:pointer;display:inline-block;text-decoration:none}small{color:#68776e}.warning{background:#fff1d9;padding:15px;border-radius:10px}form{margin:10px 0}.demo-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.product-card{padding:0;overflow:hidden;margin:0}.product-art{height:110px;background:#e9f3eb;display:grid;place-items:center;font-size:48px}.product-info{padding:15px}.product-info h2{font-size:18px}.product-info p{font-size:13px}.product-info input{width:70px}.product-info button{width:100%}@media(max-width:520px){main{margin:8px auto;padding:12px}.demo-grid{gap:8px}.product-art{height:85px;font-size:39px}.product-info{padding:10px}.product-info h2{font-size:15px}.product-info p{font-size:12px}} .cart-line{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid #e5eee7}.cart-line p{margin:5px 0;font-size:13px}.cart-controls{display:flex;align-items:end;gap:8px}.cart-controls form{display:flex;align-items:end;gap:6px}.cart-controls label{font-size:12px;margin:0}.cart-controls input{width:62px}.cart-controls button{padding:9px}.cart-controls .subtle{background:#f0f3f0;color:#355e48}.cart-controls{flex-wrap:wrap}.cart-controls form{margin:0}.cart-controls form:first-child{flex:0 1 auto}.cart-controls form:last-child{margin-left:4px}.cart-controls input{box-sizing:border-box}.cart-line>div:first-child{min-width:0}.cart-line strong a{color:inherit;text-decoration:none}.cart-line strong a:hover{text-decoration:underline}@media(max-width:550px){.cart-controls{justify-content:flex-start;align-items:center;gap:10px}.cart-controls form{align-items:center}.cart-controls label{display:flex;align-items:center;gap:6px}.cart-controls input{width:58px}.cart-controls form:last-child{margin-left:0}.cart-line{gap:14px}}@media(max-width:550px){.cart-line{align-items:stretch;flex-direction:column}.cart-controls{justify-content:space-between}} .shop-search{display:flex;flex-wrap:wrap;gap:10px;align-items:end;background:white;padding:14px;border-radius:12px;border:1px solid #dbe8df;margin:14px 0}.shop-search label{margin:0;flex:1 1 140px;font-size:13px}.shop-search input,.shop-search select{display:block;width:100%;max-width:none;margin-top:6px;min-height:40px}.shop-search button{min-height:40px}.shop-search a{padding:10px} .review-table{border-collapse:collapse;width:100%;margin:12px 0}.review-table td,.review-table th{border-bottom:1px solid #e1eae4;padding:12px 6px;text-align:left;font-size:14px}.review-table td:last-child,.review-table th:last-child{text-align:right;white-space:nowrap}.review-totals{padding:10px 0}.review-totals p{display:flex;justify-content:space-between;gap:12px}.review-grand{border-top:1px solid #dce8de;padding-top:13px}.review-actions{display:flex;gap:12px;flex-wrap:wrap}.review-actions button:disabled{background:#a5b5ac;cursor:not-allowed;opacity:.85} .account-shortcuts{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.account-shortcuts a{flex:1 1 145px;text-align:center}.account-shortcuts a:nth-child(2){background:#1f5945}.account-shortcuts a:nth-child(3){background:#527b62} .member-coming-soon .member-benefits{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.member-coming-soon .member-benefits span{background:#eaf4ed;border:1px solid #d6e9dc;padding:8px 10px;border-radius:9px;font-size:13px}.member-coming-soon button[disabled]{background:#a3b7ab;cursor:not-allowed}.member-coming-soon small{line-height:1.6}.subtle-action{background:#f0f4f1;color:#315d47;border:1px solid #d4e2d8}.subtle-action:hover{background:#e5eee8}.demo-profile{border-top:1px solid #dbe8df;margin:18px 0;padding-top:16px}.demo-profile summary{cursor:pointer;font-weight:700}.demo-profile input{display:block;margin:8px 0 12px;max-width:100%}/* Consistent mobile storefront and checkout preview */ *{box-sizing:border-box}body{line-height:1.5}a{text-decoration:none}a:hover{text-decoration:underline} header{align-items:center;border-bottom:1px solid #dce8df}header strong a{font-size:23px;font-weight:800}header nav{display:flex;gap:8px;flex-wrap:wrap;align-items:center}header nav a{padding:8px 10px;border-radius:9px;font-size:14px}header nav a:first-child{background:#e1f0e6;color:#15563d;font-weight:800} main{margin:18px auto;padding:18px}main>h1{font-size:clamp(28px,5vw,38px);line-height:1.25;letter-spacing:-.8px;margin:12px 0 24px} .card{box-shadow:0 2px 12px rgba(26,69,47,.035)}.warning{font-size:14px;line-height:1.65} .demo-grid{align-items:stretch;gap:14px}.product-card{display:flex;flex-direction:column;min-width:0}.product-art{height:130px;flex:none}.product-info{display:flex;flex-direction:column;flex:1;gap:8px;padding:16px}.product-info small{line-height:1.4}.product-info h2{font-size:18px;line-height:1.35;margin:0;min-height:49px;overflow-wrap:anywhere}.product-info p{margin:0;color:#65786b;line-height:1.45;min-height:19px}.product-info strong{font-size:20px}.product-info form{margin-top:auto;display:flex;flex-direction:column;gap:10px}.product-info label{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0;font-size:13px}.product-info input{width:70px;max-width:70px;min-height:40px;font-size:16px}.product-info button{min-height:44px;font-weight:700} .shop-search{gap:12px}.shop-search label{min-width:0}.shop-search input,.shop-search select{font-size:16px;background:#fff}.shop-search button{min-height:44px} .empty-cart{max-width:550px;margin:18px auto;padding:26px 20px;text-align:center}.empty-cart strong{display:block;font-size:20px}.empty-cart .btn{margin-top:10px} @media(max-width:550px){header{padding:15px 16px;gap:9px}header nav{gap:3px 5px}header nav a{font-size:12px;padding:7px 6px}main{padding:14px;margin:8px auto}main>h1{font-size:30px;margin:12px 0 20px}.warning{padding:13px}.demo-grid{gap:10px}.product-art{height:96px;font-size:38px}.product-info{padding:12px;gap:7px}.product-info h2{font-size:15px;min-height:41px}.product-info p{font-size:12px}.product-info strong{font-size:17px}.product-info input{width:58px;max-width:58px}.product-info button{font-size:12px;padding:10px 5px}.shop-search{padding:12px;gap:10px}.shop-search label{flex:1 1 100%;font-size:13px}.shop-search input,.shop-search select{min-height:44px}.empty-cart{padding:20px 14px}} /* Product card image placeholders: consistent neutral visual language */ .product-art{position:relative;isolation:isolate;background:linear-gradient(145deg,#e6f1e9 0%,#f4f8f3 100%);border-bottom:1px solid #e1ebe4;border-radius:0;line-height:1}.product-art:after{content:attr(title);position:absolute;right:9px;bottom:8px;font-size:10px;letter-spacing:.3px;color:#648173;background:rgba(255,255,255,.8);border:1px solid #dce9df;padding:4px 7px;border-radius:20px}.product-card:focus-within{outline:2px solid #367b60;outline-offset:2px}.product-info button:hover{background:#195a43}.product-info button:focus-visible,.shop-search button:focus-visible{outline:3px solid #9dcead;outline-offset:2px} @media(max-width:550px){.product-art:after{font-size:9px;right:6px;bottom:5px;padding:3px 5px}.product-info h2{word-break:keep-all}.product-info label{white-space:nowrap}} /* Equal-height product cards and accessible actions */ .product-card .product-info>p:first-of-type{min-height:38px}.product-card .product-info>p:nth-of-type(2){min-height:20px}.product-card .product-info>p:nth-of-type(3){min-height:22px}.product-card .product-info>strong{margin-top:auto}.product-card .product-info form{margin-top:0}.product-info h2 a{color:inherit;text-decoration:none}.product-info h2 a:focus-visible,.product-info p a:focus-visible{outline:2px solid #267257;outline-offset:3px}.product-info p a{font-weight:700;text-decoration:underline;text-underline-offset:3px}@media(max-width:550px){.product-card .product-info>p:first-of-type{min-height:52px}.product-info h2{min-height:44px}.product-info p a{font-size:12px}} </style><header><strong><a href='/'>✚ 소망약국</a></strong><nav><a href='/online-products'>온라인 상품</a>　<a href='/cart'>장바구니 ("+str(cart_count())+")</a>　<a href='/policy/returns'>반품·환불 안내</a>　<a href='/account'>"+("마이페이지" if session.get("member_id") or session.get("demo_member") else "로그인 · 회원가입")+"</a></nav></header><main><h1>"+esc(title)+"</h1>"+body+"</main>"
def product_rows():
    with db() as c:return [dict(r) for r in c.execute("SELECT id,name,category,description,price,stock FROM products WHERE approved=1 AND visible=1 AND stock>0 ORDER BY id DESC LIMIT 100")]
def find_product(pid):
    if pid in DEMO_BY_ID:
        return dict(DEMO_BY_ID[pid])
    with db() as c:
        row=c.execute("SELECT id,name,category,description,price,stock FROM products WHERE id=? AND approved=1 AND visible=1",(pid,)).fetchone()
        return dict(row) if row else None

@shop.get("/shop/product/<int:pid>")
def product_detail(pid):
    p=find_product(pid)
    if not p:abort(404)
    available=p["stock"]>0
    body="<p><a href='/shop'>← 상품 목록으로</a></p><div class='card'><div class='product-art' style='height:180px'>"+esc(p.get("emoji","🛍️"))+"</div><h2>"+esc(p["name"])+"</h2><p>"+esc(p["category"])+"</p><p>"+esc(p["description"])+"</p><strong>"+f'{p["price"]:,}'+"원</strong><p>"+("재고 "+str(p["stock"])+"개" if available else "품절")+"</p>"
    if available:
        body+="<form action='/cart/add' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(pid)+"'><label>수량 <input type='number' name='quantity' min='1' max='"+str(min(20,p["stock"]))+"' value='1' required></label><button>장바구니 담기</button></form>"
    body+="<p><small>현재는 상품 체험용 미리보기이며 실제 주문·결제는 불가능합니다.</small></p></div>"
    return page(p["name"],body)

@shop.get("/shop")
def catalog():
    keyword=request.args.get("q","").strip()[:60]
    category=request.args.get("category","").strip()[:60]
    sort=request.args.get("sort","recommended")
    if sort not in ("recommended","price_asc","price_desc","name"):sort="recommended"
    all_products=DEMO_PRODUCTS+product_rows()
    categories=sorted(set(p["category"] for p in all_products))
    if category and category not in categories:category=""
    selected=[p for p in all_products if (not category or p["category"]==category) and (not keyword or keyword.casefold() in (p["name"]+" "+p["description"]+" "+p["category"]).casefold())]
    if sort=="price_asc":selected.sort(key=lambda p:(p["price"],p["name"]))
    elif sort=="price_desc":selected.sort(key=lambda p:(-p["price"],p["name"]))
    elif sort=="name":selected.sort(key=lambda p:p["name"])
    body="<div class='warning'>체험용 가상 상품입니다. 가격은 예시이며 실제 주문·결제는 불가능합니다.</div><form method='get' action='/shop' class='shop-search'><label>상품 검색 <input type='search' name='q' value='"+esc(keyword)+"' placeholder='예: 보습, 샴푸'></label><label>카테고리 <select name='category'><option value=''>전체 상품</option>"
    for c in categories:
        body+="<option value='"+esc(c)+"'"+(" selected" if c==category else "")+">"+esc(c)+"</option>"
    body+="</select></label><label>정렬 <select name='sort'>"
    for key,label in (("recommended","기본순"),("price_asc","낮은 가격순"),("price_desc","높은 가격순"),("name","상품명순")):
        body+="<option value='"+key+"'"+(" selected" if sort==key else "")+">"+label+"</option>"
    body+="</select></label><button>검색</button><a href='/shop'>초기화</a></form><p><small>검색 결과 "+str(len(selected))+"개 · <a href='/cart'>장바구니 보기 →</a></small></p><div class='demo-grid'>"
    for p in selected:
        body+="<article class='card product-card'><div class='product-art'>"+p.get("emoji","🛍️")+"</div><div class='product-info'><small>"+esc(p["category"])+" · "+("체험 상품" if p["id"] in DEMO_BY_ID else "등록 상품")+"</small><h2><a href='/shop/product/"+str(p["id"])+"'>"+esc(p["name"])+"</a></h2><p>"+esc(p["description"])+"</p><strong>"+f'{p["price"]:,}'+"원</strong><p><small>재고 "+str(p["stock"])+"개 · 체험 전시 상품</small></p><p><a href='/shop/product/"+str(p["id"])+"'>상세 보기 →</a></p><form action='/cart/add' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><label>수량 <input type='number' name='quantity' min='1' max='"+str(min(20,p["stock"]))+"' value='1' required></label><button>장바구니 담기</button></form></div></article>"
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
    try:existing=int(cart.get(str(pid),0))
    except (ValueError,TypeError):existing=0
    new_qty=min(20,max(0,p["stock"]),max(0,existing)+qty)
    if new_qty<=0:abort(409,"품절된 상품입니다.")
    cart[str(pid)]=new_qty
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
            if p and qty>0 and p["stock"]>0:
                qty=min(qty,p["stock"],20);row=dict(p);row["quantity"]=qty;rows.append(row);total+=row["price"]*qty
    return rows,total
@shop.get("/cart")
def cart():
    rows,total=contents()
    body="<div class='warning'>체험용 장바구니 · 실제 결제 불가</div><p><a href='/shop'>← 상품 더 보기</a></p>"+("<div class='card'>" if rows else "<div class='card empty-cart'>")
    for p in rows:
        body+="<div class='cart-line'><div><strong><a href='/shop/product/"+str(p["id"])+"'>"+esc(p["name"])+"</a></strong><p>단가 "+f'{p["price"]:,}'+"원 · 소계 "+f'{p["price"]*p["quantity"]:,}'+"원</p></div><div class='cart-controls'><form action='/cart/update' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><label>수량 <input type='number' name='quantity' min='0' max='"+str(min(20,p["stock"]))+"' value='"+str(p["quantity"])+"' required></label><button>변경</button></form><form action='/cart/remove' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><input type='hidden' name='product_id' value='"+str(p["id"])+"'><button class='subtle'>삭제</button></form></div></div>"
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
        if stock<=0:abort(409,"품절된 상품입니다.")
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
        return page("내 계정 · 체험 회원","<div class='warning'>체험용 회원 상태입니다. 실제 회원가입·개인정보 저장은 하지 않습니다.</div><div class='card'><h2>체험 회원으로 로그인 중</h2><p>반갑습니다, "+esc(session.get('demo_nickname') or '소망손님')+"! 소망약국 상품 체험을 계속 이용할 수 있어요.</p><div class='account-shortcuts'><a class='btn' href='/shop'>상품 둘러보기</a><a class='btn' href='/cart'>내 장바구니 ("+str(cart_count())+")</a><a class='btn' href='/checkout'>결제 전 확인</a></div><p><small>체험 계정은 실제 회원 계정이 아니며 주문 내역을 저장하지 않습니다.</small></p><details class='demo-profile'><summary>체험 별명 변경</summary><form action='/demo/rename' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><label for='change-nickname'>새 별명</label><input id='change-nickname' name='nickname' minlength='2' maxlength='16' pattern='[A-Za-z0-9가-힣_-]{2,16}' autocomplete='off' required><button type='submit'>별명 저장</button></form></details><form action='/demo/logout' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><button>체험 로그아웃</button></form><form action='/demo/delete' method='post'><input type='hidden' name='csrf' value='"+csrf()+"'><button type='submit' class='subtle-action'>체험 계정 삭제</button></form></div>")
    if session.get("member_id"):
        with db() as c:
            state=c.execute("SELECT suspended FROM shop_member_controls WHERE member_id=?",(session["member_id"],)).fetchone()
        if state and state["suspended"]:
            session.pop("member_id",None)
            return redirect("/account")
        return page("내 계정","<div class='card'>로그인 상태입니다.<form method='post' action='/logout'><input type='hidden' name='csrf' value='"+csrf()+"'><button>로그아웃</button></form></div>")
    body="<div class='warning'>현재는 미리보기 사이트입니다. 정식 고객 회원가입·로그인은 영구 데이터베이스와 개인정보 보호 준비 전까지 비활성화됩니다.</div><div class='card'><h2>체험 회원가입</h2><p>이름·이메일·전화번호 없이 별명만 정해 회원가입 화면을 체험할 수 있어요. 입력한 별명은 브라우저 세션에만 보관됩니다.</p><form method='post' action='/demo/register'><input type='hidden' name='csrf' value='"+csrf()+"'><label for='demo-nickname'>체험 별명</label><input id='demo-nickname' name='nickname' maxlength='16' minlength='2' pattern='[A-Za-z0-9가-힣_-]{2,16}' placeholder='예: 소망손님' autocomplete='off' required><button type='submit'>체험 회원가입</button></form><p><small>실명이나 개인정보는 입력하지 마세요. 체험 계정은 영구 저장되지 않습니다.</small></p></div><div class='card'><h2>체험 회원 로그인</h2><p>개인정보 입력 없이 회원 화면과 장바구니 연결을 체험해 보세요.</p><form method='post' action='/demo/login'><input type='hidden' name='csrf' value='"+csrf()+"'><button>체험 회원으로 로그인</button></form></div>"
    body+="<div class='card member-coming-soon'><h2>소망약국 회원가입</h2><p>전용 데이터베이스 연결 및 회원 테이블 준비를 완료했습니다. 이메일 인증과 개인정보 보호 검증이 완료되면 정식 가입을 열 예정입니다.</p><div class='member-benefits'><span>✓ 회원 계정 관리</span><span>✓ 장바구니 이용</span><span>✓ 주문 내역 확인 (판매 개시 후)</span></div><p><small>실제 이메일·비밀번호·전화번호를 입력하지 마세요.</small></p><details class='demo-profile'><summary>정식 회원가입 화면 미리 체험하기</summary><p><small>화면 확인 전용입니다. 입력값은 서버로 전송하지 않으며 계정이 생성되지 않습니다.</small></p><form onsubmit='return false'><label>이메일 (예시만 입력)<input type='text' placeholder='example@example.com' autocomplete='off'></label><label>비밀번호 (예시만 입력)<input type='text' placeholder='12자 이상 예시' autocomplete='off'></label><button type='button' disabled>정식 가입은 보안 검증 후 가능</button></form></details></div>"
    return page("회원 로그인 · 회원가입",body)
@shop.get("/membership/connection-status")
def membership_connection_status():
    """Configuration-only status; never exposes database credentials."""
    import somang_member_store
    connected = False
    if somang_member_store.configured():
        try:
            with somang_member_store.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    connected = cur.fetchone()[0] == 1
        except Exception:
            connected = False
    return jsonify(database_configured=somang_member_store.configured(),database_reachable=connected,member_schema_ready=somang_member_store.schema_ready() if connected else False,real_registration_enabled=False,email_verification_enabled=False,preview_only=True)
@shop.post("/demo/register")
def demo_register():
    check()
    nickname=request.form.get("nickname","").strip()
    if not re.fullmatch(r"[A-Za-z0-9가-힣_-]{2,16}",nickname):abort(400)
    session["demo_member"]=True
    session["demo_nickname"]=nickname
    return redirect("/account")
@shop.post("/demo/rename")
def demo_rename():
    check()
    if not session.get("demo_member"):abort(403)
    nickname=request.form.get("nickname","").strip()
    if not re.fullmatch(r"[A-Za-z0-9가-힣_-]{2,16}",nickname):abort(400)
    session["demo_nickname"]=nickname
    return redirect("/account")
@shop.post("/demo/delete")
def demo_delete():
    check()
    cart=session.get("cart",{})
    session.clear()
    session["cart"]=cart
    return redirect("/account")
@shop.post("/demo/login")
def demo_login():
    check()
    session["demo_member"]=True
    session.pop("demo_nickname",None)
    return redirect("/account")
@shop.post("/demo/logout")
def demo_logout():
    check()
    session.pop("demo_member",None)
    session.pop("demo_nickname",None)
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
    abort(503,"임시 SQLite 회원가입은 비활성화되었습니다.")
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
    abort(503,"임시 SQLite 회원 로그인은 비활성화되었습니다.")
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
    body+="<div class='card'><h2>주문자 정보 확인</h2><p><small>정식 판매 전 화면 미리보기입니다. 아래 입력칸은 비활성화되어 있으며 개인정보를 전송하거나 저장하지 않습니다.</small></p><label>주문자 이름<input type='text' placeholder='주문자 이름' disabled autocomplete='off'></label><label>주문자 연락처<input type='tel' placeholder='휴대전화 번호' disabled autocomplete='off'></label><label>주문자 이메일<input type='email' placeholder='이메일 주소' disabled autocomplete='off'></label></div>"
    body+="<div class='card'><h2>배송지 확인</h2><label><input type='checkbox' disabled> 주문자 정보와 동일</label><label>받는 분<input type='text' placeholder='수령인 이름' disabled autocomplete='off'></label><label>받는 분 연락처<input type='tel' placeholder='수령인 연락처' disabled autocomplete='off'></label><label>우편번호<input type='text' placeholder='우편번호' disabled autocomplete='off'></label><button type='button' disabled title='주소 검색 연동 준비 중'>우편번호 검색 (준비 중)</button><label>기본 주소<input type='text' placeholder='도로명 주소' disabled autocomplete='off'></label><label>상세 주소<input type='text' placeholder='동·호수 등' disabled autocomplete='off'></label><fieldset disabled style='border:1px solid #dbe8df;border-radius:10px;padding:12px;margin:14px 0'><legend>배송 요청사항 (선택)</legend><label><input type='radio' name='delivery_request'> 문 앞에 놓아주세요</label><label><input type='radio' name='delivery_request'> 경비실에 맡겨주세요</label><label><input type='radio' name='delivery_request'> 직접 받을게요</label><label>기타 요청사항<input type='text' placeholder='예: 배송 전 연락 부탁드립니다' autocomplete='off'></label></fieldset><p><small>정식 운영 시 주소 검색, 배송비 산정, 주문 정보 확인 및 개인정보 보호 절차를 연결합니다.</small></p></div>"
    return page("결제 전 주문 확인",body)
@shop.get("/payment/status")
def payment_status():
    return jsonify(provider="not_configured",payments_enabled=False,real_orders_enabled=False,message="PG 계약·키·웹훅 검증 및 영구 저장소 설정 전 결제 차단")
