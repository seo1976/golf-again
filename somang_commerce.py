"""Member storefront and staff commerce console; no demo identity can authorize orders."""
import os,re,secrets,hashlib,time,json
from datetime import timedelta
from urllib.parse import quote,urlparse
from flask import Blueprint,request,session,redirect,abort,jsonify,current_app,render_template_string
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.exceptions import HTTPException
import somang_commerce_store as store
import somang_commerce_payments as pay
from somang_shop import page,esc,csrf,check
commerce=Blueprint('commerce',__name__)
CATEGORIES=('화장품','더마 화장품','두피·모발','생활용품')
STATES={'pending':'결제 대기','checking':'결제 확인 중','paid':'결제 완료','preparing':'배송 준비','shipped':'배송 중','delivered':'배송 완료','cancelled':'주문 취소','refunded':'전액 환불','review':'관리자 확인 필요'}

def form(action,body,label):
    return "<form method='post' action='"+esc(action)+"'><input type='hidden' name='csrf' value='"+csrf()+"'>"+body+"<button>"+esc(label)+"</button></form>"

def field(name,label,kind='text',value='',required=True,extra=''):
    return "<label>"+esc(label)+"<input name='"+name+"' type='"+kind+"' value='"+esc(value)+"' "+('required' if required else '')+" "+extra+"></label>"

def screen(title,body):
    return page(title,"<style>.commerce-nav{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.commerce-status{display:inline-block;background:#e4f1e8;color:#20563d;padding:5px 9px;border-radius:8px;font-weight:700}input,select,textarea{font-size:16px}label input:not([type=checkbox]){display:block;width:100%;max-width:100%;min-height:44px}button{min-height:44px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #dbe8df}.commerce-scroll{overflow-x:auto}.commerce-nav a{padding:9px;background:#e6f1e9;border-radius:8px}.commerce-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}.commerce-cards .card{margin:0}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #247b9b;outline-offset:2px}.commerce-help{padding:12px;border-left:3px solid #54779a;background:#eef5fa;margin:12px 0}</style>"+body)

def message(text,title='안내',code=200):
    return screen(title,"<div class='card'>"+esc(text)+"<p><a href='/account'>내 계정</a> · <a href='/shop'>상품 보기</a></p></div>"),code

def current_member(required=True, verified=True):
    mid=session.get('somang_auth_member_id')
    m=store.member(mid) if session.get('somang_auth_kind')=='persistent_member' and isinstance(mid,int) and not isinstance(mid,bool) else None
    if not m or m['status'] not in ('active','pending') or (verified and (m['status']!='active' or not m['email_verified_at'])) or session.get('somang_auth_version')!=m['auth_version']:
        if required:abort(401,'이메일 인증 후 주문 기능을 이용할 수 있습니다. 내 계정에서 인증 상태를 확인해 주세요.' if m and m['status']=='pending' and session.get('somang_auth_version')==m['auth_version'] else '회원 로그인이 필요합니다.')
        return None
    return m

def staff():
    from somang_preview import admin
    admin()

def admin_nav():
    return "<nav class='commerce-nav'><a href='/admin/sales'>판매 대시보드</a><a href='/admin/sales/products'>상품·재고</a><a href='/admin/sales/orders'>주문·결제·배송</a><a href='/admin/members'>회원</a><a href='/admin/returns'>취소·반품</a><a href='/admin/sales/settings'>판매 설정</a><a href='/admin/ops'>기존 운영 메뉴</a></nav>"+form('/admin/sales/logout','','관리자 로그아웃')

def origin():
    value=os.environ.get('SOMANG_PUBLIC_ORIGIN','https://somang-pharmacy-preview.onrender.com').rstrip('/')
    u=urlparse(value)
    if u.scheme!='https' or not u.netloc or u.username or u.password or u.path:raise store.BusinessError('사이트 주소 설정을 확인해 주세요.')
    return value

def registration_ready():
    # Account creation is independent of checkout and email delivery readiness.
    with store.connect() as c:store.sql(c,'SELECT auth_version FROM members LIMIT 0')
    return bool(os.environ.get('SOMANG_SECRET_KEY'))

def throttle(action,email='',limit=10):
    # Ignore user-supplied forwarding headers. Shared-IP and per-account limits are durable.
    if not store.rate_limit(action+':ip:'+str(request.remote_addr),limit*5) or not store.rate_limit(action+':email:'+email,limit):abort(429,'요청이 많습니다. 잠시 후 다시 시도해 주세요.')

