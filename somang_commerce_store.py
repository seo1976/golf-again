"""Durable PostgreSQL commerce operations; SQLite is available only in Flask TESTING."""
import os, re, secrets, time
from contextlib import contextmanager
from pathlib import Path
from flask import current_app

class BusinessError(ValueError): pass

def enabled():
    return os.environ.get('SOMANG_COMMERCE_ENABLED') == '1'

@contextmanager
def connect():
    test_path=current_app.config.get('SOMANG_COMMERCE_TEST_DB')
    if test_path:
        if not current_app.testing: raise RuntimeError('Test database forbidden outside testing')
        import sqlite3
        c=sqlite3.connect(test_path,timeout=15);c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON');c.execute('BEGIN IMMEDIATE')
    else:
        import psycopg
        from psycopg.rows import dict_row
        url=os.environ.get('SOMANG_MEMBERS_DATABASE_URL')
        if not url: raise BusinessError('회원·주문 전용 데이터베이스 연결을 준비 중입니다.')
        c=psycopg.connect(url,connect_timeout=8,row_factory=dict_row)
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback();raise
    finally:c.close()

def sql(c,query,args=()):
    if c.__class__.__module__.startswith('sqlite3'):
        query=query.replace(' FOR UPDATE','').replace('now()','CURRENT_TIMESTAMP')
    else:query=query.replace('?', '%s')
    return c.execute(query,args)

