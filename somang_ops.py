"""Somang Pharmacy operations admin. Preview only: no patient or prescription data."""
import os, sqlite3, hmac, secrets, html
from flask import Blueprint, request, session, redirect, abort
ops=Blueprint("somang_ops",__name__,url_prefix="/admin/ops")
def conn():
    c=sqlite3.connect(os.environ.get("SOMANG_DB_PATH","/tmp/somang_preview.sqlite3"),timeout=15)
    c.row_factory=sqlite3.Row
    return c
def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,contact TEXT DEFAULT '',note TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY,alias TEXT NOT NULL,note TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS purchase_orders(id INTEGER PRIMARY KEY,supplier_id INTEGER NOT NULL,reference TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',total INTEGER NOT NULL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(supplier_id) REFERENCES suppliers(id));
        CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,amount INTEGER NOT NULL,description TEXT NOT NULL,reference TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL,change_qty INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS inventory_lots(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL,lot_code TEXT NOT NULL,expiry_date TEXT NOT NULL,quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(product_id,lot_code,expiry_date));
        CREATE TABLE IF NOT EXISTS inventory_disposals(id INTEGER PRIMARY KEY,lot_id INTEGER NOT NULL,product_id INTEGER NOT NULL,quantity INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS ops_audit(id INTEGER PRIMARY KEY,action TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
init()
def guard(post=False):
    if not os.environ.get("SOMANG_ADMIN_PASSWORD") or not os.environ.get("SOMANG_SECRET_KEY") or not session.get("admin"):abort(403)
    if post and (not session.get("csrf") or not hmac.compare_digest(session["csrf"],request.form.get("csrf",""))):abort(400)
def esc(x):return html.escape(str(x),quote=True)
def csrf():return esc(session.get("csrf",""))
def layout(title,body):
    return """<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>소망약국 운영관리</title><style>body{font-family:system-ui,sans-serif;background:#f5faf6;color:#244638;margin:0}header{background:#1d5945;color:white;padding:18px 5%}main{max-width:1100px;margin:auto;padding:25px 16px}a{color:#216f55}header a{color:white}nav{display:flex;gap:15px;flex-wrap:wrap;margin:18px 0}.box{background:white;border:1px solid #dce9e0;border-radius:13px;padding:20px;margin:14px 0}input,select{padding:10px;margin:5px;max-width:95%;border:1px solid #ccc;border-radius:7px}button{padding:10px 15px;background:#267456;color:white;border:0;border-radius:7px}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #eee}small{color:#667}form{display:flex;flex-wrap:wrap;gap:7px;align-items:center} .scroll{overflow-x:auto}</style><header><b>✚ 소망약국 · 통합 운영관리</b>　<a href="/">홈페이지</a>　<a href="/admin">상품 관리</a></header><main><nav><a href="/admin/ops">대시보드</a><a href="/admin/ops/suppliers">공급사·발주</a><a href="/admin/ops/customers">고객 관리</a><a href="/admin/ops/ledger">매출·매입 장부</a><a href="/admin/ops/stock">재고</a><a href="/admin/ops/lots">로트·유통기한</a></nav><h1>"""+esc(title)+"</h1><p><small>개발용 운영 화면 · 현재 무료 서버의 데이터는 영구 보관되지 않습니다. 실제 고객 개인정보 및 실거래를 입력하지 마세요.</small></p>"+body+"</main></html>"
def form(action,fields,button):
    return "<form method='post' action='"+action+"'><input type='hidden' name='csrf' value='"+csrf()+"'>"+fields+"<button>"+button+"</button></form>"
def audit(c,action,details):c.execute("INSERT INTO ops_audit(action,details) VALUES(?,?)",(action,details))
@ops.get("")
@ops.get("/")
def dashboard():
    guard()
    with conn() as c:
        stats={t:c.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in ("suppliers","customers","purchase_orders","ledger","stock_movements")}
        revenue=c.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE kind='income'").fetchone()[0]
        cost=c.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE kind='expense'").fetchone()[0]
    return layout("운영 대시보드","<div class='box'><h2>운영 현황</h2>"+''.join("<p>"+esc(k)+" : <b>"+str(v)+"</b></p>" for k,v in stats.items())+f"<p>기록된 수입 {revenue:,}원 / 지출 {cost:,}원 / 차액 {revenue-cost:,}원</p><small>장부는 수동 입력 기준이며 PG 정산이나 회계 신고자료와 자동 연동되지 않습니다.</small></div>")
@ops.route("/suppliers",methods=["GET","POST"])
def suppliers():
    guard(request.method=="POST")
    if request.method=="POST":
        name=request.form.get("name","").strip()[:100]
        if not name:abort(400)
        with conn() as c:
            c.execute("INSERT INTO suppliers(name,contact,note) VALUES(?,?,?)",(name,request.form.get("contact","")[:120],request.form.get("note","")[:200]))
            audit(c,"supplier.create",name)
        return redirect("/admin/ops/suppliers")
    with conn() as c:
        rows=c.execute("SELECT * FROM suppliers ORDER BY id DESC LIMIT 100").fetchall()
        orders=c.execute("SELECT p.id,s.name,p.reference,p.total,p.status FROM purchase_orders p JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.id DESC LIMIT 100").fetchall()
    body="<div class='box'><h2>공급사 등록</h2>"+form("/admin/ops/suppliers","<input name='name' placeholder='공급사명' required maxlength='100'><input name='contact' placeholder='연락처 (테스트용)'><input name='note' placeholder='메모'>","공급사 추가")+"</div><div class='box'><h2>공급사 목록</h2>"+''.join("<p>#"+str(r["id"])+" "+esc(r["name"])+" · "+esc(r["note"])+"</p>" for r in rows)+"</div><div class='box'><h2>발주 초안 작성</h2>"+form("/admin/ops/purchase","<select name='supplier_id'>"+''.join("<option value='"+str(r["id"])+"'>"+esc(r["name"])+"</option>" for r in rows)+"</select><input name='reference' placeholder='발주번호/설명' required><input type='number' name='total' min='0' placeholder='발주금액' required>","발주 초안 저장")+"</div><div class='box'><h2>발주 목록</h2>"+''.join("<p>#"+str(r[0])+" "+esc(r[1])+" · "+esc(r[2])+" · "+str(r[3])+"원 · "+esc(r[4])+"</p>" for r in orders)+"</div>"
    with conn() as c:
        products=c.execute("SELECT id,name FROM products ORDER BY id DESC LIMIT 100").fetchall()
    draft_options="".join("<option value='"+str(r[0])+"'>#"+str(r[0])+" "+esc(r[2])+"</option>" for r in orders if r[4]=="draft")
    product_options="".join("<option value='"+str(p[0])+"'>"+esc(p[1])+"</option>" for p in products)
    if draft_options and product_options:
        fields="<select name='order_id'>"+draft_options+"</select><select name='product_id'>"+product_options+"</select><input type='number' name='quantity' min='1' required placeholder='입고 수량'>"
        body+="<div class='box'><h2>발주 입고 확정 (테스트)</h2><p>현재 발주 1건당 상품 1종만 입고 처리할 수 있습니다. 재고와 매입 장부가 동시에 반영됩니다.</p>"+form("/admin/ops/purchase/receive",fields,"입고 확정")+"</div>"
    return layout("공급사 및 발주",body)
@ops.post("/purchase")
def purchase():
    guard(True)
    try:sid=int(request.form.get("supplier_id",""));amount=int(request.form.get("total",""))
    except ValueError:abort(400)
    ref=request.form.get("reference","").strip()[:100]
    if not ref or amount<0:abort(400)
    with conn() as c:
        if not c.execute("SELECT 1 FROM suppliers WHERE id=?",(sid,)).fetchone():abort(400)
        c.execute("INSERT INTO purchase_orders(supplier_id,reference,total) VALUES(?,?,?)",(sid,ref,amount))
        audit(c,"purchase.draft",ref)
    return redirect("/admin/ops/suppliers")
@ops.route("/customers",methods=["GET","POST"])
def customers():
    guard(request.method=="POST")
    if request.method=="POST":
        alias=request.form.get("alias","").strip()[:100]
        if not alias:abort(400)
        with conn() as c:
            c.execute("INSERT INTO customers(alias,note) VALUES(?,?)",(alias,request.form.get("note","")[:200]))
            audit(c,"customer.demo.create",alias)
        return redirect("/admin/ops/customers")
    with conn() as c:rows=c.execute("SELECT id,alias,note FROM customers ORDER BY id DESC LIMIT 100").fetchall()
    return layout("고객 관리 (가명 테스트)", "<div class='box'><p>실제 고객 이름·연락처·주소·처방정보 입력 금지. 가명으로 업무 흐름만 테스트합니다.</p>"+form("/admin/ops/customers","<input name='alias' placeholder='테스트 고객 가명' required><input name='note' placeholder='메모'>","테스트 고객 추가")+"</div><div class='box'>"+''.join("<p>#"+str(r["id"])+" "+esc(r["alias"])+" · "+esc(r["note"])+"</p>" for r in rows)+"</div>")
@ops.route("/ledger",methods=["GET","POST"])
def ledger():
    guard(request.method=="POST")
    if request.method=="POST":
        kind=request.form.get("kind","")
        if kind not in ("income","expense"):abort(400)
        try:amount=int(request.form.get("amount",""))
        except ValueError:abort(400)
        description=request.form.get("description","").strip()[:200]
        if amount<0 or not description:abort(400)
        with conn() as c:
            c.execute("INSERT INTO ledger(kind,amount,description,reference) VALUES(?,?,?,?)",(kind,amount,description,request.form.get("reference","")[:80]))
            audit(c,"ledger.entry",kind)
        return redirect("/admin/ops/ledger")
    with conn() as c:rows=c.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT 100").fetchall()
    body="<div class='box'><h2>수동 장부 기록</h2>"+form("/admin/ops/ledger","<select name='kind'><option value='income'>수입</option><option value='expense'>지출</option></select><input type='number' name='amount' min='0' required placeholder='금액'><input name='description' required placeholder='적요'><input name='reference' placeholder='참조번호'>","장부 기록")+"</div><div class='box scroll'><table><tr><th>일시</th><th>구분</th><th>금액</th><th>적요</th></tr>"+''.join("<tr><td>"+esc(r["created_at"])+"</td><td>"+esc(r["kind"])+"</td><td>"+f'{r["amount"]:,}'+"</td><td>"+esc(r["description"])+"</td></tr>" for r in rows)+"</table></div>"
    return layout("매출·매입 장부",body)
@ops.get("/stock")
def stock():
    guard()
    with conn() as c:
        rows=c.execute("SELECT id,name,stock,approved,visible FROM products ORDER BY id DESC LIMIT 100").fetchall()
        movements=c.execute("SELECT m.created_at,p.name,m.change_qty,m.reason FROM stock_movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 50").fetchall()
    body="<div class='box'><h2>입고·출고·재고 조정</h2><p>입고는 양수, 출고는 음수로 입력합니다. 로트·유통기한은 별도 메뉴에서 관리합니다. 일반 재고와 로트 재고의 자동 배분은 아직 연결되지 않았습니다.</p>"+form('/admin/ops/stock/adjust',"<select name='product_id'>"+''.join("<option value='"+str(r['id'])+"'>"+esc(r['name'])+"</option>" for r in rows)+"</select><input name='change_qty' type='number' required placeholder='수량 변화 (+/-)'><input name='reason' required maxlength='120' placeholder='입고/출고 사유'>","재고 변경 기록")+"</div><div class='box'><h2>상품별 재고</h2>"+''.join("<p>#"+str(r["id"])+" "+esc(r["name"])+" · "+str(r["stock"])+"개 · 승인 "+str(r["approved"])+" · 공개 "+str(r["visible"])+"</p>" for r in rows)+"<p>재고 이력 기록을 위해 위 입고·출고 기능을 사용하세요. 상품 관리 화면의 직접 수정도 이동 이력에 기록됩니다.</p></div><div class='box'><h2>재고 이동 기록</h2>"+''.join("<p>"+esc(r[0])+" "+esc(r[1])+" "+str(r[2])+" · "+esc(r[3])+"</p>" for r in movements)+"<p><small>관리자 재고 변경은 이동 이력에 기록됩니다.</small></p></div>"
    return layout("재고 현황",body)

@ops.post("/stock/adjust")
def adjust_stock():
    """Atomically adjust stock and append an inventory movement record."""
    guard(True)
    try:
        pid=int(request.form.get("product_id",""))
        delta=int(request.form.get("change_qty",""))
    except (ValueError,TypeError):abort(400)
    reason=request.form.get("reason","").strip()[:120]
    if not reason or delta==0 or abs(delta)>100000:abort(400)
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()
        if row is None or row["stock"]+delta<0:abort(400)
        c.execute("UPDATE products SET stock=stock+? WHERE id=?",(delta,pid))
        c.execute("INSERT INTO stock_movements(product_id,change_qty,reason) VALUES(?,?,?)",(pid,delta,reason))
        audit(c,"stock.adjust",f"product={pid},change={delta},reason={reason}")
    return redirect("/admin/ops/stock")

@ops.post("/purchase/receive")
def receive_purchase():
    """Receive a single-product demo purchase order exactly once."""
    guard(True)
    try:
        order_id=int(request.form.get("order_id",""))
        product_id=int(request.form.get("product_id",""))
        qty=int(request.form.get("quantity",""))
    except (TypeError,ValueError):abort(400)
    if qty<=0 or qty>100000:abort(400)
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")
        order=c.execute("SELECT id,reference,total,status FROM purchase_orders WHERE id=?",(order_id,)).fetchone()
        product=c.execute("SELECT id FROM products WHERE id=?",(product_id,)).fetchone()
        if order is None or product is None:abort(404)
        if order["status"]!="draft":abort(409,"이미 처리된 발주입니다.")
        c.execute("UPDATE purchase_orders SET status='received' WHERE id=?",(order_id,))
        c.execute("UPDATE products SET stock=stock+? WHERE id=?",(qty,product_id))
        c.execute("INSERT INTO stock_movements(product_id,change_qty,reason) VALUES(?,?,?)",(product_id,qty,f"발주 #{order_id} 입고"))
        c.execute("INSERT INTO ledger(kind,amount,description,reference) VALUES('expense',?,?,?)",(order["total"],"발주 입고 확정 (테스트)",f"PO-{order_id}"))
        audit(c,"purchase.received",f"order={order_id},product={product_id},qty={qty},amount={order['total']}")
    return redirect("/admin/ops/suppliers")

@ops.post("/lots/receive")
def receive_lot():
    """Register a non-medicine demo batch with expiry and stock movement."""
    guard(True)
    try:
        pid=int(request.form.get("product_id",""))
        qty=int(request.form.get("quantity",""))
    except (ValueError,TypeError):abort(400)
    lot=request.form.get("lot_code","").strip()[:60]
    expiry=request.form.get("expiry_date","").strip()
    import datetime
    try:datetime.date.fromisoformat(expiry)
    except ValueError:abort(400)
    if not lot or qty<=0 or qty>100000:abort(400)
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")
        product=c.execute("SELECT id,category FROM products WHERE id=?",(pid,)).fetchone()
        if product is None:abort(404)
        if "의약품" in product["category"]:abort(400,"의약품 로트는 이 쇼핑몰에서 취급하지 않습니다.")
        c.execute("INSERT INTO inventory_lots(product_id,lot_code,expiry_date,quantity) VALUES(?,?,?,?) ON CONFLICT(product_id,lot_code,expiry_date) DO UPDATE SET quantity=quantity+excluded.quantity",(pid,lot,expiry,qty))
        c.execute("UPDATE products SET stock=stock+? WHERE id=?",(qty,pid))
        c.execute("INSERT INTO stock_movements(product_id,change_qty,reason) VALUES(?,?,?)",(pid,qty,f"LOT {lot} expiry {expiry}"))
        audit(c,"lot.received",f"product={pid},lot={lot},qty={qty}")
    return redirect("/admin/ops/stock")
@ops.get("/lots")
def lots():
    guard()
    with conn() as c:
        rows=c.execute("SELECT l.id,l.lot_code,l.expiry_date,l.quantity,p.name FROM inventory_lots l JOIN products p ON p.id=l.product_id ORDER BY l.expiry_date,l.id LIMIT 200").fetchall()
        products=c.execute("SELECT id,name FROM products WHERE category NOT LIKE '%의약품%' ORDER BY id DESC LIMIT 100").fetchall()
    fields="<select name='product_id'>"+''.join("<option value='"+str(p['id'])+"'>"+esc(p['name'])+"</option>" for p in products)+"</select><input name='lot_code' required maxlength='60' placeholder='로트번호'><input name='expiry_date' type='date' required><input name='quantity' type='number' min='1' required placeholder='입고 수량'>"
    body="<div class='box'><h2>로트·유통기한 입고 (개발용)</h2><p>의약품이 아닌 품목에 한정합니다. 일반 재고와 로트 재고는 아직 출고 배분이 연결되지 않았습니다.</p>"+form("/admin/ops/lots/receive",fields,"로트 입고")+"</div><div class='box'><h2>유통기한순 재고</h2>"+''.join("<p>"+esc(r['name'])+" · "+esc(r['lot_code'])+" · "+esc(r['expiry_date'])+" · "+str(r['quantity'])+"개</p>" for r in rows)+"</div>"
    import datetime
    today=datetime.date.today()
    cutoff=today+datetime.timedelta(days=30)
    expired=[r for r in rows if r["expiry_date"]<today.isoformat()]
    soon=[r for r in rows if today.isoformat()<=r["expiry_date"]<=cutoff.isoformat()]
    body="<div class='box'><h2>유통기한 주의</h2><p>기한 경과 "+str(len(expired))+"건 · 30일 이내 "+str(len(soon))+"건</p><p>경과 품목은 판매 가능 상태를 별도로 확인해야 합니다. 현재 자동 판매 차단은 미구현입니다.</p></div>"+body
    options="".join("<option value='"+str(r["id"])+"'>"+esc(r["name"])+" / "+esc(r["lot_code"])+" / "+esc(r["expiry_date"])+" ("+str(r["quantity"])+"개)</option>" for r in rows if r["quantity"]>0 and r["expiry_date"]>=today.isoformat())
    if options:
        body+="<div class='box'><h2>로트별 출고 (개발용)</h2><p>유통기한이 지난 로트는 선택할 수 없으며 서버에서도 출고를 거부합니다. 실제 판매 주문과는 연결되지 않습니다.</p>"+form("/admin/ops/lots/dispatch","<select name='lot_id'>"+options+"</select><input type='number' name='quantity' min='1' required placeholder='출고 수량'>","로트 출고")+"</div>"
    dispose_options="".join("<option value='"+str(r["id"])+"'>"+esc(r["name"])+" / "+esc(r["lot_code"])+" ("+str(r["quantity"])+"개)</option>" for r in rows if r["quantity"]>0)
    if dispose_options:
        fields="<select name='lot_id'>"+dispose_options+"</select><input type='number' name='quantity' min='1' required placeholder='폐기 수량'><input name='reason' required maxlength='120' placeholder='폐기 사유'>"
        body+="<div class='box'><h2>로트 폐기 기록 (개발용)</h2><p>유통기한 경과 등 폐기 사유를 기록하고 재고를 차감합니다. 실제 폐기 절차를 대체하지 않습니다.</p>"+form("/admin/ops/lots/dispose",fields,"폐기 기록")+"</div>"
    return layout("로트·유통기한",body)

@ops.post("/lots/dispatch")
def dispatch_lot():
    """Demo FEFO dispatch. Expired batches cannot be dispatched."""
    guard(True)
    try:
        lot_id=int(request.form.get("lot_id",""))
        qty=int(request.form.get("quantity",""))
    except (ValueError,TypeError):abort(400)
    if qty<=0 or qty>100000:abort(400)
    import datetime
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")
        lot=c.execute("SELECT id,product_id,quantity,expiry_date,lot_code FROM inventory_lots WHERE id=?",(lot_id,)).fetchone()
        if lot is None:abort(404)
        if lot["expiry_date"]<datetime.date.today().isoformat():abort(409,"유통기한 경과 로트는 출고할 수 없습니다.")
        if lot["quantity"]<qty:abort(409,"로트 재고 부족")
        product=c.execute("SELECT stock FROM products WHERE id=?",(lot["product_id"],)).fetchone()
        if product is None or product["stock"]<qty:abort(409,"상품 재고 부족")
        c.execute("UPDATE inventory_lots SET quantity=quantity-? WHERE id=?",(qty,lot_id))
        c.execute("UPDATE products SET stock=stock-? WHERE id=?",(qty,lot["product_id"]))
        c.execute("INSERT INTO stock_movements(product_id,change_qty,reason) VALUES(?,?,?)",(lot["product_id"],-qty,f"LOT {lot['lot_code']} demo dispatch"))
        audit(c,"lot.dispatch",f"lot={lot_id},qty={qty}")
    return redirect("/admin/ops/lots")

@ops.post("/lots/dispose")
def dispose_lot():
    """Write off a lot with reason and inventory audit; demo only."""
    guard(True)
    try:
        lot_id=int(request.form.get("lot_id",""))
        qty=int(request.form.get("quantity",""))
    except (ValueError,TypeError):abort(400)
    reason=request.form.get("reason","").strip()[:120]
    if not reason or qty<=0 or qty>100000:abort(400)
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")
        lot=c.execute("SELECT id,product_id,quantity,lot_code FROM inventory_lots WHERE id=?",(lot_id,)).fetchone()
        if lot is None:abort(404)
        if lot["quantity"]<qty:abort(409,"로트 재고 부족")
        product=c.execute("SELECT stock FROM products WHERE id=?",(lot["product_id"],)).fetchone()
        if product is None or product["stock"]<qty:abort(409,"상품 재고 부족")
        c.execute("UPDATE inventory_lots SET quantity=quantity-? WHERE id=?",(qty,lot_id))
        c.execute("UPDATE products SET stock=stock-? WHERE id=?",(qty,lot["product_id"]))
        c.execute("INSERT INTO inventory_disposals(lot_id,product_id,quantity,reason) VALUES(?,?,?,?)",(lot_id,lot["product_id"],qty,reason))
        c.execute("INSERT INTO stock_movements(product_id,change_qty,reason) VALUES(?,?,?)",(lot["product_id"],-qty,f"LOT {lot['lot_code']} disposal: {reason}"))
        audit(c,"lot.disposal",f"lot={lot_id},qty={qty},reason={reason}")
    return redirect("/admin/ops/lots")