def issue_token(c,mid,purpose):
    raw=secrets.token_urlsafe(32)
    store.sql(c,'UPDATE commerce_tokens SET consumed=1 WHERE member_id=? AND purpose=?',(mid,purpose))
    store.sql(c,'INSERT INTO commerce_tokens(digest,member_id,purpose,expires_at) VALUES(?,?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),mid,purpose,int(time.time())+1800))
    return raw

def account():
    from somang_member_mail import mail_ready
    m=current_member(False, verified=False)
    if m:
        body="<div class='card'><h2>"+esc(m['email'])+"</h2><p>소망약국 회원입니다.</p><div class='account-shortcuts'><a class='btn' href='/shop'>상품 보기</a><a class='btn' href='/cart'>장바구니</a></div>"
        if m['email_verified_at']:body+="<p><a class='btn' href='/orders'>주문·배송 내역</a></p>"
        if not m['email_verified_at']:
            body+="<div class='commerce-help'><strong>회원가입이 완료되었습니다.</strong><p>이메일 인증 후 주문 기능을 이용할 수 있습니다.</p>"
            if mail_ready():body+=form('/members/resend',"<input type='hidden' name='email' value='"+esc(m['email'])+"'>",'인증메일 받기')
            else:body+="<p>인증메일 연결을 준비하고 있습니다. 가입 정보는 안전하게 저장되었습니다.</p>"
            body+="</div>"
        body+=form('/logout','','로그아웃')+"<details><summary>회원 탈퇴</summary><p>진행 중인 주문은 처리 후 탈퇴할 수 있습니다. 주문·결제 기록은 거래 보존 정책에 따라 별도 보관됩니다.</p>"+form('/members/delete',field('password','현재 비밀번호','password',extra="maxlength='200' autocomplete='current-password'"),'비밀번호 확인 후 탈퇴')+"</details></div>"
    else:
        body="<div class='card'><h2>회원 로그인</h2>"+form('/login',field('email','이메일','email',extra="maxlength='254' autocomplete='email'")+field('password','비밀번호','password',extra="maxlength='200' autocomplete='current-password'"),'로그인')+"<a href='/members/reset'>비밀번호 재설정</a></div>"
        if registration_ready():
            body+="<div class='card'><h2>회원가입</h2><p>이메일과 비밀번호로 가입할 수 있어요. 주문 기능은 이메일 인증 후 이용할 수 있습니다.</p>"+form('/register',field('email','이메일','email',extra="maxlength='254' autocomplete='email'")+field('password','비밀번호 (12~200자)','password',extra="minlength='12' maxlength='200' autocomplete='new-password'")+field('password_confirm','비밀번호 확인','password',extra="minlength='12' maxlength='200' autocomplete='new-password'")+"<label><input type='checkbox' name='consent' value='yes' required> <a href='/members/privacy'>개인정보 수집·이용</a> 및 <a href='/members/terms'>이용약관</a> 동의 (필수)</label>",'회원가입')+"</div>"
        else:body+="<div class='commerce-help'>회원 서비스 연결을 확인 중입니다. 잠시 후 다시 이용해 주세요.</div>"
        if mail_ready():body+="<details class='card'><summary>인증메일 다시 받기</summary>"+form('/members/resend',field('email','이메일','email'),'인증메일 재발송')+"</details>"
    return screen('소망약국 회원',body)

def register():
    check()
    if not registration_ready():return message('회원 서비스 연결을 확인 중입니다. 잠시 후 다시 이용해 주세요.',code=503)
    from somang_member_store import normalize_email
    from somang_member_mail import send_account_email, mail_ready
    try:email=normalize_email(request.form.get('email',''))
    except ValueError:raise store.BusinessError('이메일을 확인해 주세요.')
    pw=request.form.get('password','')
    if not 12<=len(pw)<=200 or request.form.get('consent')!='yes':raise store.BusinessError('12자 이상 비밀번호와 필수 동의를 확인해 주세요.')
    if pw!=request.form.get('password_confirm',''):raise store.BusinessError('비밀번호 확인이 일치하지 않습니다.')
    throttle('register',email,3)
    raw=None
    with store.connect() as c:
        r=store.sql(c,'INSERT INTO members(email,password_hash) VALUES(?,?) ON CONFLICT(email) DO NOTHING RETURNING id',(email,generate_password_hash(pw))).fetchone()
        if r:
            store.sql(c,'INSERT INTO commerce_consents(member_id,version) VALUES(?,?)',(r['id'],'member-v1'))
            raw=issue_token(c,r['id'],'verify');store.audit(c,r['id'],'member.registered')
    if raw and mail_ready():
        try:send_account_email(email,raw,'verify')
        except Exception:
            current_app.logger.warning('Account created; verification delivery unavailable')
    return message('가입 신청을 처리했습니다. 입력한 이메일과 비밀번호로 로그인해 주세요. 이미 가입한 이메일은 기존 비밀번호를 이용해 주세요.')

DUMMY_HASH=generate_password_hash('not-a-real-user-'+secrets.token_hex(20))
def login():
    check();email=request.form.get('email','').strip().lower();pw=request.form.get('password','')
    if len(email)>254 or len(pw)>200:abort(400)
    throttle('login',email)
    with store.connect() as c:r=store.sql(c,'SELECT * FROM members WHERE email=?',(email,)).fetchone()
    valid=check_password_hash(r['password_hash'] if r else DUMMY_HASH,pw)
    if not valid or not r or r['status'] not in ('active','pending'):return message('이메일·비밀번호 또는 계정 상태를 확인해 주세요.',code=403)
    cart=session.get('cart',{});session.clear();session.permanent=True
    session.update(somang_auth_kind='persistent_member',somang_auth_member_id=r['id'],somang_auth_version=r['auth_version'],cart=cart)
    return redirect('/account')

@commerce.route('/members/<purpose>',methods=['GET','POST'])
def token_flow(purpose):
    if purpose not in ('verify','reset'):abort(404)
    if request.method=='GET':
        if purpose=='reset' and not request.args.get('finish'):
            return screen('비밀번호 재설정',"<div class='card'>"+form('/members/reset/request',field('email','가입 이메일','email'),'재설정 메일 받기')+"</div>")
        fields="<input type='hidden' id='member-token' name='token'>"
        if purpose=='reset':fields+=field('password','새 비밀번호 (12자 이상)','password',extra="minlength='12' maxlength='200' autocomplete='new-password'")
        return screen('이메일 인증' if purpose=='verify' else '새 비밀번호 설정',"<div class='card'><p>아래 버튼을 눌러 완료해 주세요. 인증 주소는 30분 동안 유효합니다.</p>"+form('/members/'+purpose,fields,'인증 완료' if purpose=='verify' else '비밀번호 변경')+"</div><script>const t=new URLSearchParams(location.hash.slice(1)).get('token')||'';document.getElementById('member-token').value=t;history.replaceState(null,'',location.pathname+location.search);</script>")
    check();throttle('token',limit=20)
    token=request.form.get('token','')
    if not 20<=len(token)<=100:raise store.BusinessError('인증 주소를 다시 확인해 주세요.')
    pw=request.form.get('password','')
    if purpose=='reset' and not 12<=len(pw)<=200:raise store.BusinessError('비밀번호는 12~200자로 입력해 주세요.')
    with store.connect() as c:
        r=store.sql(c,'SELECT * FROM commerce_tokens WHERE digest=? AND purpose=? FOR UPDATE',(hashlib.sha256(token.encode()).hexdigest(),purpose)).fetchone()
        if not r or r['consumed'] or r['expires_at']<time.time():raise store.BusinessError('만료되었거나 이미 사용한 인증 주소입니다. 다시 메일을 요청해 주세요.')
        if purpose=='verify':
            store.sql(c,"UPDATE members SET status='active',email_verified_at=now(),updated_at=now() WHERE id=? AND status='pending'",(r['member_id'],))
        else:
            changed=store.sql(c,"UPDATE members SET password_hash=?,auth_version=auth_version+1,updated_at=now() WHERE id=? AND status='active' AND email_verified_at IS NOT NULL",(generate_password_hash(pw),r['member_id'])).rowcount
            if not changed:raise store.BusinessError('계정 상태를 확인해 주세요.')
        store.sql(c,'UPDATE commerce_tokens SET consumed=1 WHERE member_id=? AND purpose=?',(r['member_id'],purpose))
        store.audit(c,r['member_id'],'member.'+purpose)
    return message('완료했습니다. 회원 로그인으로 이동해 주세요.')

@commerce.post('/members/reset/request')
@commerce.post('/members/resend')
def send_token_again():
    check()
    from somang_member_mail import mail_ready
    if not mail_ready():return message('인증메일 연결을 준비하고 있습니다. 가입한 계정으로 로그인할 수 있습니다.',code=503)
    email=request.form.get('email','').strip().lower()[:254];throttle('email',email,3)
    purpose='verify' if request.path.endswith('resend') else 'reset';raw=None
    with store.connect() as c:
        r=store.sql(c,'SELECT id,status FROM members WHERE email=?',(email,)).fetchone()
        if r and r['status']==('pending' if purpose=='verify' else 'active'):raw=issue_token(c,r['id'],purpose)
    if raw:
        from somang_member_mail import send_account_email
        try:send_account_email(email,raw,purpose)
        except Exception:return message('메일 전송을 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.',code=503)
    return message('해당되는 계정이 있으면 인증메일을 보냈습니다. 메일함을 확인해 주세요.')

@commerce.post('/members/delete')
def delete_member():
    check();m=current_member(verified=False);throttle('delete',m['email'],5)
    with store.connect() as c:
        r=store.sql(c,'SELECT * FROM members WHERE id=? FOR UPDATE',(m['id'],)).fetchone()
        if not check_password_hash(r['password_hash'],request.form.get('password','')[:200]):raise store.BusinessError('비밀번호를 확인해 주세요.')
        if store.sql(c,"SELECT number FROM commerce_orders WHERE member_id=? AND state NOT IN ('delivered','cancelled','refunded') LIMIT 1",(m['id'],)).fetchone():raise store.BusinessError('진행 중인 주문을 먼저 처리해 주세요.')
        store.sql(c,"UPDATE members SET email=?,password_hash=?,status='deleted',auth_version=auth_version+1,updated_at=now() WHERE id=?",('deleted-'+str(m['id'])+'@invalid.local',generate_password_hash(secrets.token_urlsafe(32)),m['id']))
        store.sql(c,'DELETE FROM commerce_tokens WHERE member_id=?',(m['id'],));store.audit(c,m['id'],'member.deleted')
    session.clear();return message('회원 탈퇴가 완료되었습니다.')

@commerce.get('/members/privacy')
@commerce.get('/members/terms')
def policies():
    with store.connect() as c:cfg=store.settings(c)
    if request.path.endswith('privacy'):
        body="<h2>회원·주문 정보 수집 및 이용</h2><p>회원 식별과 이메일 인증: 이메일, 암호화된 비밀번호. 주문·배송 및 고객 상담: 수령인, 연락처, 우편번호, 주소, 주문·결제 내역.</p><p>회원 정보는 탈퇴 시 계정 식별정보를 삭제하며, 거래 기록은 관계 법령과 확정된 보유정책에 따라 별도 보관합니다. 필수 정보 수집에 동의하지 않으면 회원가입·주문을 이용할 수 없습니다.</p><p>수탁 처리: Render(호스팅·데이터 저장), Resend(인증메일), 토스페이먼츠(결제). 카드번호는 소망약국 서버에 저장하지 않습니다.</p>"
    else:body="<h2>소망약국 온라인 이용약관</h2><p>실제 판매 등록 및 확인을 마친 비의약품만 주문할 수 있습니다. 결제사 승인 이후 주문이 확정되며, 주문·결제·배송 내역은 내 계정에서 확인할 수 있습니다.</p><p>결제 전 주문은 직접 취소할 수 있습니다. 결제 후 취소·교환·반품은 고객센터로 요청해 주세요. 배송 이후에는 반품 확인 후 환불합니다.</p>"
    body+="<h2>판매자·고객센터</h2><p>소망약국 · 종로 335, 1층 · 02-742-0075</p><p>"+esc(cfg.get('seller_details','판매자 세부 정보 설정 전입니다.'))+"</p><h2>배송·반품 안내</h2><p>"+esc(cfg.get('shipping_policy','배송·반품 정책 설정 전입니다.'))+"</p><p>개인정보 문의: "+esc(cfg.get('privacy_contact','02-742-0075'))+"</p>"
    return screen('개인정보 안내' if request.path.endswith('privacy') else '이용약관',"<div class='card'>"+body+"</div>")

def catalog():
    q=request.args.get('q','').strip()[:60];cat=request.args.get('category','')[:60];sort=request.args.get('sort','')
    rows=[p for p in store.products() if (not q or q.casefold() in (p['name']+' '+p['description']).casefold()) and (not cat or cat==p['category'])]
    if sort in ('price_asc','price_desc'):rows.sort(key=lambda p:p['price'],reverse=sort=='price_desc')
    body="<form class='shop-search'><label>상품 검색<input name='q' value='"+esc(q)+"'></label><label>정렬<select name='sort'><option value=''>기본순</option><option value='price_asc'>낮은 가격순</option><option value='price_desc'>높은 가격순</option></select></label><button>검색</button><a href='/shop'>전체 상품</a></form><div class='demo-grid'>"
    for p in rows:
        body+="<article class='card product-card'><div class='product-art'>🛍️</div><div class='product-info'><small>"+esc(p['category'])+"</small><h2><a href='/shop/product/"+str(p['id'])+"'>"+esc(p['name'])+"</a></h2><p>"+esc(p['description'][:120])+"</p><strong>"+f"{p['price']:,}원"+"</strong><a class='btn' href='/shop/product/"+str(p['id'])+"'>"+('상품 보기' if p['stock'] else '품절')+"</a></div></article>"
    if not rows:body+="<div class='card'>등록된 판매 상품이 없습니다. 상품 입고 후 안내하겠습니다.</div>"
    return screen('소망약국 온라인 상품',body+"</div>")

def product_detail(pid):
    p=next((p for p in store.products() if p['id']==pid),None)
    if not p:abort(404)
    body="<p><a href='/shop'>← 상품 목록</a></p><div class='card'><small>"+esc(p['category'])+"</small><h2>"+esc(p['name'])+"</h2><p>"+esc(p['description'])+"</p><strong>"+f"{p['price']:,}원"+"</strong>"
    body+=(form('/cart/add',"<input type='hidden' name='product_id' value='"+str(pid)+"'>"+field('quantity','수량','number','1',extra="min='1' max='20'"),'장바구니 담기') if p['stock'] else '<p>품절입니다.</p>')
    return screen(p['name'],body+"<p><a href='/members/terms'>배송·반품 안내</a></p></div>")

def cart_rows():
    products={str(p['id']):p for p in store.products()};rows=[]
    for key,qty in list(session.get('cart',{}).items())[:50]:
        p=products.get(key)
        if not p:raise store.BusinessError('판매하지 않는 상품이 장바구니에 있습니다. 장바구니를 비운 뒤 다시 담아 주세요.')
        try:qty=int(qty)
        except (ValueError,TypeError):raise store.BusinessError('장바구니 수량을 확인해 주세요.')
        if not 1<=qty<=20 or qty>p['stock']:raise store.BusinessError('장바구니 상품의 재고가 부족합니다. 수량을 조정해 주세요.')
        rows.append(dict(p,quantity=qty))
    return rows,sum(p['price']*p['quantity'] for p in rows)

def cart():
    body="<p><a href='/shop'>← 상품 더 보기</a></p><div class='card'>";products={str(p['id']):p for p in store.products()};total=0
    for pid,qty in list(session.get('cart',{}).items())[:50]:
        p=products.get(pid)
        name=p['name'] if p else '판매 종료 상품';price=p['price'] if p else 0
        try:q=int(qty)
        except (TypeError,ValueError):q=0
        total+=price*max(0,q)
        body+="<div class='cart-line'><div><strong>"+esc(name)+"</strong><p>"+f'{price:,}원 × {q}개'+"</p></div>"+form('/cart/update',"<input name='product_id' type='hidden' value='"+esc(pid)+"'>"+field('quantity','수량 (0 입력 시 삭제)','number',str(q),extra="min='0' max='20'"),'변경')+"</div>"
    body+="<h2>상품 합계 "+f'{total:,}원'+"</h2>"+("<a class='btn' href='/checkout'>배송지 입력 · 주문하기</a>" if session.get('cart') else "<p>장바구니가 비어 있습니다.</p><a class='btn' href='/shop'>상품 둘러보기</a>")+form('/commerce/cart/clear','','장바구니 비우기')+"</div>"
    return screen('장바구니',body)

def cart_change():
    check()
    try:pid=int(request.form.get('product_id',''));q=int(request.form.get('quantity','1'))
    except (TypeError,ValueError):abort(400)
    cart=dict(session.get('cart',{}));key=str(pid)
    if request.path.endswith('/remove') or q==0:cart.pop(key,None)
    else:
        p=next((p for p in store.products() if p['id']==pid),None)
        if not p:abort(404)
        if request.path.endswith('/add'):q+=int(cart.get(key,0))
        if not 1<=q<=20 or q>p['stock']:raise store.BusinessError('주문 수량 또는 재고를 확인해 주세요.')
        cart[key]=q
    session['cart']=cart;return redirect('/cart')

@commerce.post('/commerce/cart/clear')
def clear_cart():
    check();session.pop('cart',None);return redirect('/cart')

def checkout():
    m=current_member(False)
    if not m:return redirect('/account')
    rows,total=cart_rows()
    if not rows:return redirect('/cart')
    status=pay.readiness()
    if not status['checkout_enabled']:return message('결제 서비스 설정을 준비 중입니다. 주문·결제는 설정 완료 후 이용할 수 있습니다.',code=503)
    with store.connect() as c:cfg=store.settings(c)
    fee=store.shipping_fee(cfg,total)
    token=session.setdefault('commerce_order_nonce',secrets.token_urlsafe(24))
    body="<div class='card'><h2>주문 상품</h2>"+''.join('<p>'+esc(p['name'])+' × '+str(p['quantity'])+'개 · '+f"{p['price']*p['quantity']:,}원"+'</p>' for p in rows)+f'<p>배송비 {fee:,}원</p><h2>최종 결제금액 {total+fee:,}원</h2>'
    if status['mode']=='test':body+="<div class='warning'>테스트 결제입니다. 실제 출고되지 않습니다.</div>"
    body+="<p>"+esc(cfg.get('shipping_policy',''))+"</p></div><div class='card'><h2>배송 정보</h2>"
    fields="<input type='hidden' name='request_key' value='"+esc(token)+"'>"
    for key,label,kind,limit in [('recipient','받는 분','text',60),('phone','연락처','tel',15),('postal_code','우편번호 (5자리)','text',5),('address','기본 주소','text',200),('address_detail','상세 주소 (선택)','text',200)]:
        fields+=field(key,label,kind,required=key!='address_detail',extra=f"maxlength='{limit}'")
    fields+="<label><input type='checkbox' name='consent' value='yes' required> 상품·배송비·주소를 확인했고 <a href='/members/privacy'>주문 개인정보 수집·이용</a>에 동의합니다.</label>"
    return screen('주문 확인 · 배송지 입력',body+form('/orders',fields,'주문 저장 후 결제')+"<a href='/cart'>← 장바구니 수정</a></div>")

@commerce.post('/orders')
def create_order():
    check();m=current_member()
    if not pay.readiness()['checkout_enabled']:abort(503)
    nonce=request.form.get('request_key','')
    if not nonce or nonce!=session.get('commerce_order_nonce'):abort(400)
    number=store.create_order(m['id'],session.get('cart',{}),request.form,nonce)
    # Keep nonce until payment: repeated submissions are idempotent.
    return redirect('/orders/'+number+'/pay')

@commerce.get('/orders')
def orders():
    m=current_member()
    with store.connect() as c:rows=store.sql(c,'SELECT number,total,state,created_at FROM commerce_orders WHERE member_id=? ORDER BY created_at DESC LIMIT 100',(m['id'],)).fetchall()
    body="<p><a href='/account'>← 내 계정</a></p>"
    for r in rows:body+="<div class='card'><a href='/orders/"+esc(r['number'])+"'>"+esc(r['number'])+"</a><p><span class='commerce-status'>"+STATES[r['state']]+"</span> · "+f"{r['total']:,}원"+"</p></div>"
    if not rows:body+="<div class='card'>주문 내역이 없습니다.</div>"
    return screen('주문·배송 내역',body)

@commerce.get('/orders/<number>')
def order_detail(number):
    m=current_member();o,items=store.order(number,m['id'])
    if not o:abort(404)
    return screen('주문 상세',"<p><a href='/orders'>← 주문 목록</a></p>"+order_body(o,items,False))

def order_body(o,items,is_staff):
    number=o['number'];url=('/admin/sales/orders/' if is_staff else '/orders/')+number
    body="<div class='card'><small>"+('테스트 주문 · 출고 불가' if o['mode']=='test' else '실제 판매 주문')+"</small><h2>"+esc(number)+"</h2><p><span class='commerce-status'>"+STATES[o['state']]+"</span></p>"+''.join('<p>'+esc(i['name'])+' × '+str(i['quantity'])+'개 · '+f"{i['price']*i['quantity']:,}원"+'</p>' for i in items)
    body+=f"<p>상품 {o['subtotal']:,}원 + 배송비 {o['shipping']:,}원</p><h2>합계 {o['total']:,}원</h2><p>"+esc(o['recipient'])+' · '+esc(o['phone'])+'</p><p>'+esc(o['postal_code']+' '+o['address']+' '+o['address_detail'])+'</p>'
    if o['courier']:body+='<p>택배사 '+esc(o['courier'])+' · 송장 '+esc(o['tracking'])+'</p>'
    if o['receipt_url'] and urlparse(o['receipt_url']).scheme=='https':body+="<p><a target='_blank' rel='noopener noreferrer' href='"+esc(o['receipt_url'])+"'>결제 영수증 ↗</a></p>"
    if o['state']=='pending' and not is_staff:body+="<a class='btn' href='/orders/"+esc(number)+"/pay'>결제하기</a>"
    if o['state'] in ('pending','checking','paid','preparing'):
        body+=form(url+'/reconcile','','결제사 상태 다시 확인')
    if o['state']=='pending' or (is_staff and o['state'] in ('paid','preparing','checking')):
        body+=form(url+'/cancel',"<label><input type='checkbox' required name='confirm' value='yes'> "+('주문 취소 및 결제된 금액 전액 환불에 동의합니다.' if is_staff else '결제 전 주문을 취소합니다.')+"</label>",'주문 취소 / 전액 환불' if is_staff else '주문 취소')
    if not is_staff and o['state'] in ('paid','preparing','shipped','delivered'):
        body+="<details><summary>취소·반품 요청</summary>"+form('/orders/'+number+'/return',field('reason','신청 사유 (개인정보 입력 제외)',extra="maxlength='500'"),'관리자에게 취소·반품 요청')+"</details>"
    return body+'</div>'

@commerce.get('/orders/<number>/pay')
def order_pay(number):
    m=current_member();o,items=store.order(number,m['id'])
    if not o:abort(404)
    if o['state']!='pending':return redirect('/orders/'+number)
    ready=pay.readiness()
    if not ready['checkout_enabled']:return message('결제 서비스 설정을 확인 중입니다.',code=503)
    pay.require_mode(o)
    _,client,_,_=pay.configuration()
    config={'method':'CARD','amount':{'currency':'KRW','value':o['total']},'orderId':number,'orderName':items[0]['name'][:70]+(' 외 '+str(len(items)-1)+'건' if len(items)>1 else ''),'successUrl':origin()+'/payments/success','failUrl':origin()+'/payments/fail','customerEmail':m['email']}
    html="<div class='card'><p>"+esc(config['orderName'])+"</p><h2>"+f"{o['total']:,}원"+"</h2>"+('<div class="warning">테스트 결제입니다.</div>' if ready['mode']=='test' else '')+"<button id='pay'>토스 결제창 열기</button><p id='error' role='alert'></p><p><a href='/orders/"+esc(number)+"'>주문 상세</a></p></div>"
    # tojson safely escapes HTML-significant characters in all embedded values.
    script=render_template_string("""<script src="https://js.tosspayments.com/v2/standard"></script><script>
const b=document.getElementById('pay');b.addEventListener('click',async()=>{b.disabled=true;try{
 const payment=TossPayments({{ client|tojson }}).payment({customerKey:{{ customer|tojson }}});
 await payment.requestPayment({{ config|tojson }});
}catch(e){document.getElementById('error').textContent='결제가 완료되지 않았습니다. 주문 내역에서 상태를 확인해 주세요.';b.disabled=false;}});
</script>""",client=client,customer='somang-member-'+str(m['id']),config=config)
    return screen('안전한 결제',html+script)

@commerce.route('/payments/success',methods=['GET','POST'])
def payment_success():
    m=current_member()
    if request.method=='GET':
        number=request.args.get('orderId','');key=request.args.get('paymentKey','');amount=request.args.get('amount','')
        o,_=store.order(number,m['id'])
        if not o:abort(404)
        return screen('결제 승인 확인',"<div class='card'><p>결제사 인증을 마쳤습니다. 아래 버튼으로 최종 승인을 완료해 주세요.</p>"+form('/payments/success',"<input name='orderId' type='hidden' value='"+esc(number)+"'><input name='paymentKey' type='hidden' value='"+esc(key)+"'><input name='amount' type='hidden' value='"+esc(amount)+"'>",'결제 승인 완료')+"</div>")
    check();number=request.form.get('orderId','')
    try:amount=int(request.form.get('amount',''))
    except ValueError:abort(400)
    pay.confirm(number,m['id'],request.form.get('paymentKey',''),amount)
    session.pop('commerce_order_nonce',None);session.pop('cart',None)
    return redirect('/orders/'+number)

@commerce.get('/payments/fail')
def payment_fail():return message('결제가 완료되지 않았습니다. 주문 내역에서 다시 결제하거나 결제 전 주문을 취소할 수 있습니다.')

@commerce.post('/orders/<number>/cancel')
def customer_cancel(number):
    check();m=current_member()
    if request.form.get('confirm')!='yes':abort(400)
    pay.cancel(number,str(m['id']),m['id']);session.pop('commerce_order_nonce',None)
    return redirect('/orders/'+number)

@commerce.post('/orders/<number>/reconcile')
def customer_reconcile(number):
    check();m=current_member();o,_=store.order(number,m['id'])
    if not o:abort(404)
    pay.reconcile(number);return redirect('/orders/'+number)

@commerce.post('/payments/webhook')
def webhook():
    if not store.rate_limit('webhook:'+str(request.remote_addr),60,60):abort(429)
    data=request.get_json(silent=True) or {};payload=data.get('data',{})
    if not isinstance(payload,dict):abort(400)
    number=payload.get('orderId');key=payload.get('paymentKey')
    if not isinstance(number,str) or len(number)>64 or not isinstance(key,str) or len(key)>200:abort(400)
    o,_=store.order(number)
    if not o or not o['payment_key'] or o['payment_key']!=key:abort(404)
    # Never trust webhook status. Authenticated server-to-server lookup is authoritative.
    pay.reconcile(number);return jsonify(ok=True)

@commerce.get('/admin/sales')
def admin_dashboard():
    staff()
    with store.connect() as c:
        members=store.sql(c,"SELECT count(*) n FROM members WHERE status!='deleted'").fetchone()['n']
        rows=store.sql(c,'SELECT state,count(*) n,COALESCE(sum(total),0) amount FROM commerce_orders GROUP BY state').fetchall()
    body=admin_nav()+"<div class='commerce-cards'><div class='card'><h2>회원</h2><strong>"+str(members)+"명</strong></div>"
    for r in rows:body+="<div class='card'><h2>"+STATES[r['state']]+"</h2><strong>"+str(r['n'])+"건</strong><p>"+f"{r['amount']:,}원"+"</p></div>"
    return screen('판매 관리 대시보드',body+"</div><div class='commerce-help'>등록 상품·주문·회원은 전용 PostgreSQL에 저장됩니다. 결제 확인 중인 주문은 중복 결제나 수동 결제완료 처리 없이 결제사 상태를 조회해 주세요.</div>")

@commerce.route('/admin/sales/settings',methods=['GET','POST'])
def admin_settings():
    staff()
    if request.method=='POST':
        check()
        try:fee=int(request.form.get('shipping_fee',''));free=int(request.form.get('free_shipping_over',''))
        except ValueError:raise store.BusinessError('배송비를 숫자로 입력해 주세요.')
        store.shipping_fee({'shipping_fee':str(fee),'free_shipping_over':str(free)},1)
        details=request.form.get('seller_details','').strip();policy=request.form.get('shipping_policy','').strip();contact=request.form.get('privacy_contact','').strip()
        approved=request.form.get('policies_ready')=='1'
        if approved and (len(details)<10 or len(policy)<20 or len(contact)<5):raise store.BusinessError('사업자 정보·배송/반품 정책·개인정보 문의처를 모두 입력해 주세요.')
        with store.connect() as c:
            for key,value in [('shipping_fee',fee),('free_shipping_over',free),('seller_details',details[:2000]),('shipping_policy',policy[:3000]),('privacy_contact',contact[:200]),('policies_ready','1' if approved else '0')]:store.save_setting(c,key,value)
            store.audit(c,'admin','settings.updated')
        return redirect('/admin/sales/settings')
    with store.connect() as c:cfg=store.settings(c)
    from somang_member_mail import mail_ready
    state=pay.readiness()
    body=admin_nav()+"<div class='card'><h2>연결 상태</h2><p>영구 DB: 연결됨</p><p>인증메일: "+('설정됨' if mail_ready() else '설정 필요')+"</p><p>결제 모드: "+esc(state['mode'])+" · 전용 키: "+('설정됨' if state['keys_configured'] else '설정 필요')+"</p><p>주문·결제: "+('활성' if state['checkout_enabled'] else '설정 대기')+"</p><p>웹훅 주소: "+esc(origin()+'/payments/webhook')+"</p><small>비밀키는 이 화면에서 받거나 표시하지 않습니다. Render의 소망약국 전용 환경변수에만 설정합니다.</small></div>"
    fields=field('shipping_fee','기본 배송비 (원)','number',cfg.get('shipping_fee',''),extra="min='0' max='100000'")+field('free_shipping_over','무료배송 기준 (원, 0이면 무료배송 기준 없음)','number',cfg.get('free_shipping_over','0'),extra="min='0' max='10000000'")
    for key,label in [('seller_details','판매자 사업자 정보 (상호·대표자·사업자등록/통신판매 정보 등)'),('shipping_policy','배송 지역·배송 기간·추가 운임·반품 주소·반품비·환불 절차'),('privacy_contact','개인정보 담당자·문의처')]:fields+="<label>"+label+"<textarea name='"+key+"' rows='4' style='width:100%;max-width:100%'>"+esc(cfg.get(key,''))+"</textarea></label>"
    fields+="<label><input type='checkbox' name='policies_ready' value='1' "+('checked' if cfg.get('policies_ready')=='1' else '')+"> 판매자 정보·개인정보 처리 안내·국외 처리/위탁 내용·배송/반품 정책의 실제 운영 내용을 검토하고 확정했습니다.</label>"
    body+="<div class='card'><h2>배송·판매 정책</h2>"+form('/admin/sales/settings',fields,'설정 저장')+"</div><div class='card'><h2>서버 연결 항목</h2><p>인증메일: SOMANG_MAIL_API_KEY, SOMANG_MAIL_FROM</p><p>결제: SOMANG_TOSS_CLIENT_KEY, SOMANG_TOSS_SECRET_KEY, SOMANG_PAYMENT_MODE=test 또는 live</p><p>라이브 개시: 소망약국 명의 계약과 테스트 결제·취소 확인 후 SOMANG_LIVE_APPROVED=1</p><p>다른 사업의 결제키를 재사용하지 마세요.</p></div>"
    return screen('판매 설정 · 연결 상태',body)

@commerce.route('/admin/sales/products',methods=['GET','POST'])
def admin_products():
    staff()
    if request.method=='POST':
        check()
        try:price=int(request.form.get('price',''));stock=int(request.form.get('stock',''))
        except ValueError:raise store.BusinessError('가격과 재고를 확인해 주세요.')
        name=request.form.get('name','').strip()[:100];category=request.form.get('category','')
        if not name or category not in CATEGORIES or not 1<=price<=10000000 or not 0<=stock<=1000000:raise store.BusinessError('상품명·분류·가격·재고를 확인해 주세요.')
        with store.connect() as c:
            r=store.sql(c,'INSERT INTO commerce_products(name,category,description,price,stock) VALUES(?,?,?,?,?) RETURNING id',(name,category,request.form.get('description','')[:5000],price,stock)).fetchone()
            store.audit(c,'admin','product.created',r['id'])
        return redirect('/admin/sales/products')
    fields=field('name','상품명',extra="maxlength='100'")+"<label>분류<select name='category'>"+''.join('<option>'+esc(x)+'</option>' for x in CATEGORIES)+"</select></label>"+field('price','판매가 (원)','number',extra="min='1' max='10000000'")+field('stock','판매 가능 재고','number','0',extra="min='0' max='1000000'")+"<label>상품 상세·표시 정보<textarea name='description' rows='5' maxlength='5000' style='width:100%'></textarea></label>"
    body=admin_nav()+"<div class='card'><h2>실제 판매 상품 등록</h2><p>기존 체험 상품은 판매 대상에서 제외됩니다. 상품은 비공개로 생성됩니다.</p>"+form('/admin/sales/products',fields,'비공개 상품 등록')+"</div>"
    for p in store.products(True):
        body+="<div class='card'><h2>"+esc(p['name'])+"</h2><p>"+esc(p['category'])+' · '+f"{p['price']:,}원"+' · 재고 '+str(p['stock'])+"개</p>"
        fields=field('price','판매가','number',str(p['price']),extra="min='1' max='10000000'")+field('stock_delta','재고 조정 (+입고 / -감소)','number','0',extra="min='-1000000' max='1000000'")
        fields+="<label>상품 설명<textarea name='description' rows='4' maxlength='5000' style='width:100%'>"+esc(p['description'])+"</textarea></label><label><input name='compliance_checked' type='checkbox' value='1' "+('checked' if p['compliance_checked'] else '')+"> 비의약품이며 판매 자격·필수 표시·광고 내용을 확인했습니다.</label><label><input type='checkbox' name='published' value='1' "+('checked' if p['published'] else '')+"> 고객에게 공개</label>"
        body+=form('/admin/sales/products/'+str(p['id']),fields,'상품·재고 저장')+"</div>"
    return screen('실제 상품 · 재고 관리',body)

@commerce.post('/admin/sales/products/<int:pid>')
def admin_product_update(pid):
    staff();check()
    try:price=int(request.form.get('price',''));delta=int(request.form.get('stock_delta','0'))
    except ValueError:abort(400)
    compliant=int(request.form.get('compliance_checked')=='1');published=int(request.form.get('published')=='1')
    if not 1<=price<=10000000 or abs(delta)>1000000 or (published and not compliant):raise store.BusinessError('가격·재고 또는 판매 적법성 확인을 검토해 주세요.')
    with store.connect() as c:
        p=store.sql(c,'SELECT * FROM commerce_products WHERE id=? FOR UPDATE',(pid,)).fetchone()
        if not p:abort(404)
        if p['stock']+delta<0:raise store.BusinessError('예약 재고를 제외한 판매 가능 재고가 부족합니다.')
        store.sql(c,'UPDATE commerce_products SET price=?,stock=stock+?,description=?,published=?,compliance_checked=? WHERE id=?',(price,delta,request.form.get('description','')[:5000],published,compliant,pid))
        store.audit(c,'admin','product.updated',str(pid)+':stock_delta='+str(delta))
    return redirect('/admin/sales/products')

@commerce.get('/admin/sales/orders')
def admin_orders():
    staff();q=request.args.get('q','').strip()[:254];status=request.args.get('state','')
    query='SELECT number,customer_email,total,state,created_at FROM commerce_orders WHERE 1=1';args=[]
    if q:query+=' AND (number=? OR lower(customer_email)=?)';args+=[q,q.lower()]
    if status in STATES:query+=' AND state=?';args.append(status)
    with store.connect() as c:rows=store.sql(c,query+' ORDER BY created_at DESC LIMIT 100',args).fetchall()
    body=admin_nav()+"<form class='shop-search'><label>주문번호 또는 이메일<input name='q' value='"+esc(q)+"'></label><label>상태<select name='state'><option value=''>전체</option>"+''.join("<option value='"+k+"' "+('selected' if k==status else '')+">"+v+"</option>" for k,v in STATES.items())+"</select></label><button>조회</button></form><p>최근 100건 · 이메일/주문번호는 정확히 입력해 주세요.</p>"
    for r in rows:body+="<div class='card'><a href='/admin/sales/orders/"+esc(r['number'])+"'>"+esc(r['number'])+"</a><p>"+esc(r['customer_email'])+"</p><span class='commerce-status'>"+STATES[r['state']]+"</span> · "+f"{r['total']:,}원"+"</div>"
    return screen('주문 · 결제 · 배송 관리',body)

@commerce.get('/admin/sales/orders/<number>')
def admin_order(number):
    staff();o,items=store.order(number)
    if not o:abort(404)
    with store.connect() as c:store.audit(c,'admin','order.viewed',number)
    body=admin_nav()+order_body(o,items,True)
    if o['state'] in ('paid','preparing','shipped'):
        fields="<label>다음 처리<select name='state'>"+''.join("<option value='"+s+"'>"+STATES[s]+"</option>" for s in {'paid':['preparing'],'preparing':['shipped'],'shipped':['delivered']}[o['state']])+"</select></label>"+field('courier','택배사 (출고 시 필수)',value=o['courier'],required=False,extra="maxlength='60'")+field('tracking','송장번호 (출고 시 필수)',value=o['tracking'],required=False,extra="maxlength='60'")
        body+="<div class='card'><h2>배송 처리</h2>"+form('/admin/sales/orders/'+number+'/shipping',fields,'배송 상태 저장')+"</div>"
    with store.connect() as c:
        case=store.sql(c,'SELECT * FROM commerce_returns WHERE order_number=?',(number,)).fetchone()
    if case:
        body+="<div class='card'><h2>취소·반품 요청</h2><p>"+esc(case['reason'])+"</p><p>처리 상태: "+esc(case['state'])+"</p>"
        if case['state']!='refunded':
            fields="<label><input type='checkbox' name='received' value='yes' required> 취소 적격성 또는 반품 수령·검수를 확인했습니다.</label><label><input type='checkbox' name='restock' value='yes'> 반품 상품을 판매 가능 재고로 복구합니다.</label>"
            body+=form('/admin/sales/orders/'+number+'/return',fields,'반품 확인 후 전액 환불')
        body+='</div>'
    return screen('관리자 주문 상세',body)

@commerce.post('/admin/sales/orders/<number>/shipping')
def admin_shipping(number):
    staff();check();state=request.form.get('state','');courier=request.form.get('courier','').strip()[:60];tracking=request.form.get('tracking','').strip()[:60]
    with store.connect() as c:
        o=store.sql(c,'SELECT * FROM commerce_orders WHERE number=? FOR UPDATE',(number,)).fetchone()
        if not o:abort(404)
        if o['mode']!='live':raise store.BusinessError('테스트 결제 주문은 실제 출고할 수 없습니다.')
        if {'paid':'preparing','preparing':'shipped','shipped':'delivered'}.get(o['state'])!=state:raise store.BusinessError('결제 완료 → 배송 준비 → 배송 중 → 배송 완료 순서로 처리해 주세요.')
        if state=='shipped' and (not courier or not re.fullmatch(r'[A-Za-z0-9-]{5,60}',tracking)):raise store.BusinessError('택배사와 송장번호를 입력해 주세요.')
        store.sql(c,'UPDATE commerce_orders SET state=?,courier=?,tracking=?,updated_at=now() WHERE number=?',(state,courier or o['courier'],tracking or o['tracking'],number));store.audit(c,'admin','shipping.'+state,number)
    return redirect('/admin/sales/orders/'+number)

@commerce.post('/admin/sales/orders/<number>/cancel')
@commerce.post('/admin/sales/orders/<number>/reconcile')
def admin_payment_action(number):
    staff();check()
    if request.path.endswith('/cancel'):
        if request.form.get('confirm')!='yes':abort(400)
        pay.cancel(number,'admin')
    else:pay.reconcile(number)
    return redirect('/admin/sales/orders/'+number)

def admin_members():
    staff();q=request.args.get('q','').strip().lower()[:254]
    with store.connect() as c:
        rows=store.sql(c,'SELECT id,email,status,created_at,email_verified_at FROM members'+(' WHERE email=?' if q else '')+' ORDER BY id DESC LIMIT 100',(q,) if q else ()).fetchall()
        store.audit(c,'admin','members.viewed')
    body=admin_nav()+"<form class='shop-search'><label>회원 이메일<input name='q' value='"+esc(q)+"'></label><button>조회</button></form><p>최근 100명 · 비밀번호와 인증 토큰은 표시하지 않습니다.</p>"
    for m in rows:
        body+="<div class='card'><h2>"+esc(m['email'])+"</h2><p>"+{'pending':'인증 대기','active':'이용 중','suspended':'이용 중지','deleted':'탈퇴'}[m['status']]+"</p>"
        if m['status'] in ('active','suspended'):
            action='suspend' if m['status']=='active' else 'restore'
            body+=form('/admin/members/'+str(m['id'])+'/'+action,'','이용 중지' if action=='suspend' else '중지 해제')
        body+="</div>"
    return screen('실제 회원 관리',body)

def admin_member_action(member_id,action):
    staff();check()
    if action not in ('suspend','restore'):abort(400)
    with store.connect() as c:
        r=store.sql(c,'SELECT * FROM members WHERE id=? FOR UPDATE',(member_id,)).fetchone()
        if not r:abort(404)
        if r['status'] not in ('active','suspended') or not r['email_verified_at']:raise store.BusinessError('인증된 회원만 이용 상태를 변경할 수 있습니다.')
        store.sql(c,'UPDATE members SET status=?,auth_version=auth_version+1,updated_at=now() WHERE id=?',('suspended' if action=='suspend' else 'active',member_id));store.audit(c,'admin','member.'+action,member_id)
    return redirect('/admin/members')

def commerce_health():
    state=pay.readiness()
    return jsonify(status='ok',payments_enabled=state['checkout_enabled'],admin_configured=bool(os.environ.get('SOMANG_ADMIN_PASSWORD')),commerce_enabled=True)

def launch_settings():
    staff()
    return jsonify(pay.readiness(),member_registration_enabled=registration_ready(),persistent_db_configured=bool(os.environ.get('SOMANG_MEMBERS_DATABASE_URL')))

def launch_checklist():
    state=pay.readiness()
    return jsonify(ready_for_sales=state['checkout_enabled'],checkout_enabled=state['checkout_enabled'],items=[{'id':k,'status':'configured' if v else 'pending'} for k,v in state.items() if isinstance(v,bool)])

def admin_returns():
    staff()
    with store.connect() as c:
        rows=store.sql(c,'SELECT r.*,o.state order_state FROM commerce_returns r JOIN commerce_orders o ON o.number=r.order_number ORDER BY r.created_at DESC LIMIT 100').fetchall()
    body=admin_nav()
    for r in rows:
        body+="<div class='card'><a href='/admin/sales/orders/"+esc(r['order_number'])+"'>"+esc(r['order_number'])+"</a><p>"+esc(r['reason'])+"</p><p>주문: "+STATES[r['order_state']]+" · 요청 처리: "+esc(r['state'])+"</p></div>"
    if not rows:body+="<div class='card'>접수된 취소·반품 요청이 없습니다.</div>"
    return screen('실제 취소 · 반품 요청',body)

def connection_status():
    with store.connect() as c:
        store.sql(c,'SELECT number FROM commerce_orders LIMIT 0')
        store.sql(c,'SELECT id FROM commerce_products LIMIT 0')
        store.sql(c,'SELECT auth_version FROM members LIMIT 0')
    return jsonify(database_configured=True,database_reachable=True,member_schema_ready=True,
                   commerce_schema_ready=True,email_configured=__import__('somang_member_mail').mail_ready(),stable_session_configured=bool(os.environ.get('SOMANG_SECRET_KEY')),real_registration_enabled=registration_ready(),preview_only=False)

def public_payment_status():
    r=pay.readiness()
    return jsonify(provider='tosspayments',payments_enabled=r['checkout_enabled'],
                   payment_capture_enabled=r['checkout_enabled'],real_orders_enabled=r['checkout_enabled'],mode=r['mode'])

def online_products():
    return screen('온라인 상품',"<div class='card'><h2>소망약국 온라인 스토어</h2><p>화장품·두피/모발·생활용품을 확인해 보세요. 의약품은 온라인으로 판매하지 않습니다.</p><div class='account-shortcuts'><a class='btn' href='/shop'>전체 상품 보기</a><a class='btn' href='/cart'>장바구니</a><a class='btn' href='/account'>회원 로그인</a></div></div>")

@commerce.post('/admin/sales/logout')
def admin_logout():
    staff();check();session.clear();return redirect('/admin')

def dispatch():
    if not store.enabled():return None
    if request.path=='/admin' and request.method=='POST':throttle('admin-login',limit=5)
    if request.path=='/admin' and request.method=='GET' and session.get('admin'):
        staff();return redirect('/admin/sales')
    if request.path.startswith('/demo/') and request.method=='POST':abort(404)
    if request.path.startswith('/admin/returns') and request.method=='POST':raise store.BusinessError('주문 상세 화면에서 실제 취소·반품 요청을 처리해 주세요.')
    endpoint=request.endpoint or ''
    mapping={'somang_management.public_policy':policies,'somang_management.returns':admin_returns,'somang_shop.membership_connection_status':connection_status,'health':commerce_health,'somang_launch.settings':launch_settings,'somang_launch.checklist':launch_checklist,'somang_shop.payment_status':public_payment_status,'somang_payment.readiness':public_payment_status,'online_products':online_products,'somang_shop.account':account,'somang_shop.register':register,'somang_shop.login':login,'somang_shop.catalog':catalog,'somang_shop.product_detail':product_detail,'somang_shop.cart':cart,'somang_shop.add':cart_change,'somang_shop.update_cart':cart_change,'somang_shop.remove':cart_change,'somang_shop.checkout':checkout,'somang_management.members':admin_members,'somang_management.member_action':admin_member_action}
    func=mapping.get(endpoint)
    # The management blueprint is named "somang_manage" in older versions.
    if endpoint.endswith('.members') and request.path=='/admin/members':func=admin_members
    if request.path.startswith('/admin/members/') and request.method=='POST':func=admin_member_action
    if func:return func(**(request.view_args or {}))
    return None

def install(app):
    app.register_blueprint(commerce)
    import sqlite3
    try:
        import psycopg
        db_errors=(psycopg.Error,sqlite3.DatabaseError)
    except ImportError:db_errors=(sqlite3.DatabaseError,)
    def database_unavailable(e):
        current_app.logger.warning('Commerce data operation failed; details withheld')
        return message('회원·주문 서비스 연결을 일시적으로 확인 중입니다. 잠시 후 다시 이용해 주세요.','서비스 연결 확인',503)
    for error_type in db_errors:app.register_error_handler(error_type,database_unavailable)
    app.config['PERMANENT_SESSION_LIFETIME']=timedelta(hours=2)
    app.config['MAX_CONTENT_LENGTH']=128*1024
    app.before_request(dispatch)
    @app.before_request
    def commerce_guard():
        if request.endpoint and request.endpoint.startswith('commerce.') and not store.enabled():abort(503)
    @app.after_request
    def protect_commerce_response(response):
        if store.enabled() and (request.path.startswith(('/account','/members','/orders','/payments','/checkout','/admin','/login','/register'))):
            response.headers['Cache-Control']='no-store'
            response.headers['Referrer-Policy']='no-referrer'
            response.headers['X-Content-Type-Options']='nosniff'
            response.headers['X-Frame-Options']='DENY'
        return response
    @app.errorhandler(store.BusinessError)
    def business_error(e):return message(str(e),'입력·상태 확인',409)
    @app.errorhandler(pay.ProviderError)
    def payment_error(e):return message(str(e),'결제 확인 필요',503)
    if store.enabled():
        with app.app_context():
            try:store.initialize()
            except Exception:app.logger.warning('Commerce database initialization pending; credentials and details withheld')


@commerce.post('/orders/<number>/return')
def request_return(number):
    check();m=current_member();reason=request.form.get('reason','').strip()
    if not 2<=len(reason)<=500:raise store.BusinessError('신청 사유를 2~500자로 입력해 주세요.')
    with store.connect() as c:
        o=store.sql(c,'SELECT * FROM commerce_orders WHERE number=? AND member_id=? FOR UPDATE',(number,m['id'])).fetchone()
        if not o:abort(404)
        if o['state'] not in ('paid','preparing','shipped','delivered'):raise store.BusinessError('현재 상태에서는 신청할 수 없습니다.')
        store.sql(c,'INSERT INTO commerce_returns(order_number,reason) VALUES(?,?) ON CONFLICT(order_number) DO NOTHING',(number,reason));store.audit(c,m['id'],'return.requested',number)
    return message('취소·반품 요청을 접수했습니다. 관리자가 결제·배송 상태를 확인한 뒤 처리합니다.')

@commerce.post('/admin/sales/orders/<number>/return')
def refund_return(number):
    staff();check()
    if request.form.get('received')!='yes':raise store.BusinessError('반품 수령·검수를 확인해 주세요.')
    with store.connect() as c:
        case=store.sql(c,'SELECT * FROM commerce_returns WHERE order_number=? FOR UPDATE',(number,)).fetchone()
        if not case:abort(404)
        if case['state']=='refunded':return redirect('/admin/sales/orders/'+number)
        # Persist the decision before provider call. Retries must not alter restocking.
        restock=1 if request.form.get('restock')=='yes' else 0
        if case['state']=='reviewed':restock=case['restock']
        store.sql(c,"UPDATE commerce_returns SET state='reviewed',received=1,restock=? WHERE order_number=?",(restock,number))
    pay.cancel(number,'admin',returned=True,restock=bool(restock))
    return redirect('/admin/sales/orders/'+number)
