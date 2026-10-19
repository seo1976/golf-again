"""Validated product photos stored transactionally in the dedicated commerce DB."""
import hashlib,io,warnings
import somang_commerce_store as store
MAX_UPLOAD=12*1024*1024

def prepare(upload):
    if not upload or not upload.filename:return None
    raw=upload.stream.read(MAX_UPLOAD+1)
    if len(raw)>MAX_UPLOAD:raise store.BusinessError('이미지는 12MB 이하 파일을 선택해 주세요.')
    try:
        from PIL import Image,ImageOps,UnidentifiedImageError
        from pillow_heif import register_heif_opener
    except ImportError:raise store.BusinessError('이미지 등록 기능을 연결 중입니다. 잠시 후 다시 이용해 주세요.')
    register_heif_opener()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ('JPEG','PNG','WEBP','HEIF'):raise ValueError()
                if source.width*source.height>40_000_000:raise ValueError()
                source.draft('RGB',(1600,1600))
                photo=ImageOps.exif_transpose(source)
                photo.thumbnail((1600,1600),Image.Resampling.LANCZOS)
                # Re-encode actual pixels, remove metadata and flatten alpha on white.
                photo=photo.convert('RGBA')
                output=Image.new('RGB',photo.size,'white');output.paste(photo,mask=photo.getchannel('A'))
                buf=io.BytesIO();output.save(buf,'JPEG',quality=85,optimize=True)
        data=buf.getvalue()
    except (OSError,ValueError,SyntaxError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise store.BusinessError('읽을 수 없는 이미지입니다. JPG·PNG·WebP·HEIC 파일을 선택해 주세요.') from None
    return data,hashlib.sha256(data).hexdigest()

def save(c,product_id,photo):
    data,digest=photo
    store.sql(c,'INSERT INTO commerce_product_images(product_id,data,digest) VALUES(?,?,?) ON CONFLICT(product_id) DO UPDATE SET data=excluded.data,digest=excluded.digest',(product_id,data,digest))

def html(product,detail=False):
    from somang_shop import esc
    digest=product.get('image_digest')
    if not digest:return "<div class='product-art' aria-label='상품 사진 없음'>🛍️</div>" if not detail else ''
    return "<img class='product-photo"+(' product-photo-detail' if detail else '')+"' src='/media/products/"+str(product['id'])+'/'+digest+".jpg' alt='"+esc(product['name'])+" 상품 사진' loading='lazy' decoding='async' width='600' height='600'>"

def field():
    return "<label class='product-photo-field'>상품 대표사진<input type='file' name='image' accept='image/*,.heic,.heif' data-product-image><small>사진 촬영·사진 보관함·이미지 파일 선택 · JPG/PNG/WebP/HEIC · 최대 12MB</small><img class='product-upload-preview' alt='선택한 상품 사진 미리보기' hidden><small class='product-preview-note' hidden>이 파일은 저장 후 사진을 확인할 수 있습니다.</small></label>"

PREVIEW_SCRIPT="""<script>
for(const input of document.querySelectorAll('[data-product-image]')){
 let previous;
 input.addEventListener('change',()=>{
  const box=input.closest('label'),img=box.querySelector('img'),note=box.querySelector('.product-preview-note');
  if(previous)URL.revokeObjectURL(previous);img.hidden=true;note.hidden=true;
  input.setCustomValidity('');const file=input.files[0];if(!file)return;
  if(file.size>12*1024*1024){input.setCustomValidity('12MB 이하 이미지를 선택해 주세요.');input.reportValidity();return;}
  input.setCustomValidity('');previous=URL.createObjectURL(file);
  img.onload=()=>{img.hidden=false;note.hidden=true;};img.onerror=()=>{img.hidden=true;note.hidden=false;};img.src=previous;
 });
}
</script>"""
