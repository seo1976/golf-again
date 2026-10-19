"""Toss Payments adapter. Only provider-verified payment state may mark an order paid."""
import os,json,base64
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from urllib.parse import quote,urlparse
from somang_commerce_store import connect,sql,settings,audit,restore_stock,BusinessError

class ProviderError(Exception): pass

def configuration():
    mode=os.environ.get('SOMANG_PAYMENT_MODE','disabled')
    client=os.environ.get('SOMANG_TOSS_CLIENT_KEY','');secret=os.environ.get('SOMANG_TOSS_SECRET_KEY','')
    prefix={'test':'test_','live':'live_'}.get(mode)
    valid=bool(prefix and client.startswith(prefix+'ck_') and secret.startswith(prefix+'sk_'))
    return mode,client,secret,valid

def readiness():
    mode,_,_,keys=configuration()
    with connect() as c:cfg=settings(c)
    policy=cfg.get('policies_ready')=='1'
    try:
        from somang_commerce_store import shipping_fee
        shipping_fee(cfg,1);shipping=True
    except BusinessError:shipping=False
    live_ok=mode!='live' or os.environ.get('SOMANG_LIVE_APPROVED')=='1'
    ready=keys and policy and shipping and live_ok and bool(os.environ.get('SOMANG_SECRET_KEY'))
    return {'mode':mode,'keys_configured':keys,'policies_ready':policy,'shipping_configured':shipping,'live_approved':live_ok,'checkout_enabled':ready}

def provider(method,path,payload=None,idempotency=None):
    mode,_,secret,valid=configuration()
    if not valid:raise ProviderError('결제 설정을 확인해 주세요.')
    headers={'Authorization':'Basic '+base64.b64encode((secret+':').encode()).decode(),'Content-Type':'application/json'}
    if idempotency:headers['Idempotency-Key']=idempotency
    req=Request('https://api.tosspayments.com'+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers,method=method)
    try:
        with urlopen(req,timeout=12) as r:return json.load(r)
    except HTTPError as e:
        # Never include provider bodies, credentials or customer data in error pages/logs.
        if e.code==404:return None
        raise ProviderError('결제사 확인이 필요합니다. 잠시 후 주문 내역에서 다시 확인해 주세요.') from None
    except (URLError,TimeoutError,ValueError):raise ProviderError('결제 결과 확인 중입니다. 중복 결제하지 말고 다시 확인해 주세요.') from None

def require_mode(order):
    if order['mode']!=configuration()[0]:raise BusinessError('주문 당시 결제 모드와 현재 설정이 다릅니다. 관리자 확인이 필요합니다.')

def valid_payment(order,p):
    return bool(p and p.get('orderId')==order['number'] and p.get('totalAmount')==order['total'] and p.get('currency')=='KRW' and isinstance(p.get('paymentKey'),str) and 1<=len(p['paymentKey'])<=200)

def sync(c,o,p):
    if not valid_payment(o,p):raise ProviderError('결제금액 또는 주문 정보가 일치하지 않습니다. 관리자에게 문의해 주세요.')
    if o['payment_key'] and o['payment_key']!=p['paymentKey']:raise ProviderError('결제 정보 확인이 필요합니다.')
    status=p.get('status')
    if status=='DONE':
        if p.get('balanceAmount')!=o['total']:
            sql(c,"UPDATE commerce_orders SET state='review',updated_at=now() WHERE number=?",(o['number'],));return
        if o['state'] in ('pending','checking'):
            url=p.get('receipt',{}).get('url','') if isinstance(p.get('receipt'),dict) else ''
            parsed=urlparse(url)
            if parsed.scheme!='https':url=''
            sql(c,"UPDATE commerce_orders SET state='paid',payment_key=?,receipt_url=?,updated_at=now() WHERE number=?",(p['paymentKey'],url,o['number']))
            audit(c,'provider','payment.paid',o['number'])
        elif o['state'] in ('cancelled','refunded'):
            sql(c,"UPDATE commerce_orders SET state='review',updated_at=now() WHERE number=?",(o['number'],))
    elif status=='CANCELED' and p.get('balanceAmount')==0:
        if o['state'] not in ('cancelled','refunded'):
            # Shipped/returned items require physical review before restocking.
            if o['state'] not in ('shipped','delivered','review'):restore_stock(c,o['number'])
            case=sql(c,'SELECT * FROM commerce_returns WHERE order_number=? FOR UPDATE',(o['number'],)).fetchone()
            if case and case['state']=='reviewed' and case['received']:
                if case['restock'] and o['state'] in ('shipped','delivered'):restore_stock(c,o['number'])
                sql(c,"UPDATE commerce_returns SET state='refunded' WHERE order_number=?",(o['number'],))
            sql(c,"UPDATE commerce_orders SET state='refunded',payment_key=?,updated_at=now() WHERE number=?",(p['paymentKey'],o['number']))
            audit(c,'provider','payment.refunded',o['number'])
    elif status=='PARTIAL_CANCELED':
        sql(c,"UPDATE commerce_orders SET state='review',updated_at=now() WHERE number=?",(o['number'],))

