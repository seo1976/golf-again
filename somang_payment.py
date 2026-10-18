"""Payment integration readiness checks, with live checkout explicitly disabled.
Do not accept payment, PII, or order submission from this preview.
"""
import os
from flask import Blueprint, jsonify, session, abort
payment=Blueprint("somang_payment",__name__,url_prefix="/payments")
@payment.get("/readiness")
def readiness():
    return jsonify(
        payment_provider="tosspayments",
        checkout_enabled=False,
        payment_capture_enabled=False,
        refunds_enabled=False,
        live_keys_configured=False,
        checklist={
            "pharmacy_seller_authorization":"pending",
            "online_sale_eligibility_by_product":"pending",
            "merchant_agreement":"pending",
            "privacy_terms_shipping_refund_policies":"pending",
            "persistent_database_and_backup":"pending",
            "server_side_amount_and_stock_validation":"pending",
            "idempotent_payment_confirm_webhook_and_refund":"pending",
            "staging_integration_test":"pending"
        },
        message="PG 신규 계약과 운영 요건 검증 전 실제 결제 요청은 생성하지 않습니다."
    )
@payment.route("/start",methods=["GET","POST"])
def blocked_payment():
    abort(503,"실제 결제는 현재 비활성화 상태입니다.")
