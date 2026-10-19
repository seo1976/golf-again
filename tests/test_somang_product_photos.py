import io,unittest
from unittest.mock import patch
from PIL import Image
from pillow_heif import register_heif_opener
from somang_preview import app
import somang_commerce_store as db
import test_somang_commerce as fixtures

class ProductPhotoTests(unittest.TestCase):
    login_as=fixtures.CommerceTests.login_as
    tearDown=fixtures.CommerceTests.tearDown
    def setUp(self):
        fixtures.CommerceTests.setUp(self)
        with self.client.session_transaction() as s:s['admin']=True
    def picture(self,fmt='PNG',color='red',size=(40,30)):
        buf=io.BytesIO();Image.new('RGB',size,color).save(buf,fmt);return buf.getvalue()
    def edit(self,pid=1,image=None,**changes):
        data=dict(csrf='token',price='10000',stock_delta='0',published='1',compliance_checked='1',description='사진 테스트')
        data.update(changes)
        if image is not None:data['image']=(io.BytesIO(image),'photo.jpg')
        return self.client.post('/admin/sales/products/'+str(pid),data=data,content_type='multipart/form-data')
    def image_url(self,pid=1):
        p=next(x for x in db.products(True) if x['id']==pid)
        return '/media/products/'+str(pid)+'/'+p['image_digest']+'.jpg'
    def test_upload_form_and_persistent_create(self):
        html=self.client.get('/admin/sales/products').get_data(as_text=True)
        self.assertIn("enctype='multipart/form-data'",html);self.assertIn("type='file'",html)
        r=self.client.post('/admin/sales/products',data={'csrf':'token','name':'사진 상품','category':'화장품','price':10000,'stock':2,'image':(io.BytesIO(self.picture()),'product.png')},content_type='multipart/form-data')
        self.assertEqual(r.status_code,302)
        url=self.image_url(2)
        guest=app.test_client();self.assertEqual(guest.get(url).status_code,404)
        r=self.client.get(url);self.assertEqual(r.status_code,200);self.assertEqual(r.mimetype,'image/jpeg');r.close()
        other=app.test_client()
        with other.session_transaction() as s:s['admin']=True
        self.assertEqual(other.get(url).status_code,200)
    def test_public_catalog_detail_and_etag(self):
        self.assertEqual(self.edit(image=self.picture()).status_code,302)
        url=self.image_url();guest=app.test_client()
        self.assertIn(url,guest.get('/shop').get_data(as_text=True));self.assertIn(url,guest.get('/shop/product/1').get_data(as_text=True))
        r=guest.get(url);self.assertEqual(r.status_code,200)
        self.assertEqual(guest.get(url,headers={'If-None-Match':r.headers['ETag']}).status_code,304)
        self.edit(published='0');self.assertEqual(guest.get(url).status_code,404)
    def test_replace_keep_and_remove(self):
        self.edit(image=self.picture());first=self.image_url()
        self.edit(price='12000');self.assertEqual(self.image_url(),first)
        self.edit(image=self.picture(color='blue'));second=self.image_url()
        self.assertNotEqual(first,second);self.assertEqual(self.client.get(first).status_code,404)
        self.edit(remove_image='yes');self.assertEqual(self.client.get(second).status_code,404)
    def test_invalid_image_rolls_back_product_stock_and_image(self):
        self.edit(image=self.picture());url=self.image_url()
        r=self.edit(image=b'<svg onload="alert(1)"></svg>',stock_delta='5',price='9000')
        self.assertEqual(r.status_code,409);self.assertEqual(self.image_url(),url)
        p=db.products(True)[0];self.assertEqual(p['stock'],3);self.assertEqual(p['price'],10000)
    def test_oversized_file_and_request(self):
        self.assertEqual(self.edit(image=b'x'*(12*1024*1024+1)).status_code,409)
        self.assertEqual(self.edit(image=b'x'*(13*1024*1024+1)).status_code,413)
    def test_upload_authorization_and_csrf_precede_processing(self):
        with patch('somang_product_images.prepare') as prepare:
            guest=app.test_client();self.assertEqual(guest.post('/admin/sales/products/1',data={}).status_code,403)
            self.assertEqual(self.edit(image=self.picture(),csrf='wrong').status_code,400);prepare.assert_not_called()
    def test_resize_and_strip_exif(self):
        buf=io.BytesIO();im=Image.new('RGB',(2400,1800),'white');exif=Image.Exif();exif[270]='private metadata';im.save(buf,'JPEG',exif=exif)
        self.assertEqual(self.edit(image=buf.getvalue()).status_code,302)
        r=self.client.get(self.image_url());img=Image.open(io.BytesIO(r.data))
        self.assertLessEqual(max(img.size),1600);self.assertFalse(img.getexif());self.assertNotIn(b'private metadata',r.data)
    def test_webp_and_iphone_heic(self):
        register_heif_opener()
        for fmt in ('WEBP','HEIF'):
            self.assertEqual(self.edit(image=self.picture(fmt)).status_code,302,fmt)
            r=self.client.get(self.image_url());self.assertEqual(r.mimetype,'image/jpeg')