def initialize():
    from somang_member_store import initialize_schema
    if not current_app.config.get('SOMANG_COMMERCE_TEST_DB'): initialize_schema()
    script=Path(__file__).with_name('somang_commerce_schema.sql').read_text()
    with connect() as c:
        if c.__class__.__module__.startswith('sqlite3'):
            c.execute("CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',email_verified_at TEXT,auth_version INTEGER NOT NULL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            c.execute("CREATE TABLE IF NOT EXISTS member_email_tokens(id INTEGER PRIMARY KEY,member_id INTEGER NOT NULL REFERENCES members(id),purpose TEXT,token_digest TEXT UNIQUE,expires_at REAL,consumed_at REAL)")
            script='\n'.join(x for x in script.splitlines() if not x.startswith('ALTER TABLE'))
            script=script.replace('BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY','INTEGER PRIMARY KEY').replace('TIMESTAMPTZ','TEXT').replace('now()','CURRENT_TIMESTAMP')
            c.executescript(script)
        else:c.execute(script)

def settings(c):
    return {r['key']:r['value'] for r in sql(c,'SELECT key,value FROM commerce_settings').fetchall()}

def save_setting(c,key,value):
    sql(c,'INSERT INTO commerce_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))

def audit(c,actor,action,reference=''):
    sql(c,'INSERT INTO commerce_audit(actor,action,reference) VALUES(?,?,?)',(str(actor),action,str(reference)))

def rate_limit(key,limit=10,seconds=900):
    import hashlib
    digest=hashlib.sha256(key.encode()).hexdigest()
    window=int(time.time())//seconds
    with connect() as c:
        row=sql(c,'INSERT INTO commerce_rate(bucket,hits) VALUES(?,1) ON CONFLICT(bucket) DO UPDATE SET hits=commerce_rate.hits+1 RETURNING hits',(f'{window}:{digest}',)).fetchone()
        # Bound storage to at most two windows of this rate-limit horizon.
        sql(c,'DELETE FROM commerce_rate WHERE bucket LIKE ?',(str(window-2)+':%',))
    return row['hits']<=limit

def products(include_hidden=False):
    with connect() as c:
        return [dict(r) for r in sql(c,'SELECT * FROM commerce_products'+('' if include_hidden else ' WHERE published=1 AND compliance_checked=1')+' ORDER BY id DESC').fetchall()]

def member(member_id):
    with connect() as c:
        r=sql(c,'SELECT id,email,status,email_verified_at,auth_version FROM members WHERE id=?',(member_id,)).fetchone()
        return dict(r) if r else None

def shipping_fee(config,total):
    try:
        fee=int(config['shipping_fee']);free=int(config['free_shipping_over'])
        if not 0<=fee<=100000 or not 0<=free<=10000000: raise ValueError
    except (KeyError,ValueError):raise BusinessError('배송비 설정을 먼저 완료해 주세요.')
    return 0 if free>0 and total>=free else fee

def create_order(member_id,cart,data,request_key):
    if not cart or len(cart)>50:raise BusinessError('장바구니를 확인해 주세요.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}',request_key or ''):raise BusinessError('주문 확인 화면을 새로 열어 주세요.')
    values={k:str(data.get(k,'')).strip() for k in ('recipient','phone','postal_code','address','address_detail')}
    if not 1<=len(values['recipient'])<=60 or not re.fullmatch(r'0[0-9-]{8,14}',values['phone']) or not re.fullmatch(r'[0-9]{5}',values['postal_code']) or not 5<=len(values['address'])<=200 or len(values['address_detail'])>200:
        raise BusinessError('수령인, 연락처, 우편번호 5자리와 주소를 확인해 주세요.')
    if data.get('consent')!='yes':raise BusinessError('주문 정보와 개인정보 수집·이용에 동의해 주세요.')
    try:lines=sorted((int(k),int(v)) for k,v in cart.items())
    except (TypeError,ValueError):raise BusinessError('장바구니 수량을 확인해 주세요.')
    if any(q<1 or q>20 for _,q in lines):raise BusinessError('상품 수량은 1~20개입니다.')
    with connect() as c:
        # Serialize submissions per member; duplicate browser submissions return the same order.
        m=sql(c,"SELECT * FROM members WHERE id=? FOR UPDATE",(member_id,)).fetchone()
        if not m or m['status']!='active' or not m['email_verified_at']:raise BusinessError('회원 로그인을 다시 해주세요.')
        existing=sql(c,'SELECT number,member_id FROM commerce_orders WHERE request_key=?',(request_key,)).fetchone()
        if existing:
            if existing['member_id']!=member_id:raise BusinessError('잘못된 주문 요청입니다.')
            return existing['number']
        config=settings(c);items=[];total=0
        if os.environ.get('SOMANG_PAYMENT_MODE') not in ('test','live'):raise BusinessError('결제 모드 설정이 필요합니다.')
        if config.get('policies_ready')!='1':raise BusinessError('배송·판매 정책 설정 후 주문할 수 있습니다.')
        for pid,qty in lines:
            p=sql(c,'SELECT * FROM commerce_products WHERE id=? FOR UPDATE',(pid,)).fetchone()
            if not p or not p['published'] or not p['compliance_checked'] or p['stock']<qty:raise BusinessError('품절되거나 판매가 중지된 상품이 있습니다. 장바구니를 확인해 주세요.')
            items.append((pid,p['name'],p['price'],qty));total+=p['price']*qty
        fee=shipping_fee(config,total)
        number='SM-'+secrets.token_hex(14)
        sql(c,'INSERT INTO commerce_orders(number,mode,member_id,request_key,customer_email,recipient,phone,postal_code,address,address_detail,subtotal,shipping,total,consent_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (number,os.environ.get('SOMANG_PAYMENT_MODE','disabled'),member_id,request_key,m['email'],values['recipient'],values['phone'],values['postal_code'],values['address'],values['address_detail'],total,fee,total+fee,'order-v1'))
        for pid,name,price,qty in items:
            sql(c,'INSERT INTO commerce_items(order_number,product_id,name,price,quantity) VALUES(?,?,?,?,?)',(number,pid,name,price,qty))
            sql(c,'UPDATE commerce_products SET stock=stock-? WHERE id=?',(qty,pid))
        audit(c,member_id,'order.created',number)
        return number

def restore_stock(c,number):
    state=sql(c,'SELECT stock_released FROM commerce_orders WHERE number=? FOR UPDATE',(number,)).fetchone()
    if not state or state['stock_released']:return
    for row in sql(c,'SELECT product_id,quantity FROM commerce_items WHERE order_number=? ORDER BY product_id',(number,)).fetchall():
        sql(c,'UPDATE commerce_products SET stock=stock+? WHERE id=?',(row['quantity'],row['product_id']))
    sql(c,'UPDATE commerce_orders SET stock_released=1 WHERE number=?',(number,))

def order(number,member_id=None):
    with connect() as c:
        r=sql(c,'SELECT * FROM commerce_orders WHERE number=?'+(' AND member_id=?' if member_id else ''),(number,member_id) if member_id else (number,)).fetchone()
        if not r:return None,[]
        items=sql(c,'SELECT * FROM commerce_items WHERE order_number=? ORDER BY product_id',(number,)).fetchall()
        return dict(r),[dict(i) for i in items]
