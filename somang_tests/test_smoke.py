"""Automated smoke tests for Somang Pharmacy preview.
Run: python -m unittest discover -s somang_tests -v
"""
import os, unittest, tempfile
class SomangSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        os.environ["SOMANG_DB_PATH"]=os.path.join(cls.temp.name,"test.sqlite3")
        os.environ.pop("SOMANG_ADMIN_PASSWORD",None)
        os.environ.pop("SOMANG_ENABLE_DEMO_REGISTRATION",None)
        import somang_preview
        cls.client=somang_preview.app.test_client()
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_health(self):
        r=self.client.get("/health")
        self.assertEqual(r.status_code,200)
        self.assertFalse(r.json["payments_enabled"])
    def test_storefront(self):
        self.assertEqual(self.client.get("/shop").status_code,200)
        self.assertEqual(self.client.get("/cart").status_code,200)
        self.assertEqual(self.client.get("/checkout").status_code,302)
    def test_demo_member_cart_and_checkout_flow(self):
        client=__import__("somang_preview").app.test_client()
        with client.session_transaction() as sess:
            sess["csrf"]="demo-test-token"
        self.assertEqual(client.get("/account").status_code,200)
        self.assertEqual(client.post("/demo/login",data={"csrf":"wrong"}).status_code,400)
        self.assertEqual(client.post("/demo/login",data={"csrf":"demo-test-token"}).status_code,302)
        self.assertIn("체험 회원으로 로그인 중".encode("utf-8"),client.get("/account").data)
        self.assertEqual(client.post("/cart/add",data={"csrf":"demo-test-token","product_id":900001,"quantity":2}).status_code,302)
        self.assertIn("37,800원".encode("utf-8"),client.get("/cart").data)
        self.assertEqual(client.post("/cart/update",data={"csrf":"demo-test-token","product_id":900001,"quantity":1}).status_code,302)
        self.assertIn("18,900원".encode("utf-8"),client.get("/checkout").data)
        self.assertIn("결제하기 (준비 중)".encode("utf-8"),client.get("/checkout").data)
        self.assertEqual(client.post("/demo/logout",data={"csrf":"demo-test-token"}).status_code,302)
        self.assertIn("회원 로그인 체험".encode("utf-8"),client.get("/account").data)
        self.assertIn("18,900원".encode("utf-8"),client.get("/cart").data)
    def test_payment_blocked(self):
        self.assertEqual(self.client.post("/payments/start").status_code,503)
        r=self.client.get("/payments/readiness")
        self.assertFalse(r.json["checkout_enabled"])
    def test_registration_disabled(self):
        r=self.client.get("/account")
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.post("/register").status_code,503)
    def test_admin_protected(self):
        self.assertEqual(self.client.get("/admin/ops").status_code,403)
        self.assertEqual(self.client.get("/admin/reports/summary").status_code,403)
    def test_prelaunch(self):
        r=self.client.get("/launch/checklist")
        self.assertEqual(r.status_code,200)
        self.assertFalse(r.json["ready_for_sales"])
    def test_no_medicine_catalog(self):
        with __import__("somang_preview").db() as c:
            c.execute("INSERT INTO products(name,category,price,stock,approved,visible) VALUES(?,?,?,?,?,?)",("TEST MEDICINE","일반의약품",100,3,0,0))
        self.assertNotIn(b"TEST MEDICINE",self.client.get("/shop").data)
    def test_inventory_adjustment_and_audit(self):
        import somang_preview
        os.environ["SOMANG_ADMIN_PASSWORD"]="unit-test-only-password"
        os.environ["SOMANG_SECRET_KEY"]="unit-test-only-secret"
        try:
            with somang_preview.db() as c:
                cur=c.execute("INSERT INTO products(name,category,price,stock,approved,visible) VALUES(?,?,?,?,?,?)",("Inventory Test","화장품",1000,5,0,0))
                pid=cur.lastrowid
            with self.client.session_transaction() as sess:
                sess["admin"]=True
                sess["csrf"]="test-token"
            r=self.client.post("/admin/ops/stock/adjust",data={"csrf":"test-token","product_id":pid,"change_qty":3,"reason":"test inbound"})
            self.assertEqual(r.status_code,302)
            with somang_preview.db() as c:
                self.assertEqual(c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()[0],8)
                self.assertEqual(c.execute("SELECT change_qty FROM stock_movements WHERE product_id=?",(pid,)).fetchone()[0],3)
            r=self.client.post(f"/admin/products/{pid}/stock",data={"csrf":"test-token","stock":2})
            self.assertEqual(r.status_code,302)
            with somang_preview.db() as c:
                self.assertEqual(c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()[0],2)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM stock_movements WHERE product_id=?",(pid,)).fetchone()[0],2)
            r=self.client.post("/admin/ops/stock/adjust",data={"csrf":"test-token","product_id":pid,"change_qty":-100,"reason":"invalid"})
            self.assertEqual(r.status_code,400)
        finally:
            os.environ.pop("SOMANG_ADMIN_PASSWORD",None)
            os.environ.pop("SOMANG_SECRET_KEY",None)
    def test_purchase_receipt_once(self):
        import somang_preview
        os.environ["SOMANG_ADMIN_PASSWORD"]="unit-test-only-password"
        os.environ["SOMANG_SECRET_KEY"]="unit-test-only-secret"
        try:
            with somang_preview.db() as c:
                pid=c.execute("INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)",("Receiving Test","화장품",1000,1)).lastrowid
                sid=c.execute("INSERT INTO suppliers(name) VALUES(?)",("Test Supplier",)).lastrowid
                oid=c.execute("INSERT INTO purchase_orders(supplier_id,reference,total) VALUES(?,?,?)",(sid,"TEST-PO",4000)).lastrowid
            with self.client.session_transaction() as sess:
                sess["admin"]=True
                sess["csrf"]="test-token"
            data={"csrf":"test-token","order_id":oid,"product_id":pid,"quantity":4}
            self.assertEqual(self.client.post("/admin/ops/purchase/receive",data=data).status_code,302)
            self.assertEqual(self.client.post("/admin/ops/purchase/receive",data=data).status_code,409)
            with somang_preview.db() as c:
                self.assertEqual(c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()[0],5)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM ledger WHERE reference=?",(f"PO-{oid}",)).fetchone()[0],1)
        finally:
            os.environ.pop("SOMANG_ADMIN_PASSWORD",None)
            os.environ.pop("SOMANG_SECRET_KEY",None)
    def test_lot_receipt_and_validation(self):
        import somang_preview
        os.environ["SOMANG_ADMIN_PASSWORD"]="unit-test-only-password"
        os.environ["SOMANG_SECRET_KEY"]="unit-test-only-secret"
        try:
            with somang_preview.db() as c:
                pid=c.execute("INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)",("Lot Test","화장품",1000,0)).lastrowid
            with self.client.session_transaction() as sess:
                sess["admin"]=True
                sess["csrf"]="test-token"
            data={"csrf":"test-token","product_id":pid,"quantity":5,"lot_code":"L2026A","expiry_date":"2027-12-31"}
            self.assertEqual(self.client.post("/admin/ops/lots/receive",data=data).status_code,302)
            self.assertEqual(self.client.post("/admin/ops/lots/receive",data={**data,"expiry_date":"bad-date"}).status_code,400)
            with somang_preview.db() as c:
                self.assertEqual(c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()[0],5)
                self.assertEqual(c.execute("SELECT quantity FROM inventory_lots WHERE product_id=?",(pid,)).fetchone()[0],5)
        finally:
            os.environ.pop("SOMANG_ADMIN_PASSWORD",None)
            os.environ.pop("SOMANG_SECRET_KEY",None)
    def test_lot_expiry_dashboard(self):
        os.environ["SOMANG_ADMIN_PASSWORD"]="unit-test-only-password"
        os.environ["SOMANG_SECRET_KEY"]="unit-test-only-secret"
        try:
            with self.client.session_transaction() as sess:
                sess["admin"]=True
            r=self.client.get("/admin/ops/lots")
            self.assertEqual(r.status_code,200)
            self.assertIn("30일 이내".encode("utf-8"),r.data)
        finally:
            os.environ.pop("SOMANG_ADMIN_PASSWORD",None)
            os.environ.pop("SOMANG_SECRET_KEY",None)
    def test_lot_dispatch_expiry_guard(self):
        import somang_preview
        os.environ["SOMANG_ADMIN_PASSWORD"]="unit-test-only-password"
        os.environ["SOMANG_SECRET_KEY"]="unit-test-only-secret"
        try:
            with somang_preview.db() as c:
                pid=c.execute("INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)",("Dispatch Test","화장품",1000,8)).lastrowid
                lid=c.execute("INSERT INTO inventory_lots(product_id,lot_code,expiry_date,quantity) VALUES(?,?,?,?)",(pid,"VALID","2099-01-01",5)).lastrowid
                expired=c.execute("INSERT INTO inventory_lots(product_id,lot_code,expiry_date,quantity) VALUES(?,?,?,?)",(pid,"EXPIRED","2020-01-01",3)).lastrowid
            with self.client.session_transaction() as sess:
                sess["admin"]=True
                sess["csrf"]="test-token"
            self.assertEqual(self.client.post("/admin/ops/lots/dispatch",data={"csrf":"test-token","lot_id":expired,"quantity":1}).status_code,409)
            self.assertEqual(self.client.post("/admin/ops/lots/dispatch",data={"csrf":"test-token","lot_id":lid,"quantity":2}).status_code,302)
            with somang_preview.db() as c:
                self.assertEqual(c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()[0],6)
                self.assertEqual(c.execute("SELECT quantity FROM inventory_lots WHERE id=?",(lid,)).fetchone()[0],3)
        finally:
            os.environ.pop("SOMANG_ADMIN_PASSWORD",None)
            os.environ.pop("SOMANG_SECRET_KEY",None)
    def test_lot_disposal_audit(self):
        import somang_preview
        os.environ["SOMANG_ADMIN_PASSWORD"]="unit-test-only-password"
        os.environ["SOMANG_SECRET_KEY"]="unit-test-only-secret"
        try:
            with somang_preview.db() as c:
                pid=c.execute("INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)",("Disposal Test","화장품",1000,4)).lastrowid
                lid=c.execute("INSERT INTO inventory_lots(product_id,lot_code,expiry_date,quantity) VALUES(?,?,?,?)",(pid,"DISP","2020-01-01",4)).lastrowid
            with self.client.session_transaction() as sess:
                sess["admin"]=True
                sess["csrf"]="test-token"
            data={"csrf":"test-token","lot_id":lid,"quantity":2,"reason":"expired"}
            self.assertEqual(self.client.post("/admin/ops/lots/dispose",data=data).status_code,302)
            self.assertEqual(self.client.post("/admin/ops/lots/dispose",data={**data,"quantity":5}).status_code,409)
            with somang_preview.db() as c:
                self.assertEqual(c.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()[0],2)
                self.assertEqual(c.execute("SELECT quantity FROM inventory_lots WHERE id=?",(lid,)).fetchone()[0],2)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM inventory_disposals WHERE lot_id=?",(lid,)).fetchone()[0],1)
        finally:
            os.environ.pop("SOMANG_ADMIN_PASSWORD",None)
            os.environ.pop("SOMANG_SECRET_KEY",None)
if __name__=="__main__":unittest.main()
