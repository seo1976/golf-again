"""Somang pharmacy non-sensitive operations reports.
Read-only CSV exports; do not put patient or prescription information here.
"""
import csv, io, os, sqlite3
from flask import Blueprint, session, abort, Response, jsonify, request
reports=Blueprint("somang_reports",__name__,url_prefix="/admin/reports")
def conn():
    from somang_commerce_store import enabled
    if enabled():
        from somang_ops_store import Connection
        return Connection()
    c=sqlite3.connect(os.environ.get("SOMANG_DB_PATH","/tmp/somang_preview.sqlite3"),timeout=15)
    c.row_factory=sqlite3.Row
    return c
def guard():
    if not (session.get("admin") and os.environ.get("SOMANG_SECRET_KEY") and os.environ.get("SOMANG_ADMIN_PASSWORD")):abort(403)
def export(name,query,columns):
    guard()
    with conn() as c: rows=c.execute(query).fetchall()
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(columns)
    for row in rows:
        # Prevent spreadsheet formula injection in CSV opened by Excel.
        if isinstance(row,dict):row=list(row.values())
        writer.writerow(["'"+str(value) if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")) else value for value in row])
    return Response("\ufeff"+stream.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{name}.csv"',"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
@reports.get("/suppliers.csv")
def suppliers():
    return export("somang_suppliers","SELECT id,name,contact,note,created_at FROM suppliers ORDER BY id",["ID","공급사","연락처","메모","등록일"])
@reports.get("/purchase-orders.csv")
def purchases():
    return export("somang_purchase_orders","SELECT p.id,s.name,p.reference,p.status,p.total,p.created_at FROM purchase_orders p JOIN suppliers s ON p.supplier_id=s.id ORDER BY p.id",["ID","공급사","참조번호","상태","금액","등록일"])
@reports.get("/ledger.csv")
def ledger():
    return export("somang_ledger","SELECT id,kind,amount,description,reference,created_at FROM ledger ORDER BY id",["ID","구분","금액","적요","참조","등록일"])
@reports.get("/products.csv")
def products():
    return export("somang_products","SELECT id,name,category,price,stock,approved,visible FROM products ORDER BY id",["ID","상품명","분류","가격","재고","승인","공개"])
@reports.get("/summary")
def summary():
    guard()
    with conn() as c:
        income=c.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE kind='income'").fetchone()[0]
        expense=c.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE kind='expense'").fetchone()[0]
        pending=c.execute("SELECT COUNT(*) FROM purchase_orders WHERE status='draft'").fetchone()[0]
        low=c.execute("SELECT COUNT(*) FROM products WHERE stock BETWEEN 0 AND 3").fetchone()[0]
    if os.environ.get('SOMANG_COMMERCE_ENABLED')=='1' and request.args.get('format')!='json':
        from somang_commerce import screen,admin_nav
        with conn() as c:
            sales=c.execute("SELECT count(*) n,COALESCE(sum(total),0) amount FROM commerce_orders WHERE mode='live' AND state IN ('paid','preparing','shipped','delivered')").fetchone()
        body=admin_nav()+"<div class='commerce-cards'>"+''.join("<div class='card'><h2>"+label+"</h2><strong>"+f'{value:,}'+unit+"</strong></div>" for label,value,unit in [('결제 완료 매출',sales['amount'],'원'),('결제 완료 주문',sales['n'],'건'),('수동 장부 수입',income,'원'),('수동 장부 지출',expense,'원'),('미처리 발주',pending,'건'),('재고 3개 이하',low,'종')])+"</div><p>결제 매출은 실제 결제 완료 주문 기준이며, 수동 장부와 합산하지 않습니다. 세금 신고·결제사 정산 자료를 대체하지 않습니다.</p><div class='card'><h2>CSV 다운로드</h2><nav class='commerce-nav'>"+''.join("<a href='/admin/reports/"+path+".csv'>"+label+"</a>" for path,label in [('products','상품·재고'),('suppliers','공급사'),('purchase-orders','발주'),('ledger','수동 장부'),('orders','주문')])+"</nav></div>"
        return screen('운영 보고서',body)
    return jsonify(income=income,expense=expense,balance=income-expense,draft_purchases=pending,low_stock_products=low,scope="persistent_manual_entries" if os.environ.get("SOMANG_COMMERCE_ENABLED")=="1" else "demo_manual_entries_only",not_tax_or_pg_settlement=True)

@reports.get('/orders.csv')
def orders():
    guard()
    if os.environ.get('SOMANG_COMMERCE_ENABLED')!='1':abort(404)
    return export('somang_orders',"SELECT number,state,mode,total,courier,tracking,created_at FROM commerce_orders ORDER BY created_at DESC",['주문번호','상태','결제 모드','총액','택배사','송장번호','주문일'])
