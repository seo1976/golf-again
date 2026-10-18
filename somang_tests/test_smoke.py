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
if __name__=="__main__":unittest.main()
