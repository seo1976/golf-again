"""Prelaunch controls for Somang Pharmacy.
These endpoints intentionally do not accept payment or actual customer orders.
"""
import os
from flask import Blueprint, jsonify, session, abort
launch=Blueprint("somang_launch",__name__,url_prefix="/launch")
STEPS=[
("seller_permission","대표약사 승인 및 사업자·통신판매 관련 자격 확인"),
("product_compliance","판매 품목별 온라인 판매 적법성 및 표시·광고 확인"),
("pg_agreement","소망약국 명의 토스페이먼츠 계약·심사"),
("persistent_database","영구 데이터베이스, 접근권한, 백업 및 복구 테스트"),
("privacy","개인정보처리방침·보유기간·파기·위탁처리 계약 검토"),
("shipping","배송비·배송지역·반품지·교환·환불 정책 확정"),
("order_lifecycle","주문번호·재고예약·중복주문 방지·취소 상태 검증"),
("payment_integration","서버 측 금액검증·승인·멱등성·웹훅·취소·정산대사"),
("security","관리자 권한·CSRF·세션·감사로그·취약점 점검"),
("end_to_end_test","회원/비회원·품절·결제실패·환불 통합테스트"),
]
@launch.get("/checklist")
def checklist():
    return jsonify(ready_for_sales=False,checkout_enabled=False,items=[{"id":key,"requirement":label,"status":"not_verified"} for key,label in STEPS],note="설정값 존재만으로 실제 판매 가능 여부를 판단하지 않습니다.")
@launch.get("/settings")
def settings():
    if not session.get("admin"):abort(403)
    return jsonify(
        payment_provider="tosspayments",
        mode="disabled",
        merchant_keys_in_source_code=False,
        admin_secret_configured=bool(os.environ.get("SOMANG_SECRET_KEY")),
        admin_password_configured=bool(os.environ.get("SOMANG_ADMIN_PASSWORD")),
        persistent_db_configured=bool(os.environ.get("SOMANG_DATABASE_URL")),
        customer_data_allowed=False,
        actual_order_acceptance_allowed=False,
        note="PG 라이브키는 나중에 서버 비밀 환경변수로 설정. 이 화면은 키 값을 반환하지 않습니다."
    )