def confirm(number,member_id,payment_key,amount):
    if not readiness()['checkout_enabled']:raise BusinessError('결제 설정이 완료되지 않았습니다.')
    if not isinstance(payment_key,str) or not 1<=len(payment_key)<=200:raise BusinessError('결제 식별값을 확인해 주세요.')
    # Persist attempt before external API: timeout/retry must retain the same payment identity.
    with connect() as c:
        o=sql(c,'SELECT * FROM commerce_orders WHERE number=? AND member_id=? FOR UPDATE',(number,member_id)).fetchone()
        if not o or o['total']!=amount:raise BusinessError('주문 금액을 확인해 주세요.')
        require_mode(o)
        if o['state'] in ('paid','preparing','shipped','delivered'):
            if o['payment_key']!=payment_key:raise BusinessError('이미 처리된 주문입니다.')
            return
        if o['state'] not in ('pending','checking'):raise BusinessError('결제할 수 없는 주문 상태입니다.')
        if o['payment_key'] and o['payment_key']!=payment_key:raise BusinessError('기존 결제 결과부터 확인해 주세요.')
        sql(c,"UPDATE commerce_orders SET state='checking',payment_key=?,updated_at=now() WHERE number=?",(payment_key,number))
    with connect() as c:
        o=sql(c,'SELECT * FROM commerce_orders WHERE number=? FOR UPDATE',(number,)).fetchone()
        if o['state'] not in ('checking','pending'):return
        p=provider('GET','/v1/payments/orders/'+quote(number,safe=''))
        if not p or p.get('status')=='IN_PROGRESS':
            p=provider('POST','/v1/payments/confirm',{'orderId':number,'paymentKey':payment_key,'amount':amount},'confirm-'+number)
        if not valid_payment(o,p) or p.get('paymentKey')!=payment_key:raise ProviderError('결제 결과의 주문 정보가 일치하지 않습니다.')
        sync(c,o,p)
        if p.get('status')!='DONE':raise ProviderError('결제 승인 상태를 확인해 주세요.')

def reconcile(number):
    with connect() as c:
        o=sql(c,'SELECT * FROM commerce_orders WHERE number=? FOR UPDATE',(number,)).fetchone()
        if not o:raise BusinessError('주문이 없습니다.')
        require_mode(o)
        p=provider('GET','/v1/payments/orders/'+quote(number,safe=''))
        if p:sync(c,o,p)
        return bool(p)

def cancel(number,actor,member_id=None,returned=False,restock=False):
    with connect() as c:
        o=sql(c,'SELECT * FROM commerce_orders WHERE number=? FOR UPDATE',(number,)).fetchone()
        if not o or (member_id is not None and o['member_id']!=member_id):raise BusinessError('주문을 확인해 주세요.')
        if o['state'] in ('cancelled','refunded'):
            if returned and o['state']=='refunded':
                case=sql(c,'SELECT * FROM commerce_returns WHERE order_number=? FOR UPDATE',(number,)).fetchone()
                if case and case['state']=='reviewed' and case['received']:
                    if case['restock'] and o['courier'] and o['tracking']:restore_stock(c,number)
                    sql(c,"UPDATE commerce_returns SET state='refunded' WHERE order_number=?",(number,))
                    audit(c,actor,'return.finalized',number)
            return
        if o['state']=='pending' and not o['payment_key']:
            restore_stock(c,number);sql(c,"UPDATE commerce_orders SET state='cancelled',updated_at=now() WHERE number=?",(number,))
        elif o['state'] in ('paid','preparing','checking') or (returned and o['state'] in ('shipped','delivered')):
            require_mode(o)
            if member_id is not None:raise BusinessError('결제 후 취소는 관리자에게 요청해 주세요.')
            p=provider('GET','/v1/payments/orders/'+quote(number,safe=''))
            if not valid_payment(o,p):raise ProviderError('결제 결과 확인 후 다시 처리해 주세요.')
            if p.get('status')=='DONE':
                p=provider('POST','/v1/payments/'+quote(p['paymentKey'],safe='')+'/cancel',{'cancelReason':'소망약국 관리자 전액 취소'},'refund-'+number)
            if not valid_payment(o,p) or p.get('status')!='CANCELED' or p.get('balanceAmount')!=0:raise ProviderError('결제사 전액 취소를 확인하지 못했습니다.')
            sync(c,o,p)
        else:raise BusinessError('배송 또는 검토 중인 주문은 자동 취소할 수 없습니다. 반품 상태를 먼저 확인해 주세요.')
        audit(c,actor,'order.cancel',number)
