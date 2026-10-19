"""Actual commerce handlers with isolated SQLite transactions and mocked PG/email edges.
SQLite is test-only. These tests do not claim to test real Toss captures or live email.
"""
import os,re,tempfile,unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from somang_preview import app
import somang_commerce_store as db
import somang_commerce_payments as pay

class CommerceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=dict(app.config)
        app.config.update(TESTING=True,SOMANG_COMMERCE_TEST_DB=self.temp.name+'/commerce.sqlite')
        self.env=patch.dict(os.environ,{'SOMANG_COMMERCE_ENABLED':'1','SOMANG_ADMIN_PASSWORD':'test-admin','SOMANG_SECRET_KEY':'test-secret','SOMANG_PAYMENT_MODE':'test','SOMANG_TOSS_CLIENT_KEY':'test_ck_fake','SOMANG_TOSS_SECRET_KEY':'test_sk_fake','SOMANG_MAIL_API_KEY':'fake','SOMANG_MAIL_FROM':'test@example.com'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.initialize()
        with db.connect() as c:
            for k,v in [('policies_ready','1'),('shipping_fee','3000'),('free_shipping_over','50000')]:db.save_setting(c,k,v)
            for email in ('one@example.com','two@example.com'):
                db.sql(c,"INSERT INTO members(email,password_hash,status,email_verified_at) VALUES(?,?,'active',CURRENT_TIMESTAMP)",(email,generate_password_hash('password12345')))
            db.sql(c,"INSERT INTO commerce_products(name,category,description,price,stock,published,compliance_checked) VALUES('테스트 크림','화장품','가짜 상품',10000,3,1,1)")
        self.client=app.test_client();self.login_as(self.client,1)
    def tearDown(self):
        self.ctx.pop();self.env.stop();app.config.clear();app.config.update(self.old);self.temp.cleanup()
    def login_as(self,client,mid):
        with client.session_transaction() as s:s.update(csrf='token',somang_auth_kind='persistent_member',somang_auth_member_id=mid,somang_auth_version=0)
    def data(self,nonce='abcdefghijklmnopqrst1234'):
        return dict(recipient='가상 수령인',phone='010-0000-0000',postal_code='01234',address='테스트 전용 가상 도로 123',address_detail='가상',consent='yes',request_key=nonce,csrf='token')
    def order(self,nonce='abcdefghijklmnopqrst1234',qty=1):
        return db.create_order(1,{'1':qty},self.data(nonce),nonce)
    def stock(self):
        with db.connect() as c:return db.sql(c,'SELECT stock FROM commerce_products WHERE id=1').fetchone()['stock']
    def state(self,n):return db.order(n)[0]['state']
    def payment(self,n,state='DONE',amount=13000):
        return dict(orderId=n,paymentKey='pg-'+n,totalAmount=amount,currency='KRW',balanceAmount=0 if state=='CANCELED' else amount,status=state,receipt={'url':'https://example.com/receipt'})
    def test_storefront_admin_and_account_pages(self):
        for path in ('/account','/shop','/shop/product/1','/cart','/orders'):
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.client.get('/admin/sales').status_code,403)
        with self.client.session_transaction() as s:s['admin']=True
        for path in ('/admin/sales','/admin/sales/products','/admin/sales/orders','/admin/members','/admin/sales/settings'):
            self.assertEqual(self.client.get(path).status_code,200,path)
    def test_idempotent_order_and_server_total(self):
        n=self.order();self.assertEqual(self.order(),n);self.assertEqual(self.stock(),2)
        self.assertEqual(db.order(n)[0]['total'],13000)
    def test_transaction_rollback_no_overselling(self):
        self.order(qty=3)
        with self.assertRaises(db.BusinessError):self.order('anotherabcdefghijklmnopq',1)
        self.assertEqual(self.stock(),0)
    def test_forged_total_does_not_change_server_amount(self):
        d=self.data();d['total']='1'
        n=db.create_order(1,{'1':2},d,d['request_key']);self.assertEqual(db.order(n)[0]['total'],23000)
    def test_unpublished_and_demo_products_rejected(self):
        with self.assertRaises(db.BusinessError):db.create_order(1,{'900001':1},self.data(),self.data()['request_key'])
        with db.connect() as c:db.sql(c,'UPDATE commerce_products SET compliance_checked=0 WHERE id=1')
        with self.assertRaises(db.BusinessError):self.order()
    def test_owner_access_and_fake_demo_session(self):
        n=self.order();other=app.test_client();self.login_as(other,2)
        self.assertEqual(other.get('/orders/'+n).status_code,404)
        self.assertEqual(other.post('/orders/'+n+'/cancel',data={'csrf':'token','confirm':'yes'}).status_code,409)
        guest=app.test_client()
        with guest.session_transaction() as s:s.update(member_id=1,demo_member=True,csrf='token')
        self.assertEqual(guest.get('/orders').status_code,401)
    def test_csrf_and_amount_tamper(self):
        self.assertEqual(self.client.post('/cart/add',data={'product_id':1}).status_code,400)
        n=self.order()
        with patch.object(pay,'provider') as pg:
            with self.assertRaises(db.BusinessError):pay.confirm(n,1,'fake',1)
            pg.assert_not_called()
        self.assertEqual(self.state(n),'pending')
    def test_payment_confirmation_and_duplicate_callback(self):
        n=self.order();p=self.payment(n)
        with patch.object(pay,'provider',return_value=p) as pg:
            pay.confirm(n,1,p['paymentKey'],13000);pay.confirm(n,1,p['paymentKey'],13000)
            self.assertEqual(pg.call_count,1)
        self.assertEqual(self.state(n),'paid');self.assertEqual(self.stock(),2)
    def test_approval_endpoint_calls_provider(self):
        n=self.order();p=self.payment(n)
        with patch.object(pay,'provider',side_effect=[None,p]) as pg:
            pay.confirm(n,1,p['paymentKey'],13000)
            self.assertEqual(pg.call_args.args[:2],('POST','/v1/payments/confirm'))
        self.assertEqual(self.state(n),'paid')
    def test_timeout_retains_attempt_and_does_not_release_stock(self):
        n=self.order()
        with patch.object(pay,'provider',side_effect=pay.ProviderError('timeout')):
            with self.assertRaises(pay.ProviderError):pay.confirm(n,1,'pg-'+n,13000)
        self.assertEqual(self.state(n),'checking');self.assertEqual(self.stock(),2)
        with self.assertRaises(db.BusinessError):pay.confirm(n,1,'different-key',13000)
        with patch.object(pay,'provider',return_value=self.payment(n)):
            pay.confirm(n,1,'pg-'+n,13000)
        self.assertEqual(self.state(n),'paid')
    def test_mismatched_provider_total_never_marks_paid(self):
        n=self.order()
        with patch.object(pay,'provider',return_value=self.payment(n,amount=1)):
            with self.assertRaises(pay.ProviderError):pay.confirm(n,1,'pg-'+n,13000)
        self.assertEqual(self.state(n),'checking')
    def test_pending_cancel_and_refund_are_idempotent(self):
        n=self.order();pay.cancel(n,'member',1);pay.cancel(n,'member',1)
        self.assertEqual(self.stock(),3);self.assertEqual(self.state(n),'cancelled')
        n=self.order('differentabcdefghijklmno')
        with patch.object(pay,'provider',return_value=self.payment(n)):pay.confirm(n,1,'pg-'+n,13000)
        with patch.object(pay,'provider',side_effect=[self.payment(n),self.payment(n,'CANCELED')]):pay.cancel(n,'admin')
        pay.cancel(n,'admin');self.assertEqual(self.state(n),'refunded');self.assertEqual(self.stock(),3)
    def test_failed_refund_leaves_payment_and_stock_unchanged(self):
        n=self.order()
        with patch.object(pay,'provider',return_value=self.payment(n)):pay.confirm(n,1,'pg-'+n,13000)
        with patch.object(pay,'provider',side_effect=pay.ProviderError('error')):
            with self.assertRaises(pay.ProviderError):pay.cancel(n,'admin')
        self.assertEqual(self.state(n),'paid');self.assertEqual(self.stock(),2)
    def test_suspend_invalidates_existing_login(self):
        admin=app.test_client()
        with admin.session_transaction() as s:s.update(admin=True,csrf='token')
        self.assertEqual(admin.post('/admin/members/1/suspend',data={'csrf':'token'}).status_code,302)
        self.assertEqual(self.client.get('/orders').status_code,401)
        self.assertEqual(admin.post('/admin/members/1/restore',data={'csrf':'token'}).status_code,302)
        self.assertEqual(self.client.get('/orders').status_code,401)
    def test_test_order_cannot_ship(self):
        n=self.order()
        with patch.object(pay,'provider',return_value=self.payment(n)):pay.confirm(n,1,'pg-'+n,13000)
        with self.client.session_transaction() as s:s['admin']=True
        self.assertEqual(self.client.post('/admin/sales/orders/'+n+'/shipping',data={'csrf':'token','state':'preparing'}).status_code,409)
    def test_webhook_uses_provider_not_claimed_status(self):
        n=self.order()
        with patch.object(pay,'provider',return_value=self.payment(n)):pay.confirm(n,1,'pg-'+n,13000)
        with patch.object(pay,'provider',return_value=self.payment(n)):
            r=self.client.post('/payments/webhook',json={'data':{'orderId':n,'paymentKey':'pg-'+n,'status':'CANCELED'}})
        self.assertEqual(r.status_code,200);self.assertEqual(self.state(n),'paid')
    def test_real_login_pending_account_cannot_order(self):
        self.assertEqual(self.client.post('/login',data={'csrf':'token','email':'one@example.com','password':'wrong'}).status_code,403)
        self.assertEqual(self.client.post('/login',data={'csrf':'token','email':'one@example.com','password':'password12345'}).status_code,302)
        with db.connect() as c:db.sql(c,"UPDATE members SET status='pending',email_verified_at=NULL WHERE id=1")
        with self.client.session_transaction() as s:s['csrf']='token'
        self.assertEqual(self.client.post('/login',data={'csrf':'token','email':'one@example.com','password':'password12345'}).status_code,302)
        self.assertEqual(self.client.get('/orders').status_code,401)
        self.assertIn('회원가입이 완료되었습니다.',self.client.get('/account').get_data(as_text=True))
    def test_signup_without_mail_or_sales_policy(self):
        guest=app.test_client()
        with guest.session_transaction() as s:s['csrf']='token'
        with db.connect() as c:db.save_setting(c,'policies_ready','0')
        with patch.dict(os.environ,{'SOMANG_MAIL_API_KEY':'','SOMANG_MAIL_FROM':''}), patch('somang_member_mail.send_account_email') as mail:
            self.assertIn("name='password_confirm'",guest.get('/account').get_data(as_text=True))
            data={'csrf':'token','email':'new@example.com','password':'newpassword1234','password_confirm':'newpassword1234','consent':'yes'}
            self.assertEqual(guest.post('/register',data=data).status_code,200)
            mail.assert_not_called()
            with db.connect() as c:
                r=db.sql(c,"SELECT * FROM members WHERE email='new@example.com'").fetchone()
                self.assertEqual(r['status'],'pending');self.assertIsNone(r['email_verified_at'])
                self.assertNotEqual(r['password_hash'],data['password'])
                self.assertEqual(db.sql(c,'SELECT count(*) n FROM commerce_consents WHERE member_id=?',(r['id'],)).fetchone()['n'],1)
            self.assertEqual(guest.post('/login',data=data).status_code,302)
            self.assertIn('회원가입이 완료되었습니다.',guest.get('/account').get_data(as_text=True))
            self.assertEqual(guest.get('/orders').status_code,401)
            with self.assertRaises(db.BusinessError):db.create_order(r['id'],{'1':1},self.data(),self.data()['request_key'])
            with guest.session_transaction() as s:token=s['csrf']
            self.assertEqual(guest.post('/members/delete',data={'csrf':token,'password':data['password']}).status_code,200)
    def test_signup_confirmation_and_duplicate_preserve_password(self):
        data={'csrf':'token','email':'one@example.com','password':'differentpassword123','password_confirm':'mismatch','consent':'yes'}
        self.assertEqual(self.client.post('/register',data=data).status_code,409)
        data['password_confirm']=data['password']
        self.assertEqual(self.client.post('/register',data=data).status_code,200)
        self.assertEqual(self.client.post('/login',data=data).status_code,403)
        data['password']='password12345'
        self.assertEqual(self.client.post('/login',data=data).status_code,302)
    def test_signup_mail_failure_keeps_account_and_consent(self):
        data={'csrf':'token','email':'new@example.com','password':'newpassword1234','password_confirm':'newpassword1234','consent':'yes'}
        with patch('somang_member_mail.send_account_email',side_effect=RuntimeError('offline')):
            self.assertEqual(self.client.post('/register',data=data).status_code,200)
        self.assertEqual(self.client.post('/login',data=data).status_code,302)
        self.assertEqual(self.client.get('/orders').status_code,401)
    def test_registration_verify_and_one_time_token(self):
        with patch('somang_member_mail.send_account_email') as mail:
            r=self.client.post('/register',data={'csrf':'token','email':'new@example.com','password':'newpassword1234','password_confirm':'newpassword1234','consent':'yes'})
            self.assertEqual(r.status_code,200)
            raw=mail.call_args.args[1]
        with db.connect() as c:r=db.sql(c,"SELECT * FROM members WHERE email='new@example.com'").fetchone();self.assertEqual(r['status'],'pending')
        r=self.client.post('/members/verify',data={'csrf':'token','token':raw});self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.post('/members/verify',data={'csrf':'token','token':raw}).status_code,409)
    def test_checkout_and_browser_order_flow(self):
        self.client.post('/cart/add',data={'csrf':'token','product_id':1,'quantity':1})
        r=self.client.get('/checkout');self.assertEqual(r.status_code,200)
        with self.client.session_transaction() as s:nonce=s['commerce_order_nonce']
        r=self.client.post('/orders',data=self.data(nonce));self.assertEqual(r.status_code,302)
        self.assertEqual(self.client.get(r.location).status_code,200)
    def test_payment_mode_cannot_cross_test_live(self):
        n=self.order()
        with patch.dict(os.environ,{'SOMANG_PAYMENT_MODE':'live','SOMANG_TOSS_CLIENT_KEY':'live_ck_fake','SOMANG_TOSS_SECRET_KEY':'live_sk_fake','SOMANG_LIVE_APPROVED':'1'}):
            with self.assertRaises(db.BusinessError):pay.confirm(n,1,'pg-'+n,13000)
    def test_member_and_order_responses_not_cached(self):
        self.assertEqual(self.client.get('/account').headers['Cache-Control'],'no-store')
    def test_database_backend_not_available_outside_testing(self):
        app.config['TESTING']=False
        with self.assertRaises(RuntimeError):
            with db.connect():pass
        app.config['TESTING']=True
    def test_concurrent_inventory_reservation(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(n):
            with app.app_context():
                try:return self.order('parallel-request-key-'+str(n),3)
                except db.BusinessError:return None
        with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(attempt,range(4)))
        self.assertEqual(sum(x is not None for x in result),1);self.assertEqual(self.stock(),0)
    def test_return_refund_restocks_once_after_receipt(self):
        n=self.order()
        with patch.object(pay,'provider',return_value=self.payment(n)):pay.confirm(n,1,'pg-'+n,13000)
        with db.connect() as c:
            db.sql(c,"UPDATE commerce_orders SET state='delivered',courier='가상택배',tracking='12345678' WHERE number=?",(n,))
        r=self.client.post('/orders/'+n+'/return',data={'csrf':'token','reason':'테스트 반품'});self.assertEqual(r.status_code,200)
        with self.client.session_transaction() as s:s['admin']=True
        with patch.object(pay,'provider',side_effect=[self.payment(n),self.payment(n,'CANCELED')]):
            r=self.client.post('/admin/sales/orders/'+n+'/return',data={'csrf':'token','received':'yes','restock':'yes'})
        self.assertEqual(r.status_code,302);self.assertEqual(self.stock(),3);self.assertEqual(self.state(n),'refunded')
        self.client.post('/admin/sales/orders/'+n+'/return',data={'csrf':'token','received':'yes','restock':'yes'})
        self.assertEqual(self.stock(),3)
    def test_reset_password_invalidates_session(self):
        with patch('somang_member_mail.send_account_email') as mail:
            self.client.post('/members/reset/request',data={'csrf':'token','email':'one@example.com'})
            raw=mail.call_args.args[1]
        self.assertEqual(self.client.post('/members/reset',data={'csrf':'token','token':raw,'password':'new-password12345'}).status_code,200)
        self.assertEqual(self.client.get('/orders').status_code,401)
        self.assertEqual(self.client.post('/members/reset',data={'csrf':'token','token':raw,'password':'new-password12345'}).status_code,409)
    def test_new_product_is_hidden_until_compliance_review(self):
        with self.client.session_transaction() as s:s['admin']=True
        r=self.client.post('/admin/sales/products',data={'csrf':'token','name':'실판매 테스트','category':'화장품','price':12000,'stock':5,'description':'상세'})
        self.assertEqual(r.status_code,302)
        self.assertNotIn('실판매 테스트'.encode(),self.client.get('/shop').data)
        r=self.client.post('/admin/sales/products/2',data={'csrf':'token','price':12000,'stock_delta':0,'published':1})
        self.assertEqual(r.status_code,409)
        r=self.client.post('/admin/sales/products/2',data={'csrf':'token','price':12000,'stock_delta':0,'published':1,'compliance_checked':1})
        self.assertEqual(r.status_code,302)
        self.assertIn('실판매 테스트'.encode(),self.client.get('/shop').data)
    def test_missing_payment_keys_block_order_creation(self):
        with patch.dict(os.environ,{'SOMANG_TOSS_SECRET_KEY':''}):
            self.assertFalse(pay.readiness()['checkout_enabled'])
            with self.client.session_transaction() as s:s['cart']={'1':1}
            self.assertEqual(self.client.get('/checkout').status_code,503)
    def test_admin_cannot_ship_unpaid_order(self):
        n=self.order()
        with self.client.session_transaction() as s:s['admin']=True
        with db.connect() as c:db.sql(c,"UPDATE commerce_orders SET mode='live' WHERE number=?",(n,))
        self.assertEqual(self.client.post('/admin/sales/orders/'+n+'/shipping',data={'csrf':'token','state':'shipped','courier':'택배','tracking':'12345678'}).status_code,409)
