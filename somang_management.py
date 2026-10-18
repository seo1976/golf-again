"""Admin-only member review and return/refund policy preparation.
No actual payment, refund or order operations are performed.
"""
import os, sqlite3, html
from flask import Blueprint, request, session, abort, redirect
from somang_shop import db, csrf, check, page
manage=Blueprint("somang_management",__name__)
def require_admin():
    if not os.environ.get("SOMANG_ADMIN_PASSWORD") or not os.environ.get("SOMANG_SECRET_KEY"):abort(503)
    if not session.get("admin"):abort(403)
def ensure():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS shop_member_controls(member_id INTEGER PRIMARY KEY, suspended INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS shop_member_audit(id INTEGER PRIMARY KEY,member_id INTEGER NOT NULL,action TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS shop_return_drafts(id INTEGER PRIMARY KEY,reference TEXT NOT NULL,category TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT '접수 검토',created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
ensure()
POLICY_SECTIONS=[
 ("반품·교환 신청","일반적인 통신판매의 청약철회 기간은 상품 수령 후 7일을 기본으로 검토합니다. 표시·광고와 다르거나 계약 내용과 다르게 이행된 경우에는 별도의 법정 기간이 적용될 수 있습니다."),
 ("반품 제한 가능 사유","고객 책임으로 상품이 멸실·훼손되거나 사용으로 가치가 현저히 감소한 경우 등 법령상 사유가 있을 수 있습니다. 단, 단순 포장 확인만으로 일률적으로 반품을 거절하지 않으며 사전에 적법하게 고지합니다."),
 ("배송비와 환불","단순 변심의 반환 비용은 원칙적으로 고객 부담, 오배송·하자 등 판매자 귀책은 판매자 부담을 기준으로 검토합니다. 실제 환불은 반품 수령·확인, 법정 기한 및 결제수단별 PG 절차에 따라 처리해야 합니다."),
 ("취급 품목 주의","화장품·건강기능식품·의료기기 등 품목별 판매 자격과 소비자 고지 의무를 별도 확인합니다. 의약품 온라인 판매는 제공하지 않습니다."),
 ("운영 전 확인","판매자 정보, 고객센터, 배송비·반품 주소, 환불 절차, 개인정보처리방침 및 실제 결제 취소 API 검증 후 정책을 확정해야 합니다.")
]
@manage.get("/policy/returns")
def public_policy():
    body="<div class='warning'>반품·교환·환불 정책 초안입니다. 현재 사이트는 체험용으로 실제 주문·결제·환불을 받지 않습니다.</div>"
    for title,description in POLICY_SECTIONS:body+="<section class='card'><h2>"+html.escape(title)+"</h2><p>"+html.escape(description)+"</p></section>"
    body+="<p><a href='/shop'>상품으로 돌아가기</a></p>"
    return page("반품·교환·환불 안내 (초안)",body)
@manage.get("/admin/members")
def members():
    require_admin()
    with db() as c:
        rows=c.execute("SELECT m.id,m.email,m.created_at,COALESCE(x.suspended,0) suspended FROM shop_members m LEFT JOIN shop_member_controls x ON x.member_id=m.id ORDER BY m.id DESC LIMIT 100").fetchall()
        count=c.execute("SELECT COUNT(*) FROM shop_members").fetchone()[0]
    body="<div class='warning'>테스트 회원 전용 관리 화면입니다. 체험 회원은 개인정보를 저장하지 않아 목록에 나타나지 않습니다. 현재 DB는 임시 저장소입니다.</div><p><a href='/admin'>← 관리자</a> · <a href='/admin/returns'>반품·환불 접수 관리</a></p><div class='card'><h2>회원 관리 · 전체 "+str(count)+"명</h2><p>최근 100명 표시 · 비밀번호는 저장된 해시도 노출하지 않습니다.</p>"
    for m in rows:
        status="이용 중지" if m["suspended"] else "테스트 이용 가능"
        action="restore" if m["suspended"] else "suspend"
        label="중지 해제" if m["suspended"] else "이용 중지"
        body+="<div class='cart-line'><div><strong>#"+str(m["id"])+" "+html.escape(m["email"])+"</strong><p>"+html.escape(status)+" · "+html.escape(m["created_at"])+"</p></div><form method='post' action='/admin/members/"+str(m["id"])+"/"+action+"'><input type='hidden' name='csrf' value='"+csrf()+"'><button>"+label+"</button></form></div>"
    if not rows:body+="<p>등록된 테스트 회원이 없습니다.</p>"
    return page("관리자 · 회원 관리",body+"</div>")
@manage.post("/admin/members/<int:member_id>/<action>")
def member_action(member_id,action):
    require_admin();check()
    if action not in ("suspend","restore"):abort(400)
    with db() as c:
        if not c.execute("SELECT 1 FROM shop_members WHERE id=?",(member_id,)).fetchone():abort(404)
        c.execute("INSERT INTO shop_member_controls(member_id,suspended,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(member_id) DO UPDATE SET suspended=excluded.suspended,updated_at=CURRENT_TIMESTAMP",(member_id,1 if action=="suspend" else 0))
        c.execute("INSERT INTO shop_member_audit(member_id,action) VALUES(?,?)",(member_id,action))
    return redirect("/admin/members")
@manage.get("/admin/returns")
def returns():
    require_admin()
    with db() as c:rows=c.execute("SELECT * FROM shop_return_drafts ORDER BY id DESC LIMIT 100").fetchall()
    body="<div class='warning'>반품·환불 업무 준비 화면입니다. 실제 주문번호 검증, 결제 취소, 재고 복구, 환불 송금은 실행하지 않습니다. 실제 고객 개인정보는 입력하지 마세요.</div><p><a href='/admin'>← 관리자</a> · <a href='/admin/members'>회원 관리</a> · <a href='/policy/returns'>정책 초안</a></p><div class='card'><h2>테스트 반품·환불 접수</h2><form method='post' action='/admin/returns'><input type='hidden' name='csrf' value='"+csrf()+"'><label>가상 접수번호 <input name='reference' maxlength='40' required placeholder='TEST-001'></label><label>유형 <select name='category'><option>반품</option><option>교환</option><option>환불</option></select></label><label>사유(개인정보 제외) <input name='reason' maxlength='200' required></label><button>테스트 접수 등록</button></form></div><div class='card'><h2>접수 목록</h2>"
    for r in rows:
        body+="<div class='cart-line'><div><strong>#"+str(r["id"])+" · "+html.escape(r["reference"])+"</strong><p>"+html.escape(r["category"])+" · "+html.escape(r["status"])+"</p><small>"+html.escape(r["reason"])+"</small></div><form method='post' action='/admin/returns/"+str(r["id"])+"/status'><input type='hidden' name='csrf' value='"+csrf()+"'><label>처리 상태 <select name='status'>"
        for status in ("접수 검토","증빙 확인","반품 대기","처리 보류","검토 완료"):
            body+="<option value='"+status+"'"+(" selected" if r["status"]==status else "")+">"+status+"</option>"
        body+="</select></label><button>상태 저장</button></form></div>"
    if not rows:body+="<p>접수된 테스트 건이 없습니다.</p>"
    return page("관리자 · 반품·환불 관리",body+"</div>")
@manage.post("/admin/returns")
def return_create():
    require_admin();check()
    reference=request.form.get("reference","").strip()[:40]
    reason=request.form.get("reason","").strip()[:200]
    category=request.form.get("category","")
    if not reference or not reason or category not in ("반품","교환","환불"):abort(400)
    with db() as c:c.execute("INSERT INTO shop_return_drafts(reference,category,reason) VALUES(?,?,?)",(reference,category,reason))
    return redirect("/admin/returns")

@manage.post("/admin/returns/<int:case_id>/status")
def return_status(case_id):
    require_admin();check()
    status=request.form.get("status","")
    if status not in ("접수 검토","증빙 확인","반품 대기","처리 보류","검토 완료"):abort(400)
    with db() as c:
        if not c.execute("SELECT 1 FROM shop_return_drafts WHERE id=?",(case_id,)).fetchone():abort(404)
        c.execute("UPDATE shop_return_drafts SET status=? WHERE id=?",(status,case_id))
    return redirect("/admin/returns")
