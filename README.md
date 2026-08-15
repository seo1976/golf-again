# GOLF AGAIN 운영형 MVP

실제로 동작하는 중고 골프용품 거래 웹앱입니다.

## 포함 기능
- 회원가입 / 로그인 / 로그아웃
- 상품 사진 업로드
- 골프 전문 상품정보 등록 (카테고리/브랜드/샤프트/Flex/상태/지역/거래방법)
- 상품 검색 / 카테고리 필터
- 찜하기 / 찜 취소
- 내 상품 목록
- 판매중 ↔ 판매완료 전환
- 상품 삭제
- SQLite DB 자동 생성
- 모바일 반응형 화면

## 로컬 실행
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
브라우저에서 http://localhost:5000 접속.

## 운영 배포 전 필수
1. `SECRET_KEY` 환경변수 설정
2. SQLite 대신 PostgreSQL 등 관리형 DB 권장
3. 이미지 저장을 S3/Cloudinary 같은 외부 스토리지로 변경
4. HTTPS 도메인 연결
5. 개인정보처리방침/이용약관/전자상거래 관련 고지 준비
6. 안전결제 도입 시 PG사 연동 및 사업자/정산 구조 검토

## 배포
Dockerfile과 Procfile이 포함되어 있어 일반적인 Python 호스팅 서비스에 배포할 수 있습니다.
