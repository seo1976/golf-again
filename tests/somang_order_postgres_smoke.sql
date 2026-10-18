-- Runs ONLY in a disposable CI PostgreSQL database with synthetic values.
-- Never execute this smoke test against production.
BEGIN;
INSERT INTO members (email,password_hash,status)
VALUES ('ci-fake-member@example.invalid','fake-hash-not-a-password','pending');
INSERT INTO somang_shipping_addresses
 (member_id,recipient_name,recipient_phone,postal_code,address_line1,is_default)
SELECT id,'가상 수령인','000-0000-0000','00000','테스트용 가상 주소',TRUE
FROM members WHERE email='ci-fake-member@example.invalid';
INSERT INTO somang_orders
 (order_number,member_id,customer_name,customer_phone,recipient_name,recipient_phone,
  postal_code,address_line1,merchandise_total_krw,shipping_fee_krw,payable_total_krw)
SELECT 'CI-FAKE-ORDER-001',id,'가상 주문자','000-0000-0000','가상 수령인','000-0000-0000',
       '00000','테스트용 가상 주소',37800,3000,40800
FROM members WHERE email='ci-fake-member@example.invalid';
INSERT INTO somang_order_items
 (order_id,product_id,product_name,unit_price_krw,quantity,line_total_krw)
SELECT id,1,'가상 크림',18900,2,37800
FROM somang_orders WHERE order_number='CI-FAKE-ORDER-001';
DO $$
BEGIN
 IF (SELECT COUNT(*) FROM somang_order_items i JOIN somang_orders o ON o.id=i.order_id
     WHERE o.order_number='CI-FAKE-ORDER-001' AND o.payable_total_krw=40800 AND i.quantity=2) <> 1 THEN
   RAISE EXCEPTION 'Fake order save/read smoke test failed';
 END IF;
END $$;
UPDATE somang_orders SET order_status='cancelled'
WHERE order_number='CI-FAKE-ORDER-001' AND order_status='pending';
DO $$
BEGIN
 IF (SELECT order_status FROM somang_orders WHERE order_number='CI-FAKE-ORDER-001') <> 'cancelled' THEN
   RAISE EXCEPTION 'Fake order cancel smoke test failed';
 END IF;
END $$;
-- No synthetic order persists after this test.
ROLLBACK;
