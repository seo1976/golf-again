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
-- Verify the draft schema removes saved address PII on hard member deletion.
-- A separate synthetic member avoids order-item retention FK constraints.
INSERT INTO members (email,password_hash,status)
VALUES ('ci-address-cleanup@example.invalid','fake-hash-not-a-password','pending');
INSERT INTO somang_shipping_addresses
 (member_id,recipient_name,recipient_phone,postal_code,address_line1)
SELECT id,'가상 주소 수령인','000-0000-0000','00000','가상 주소'
FROM members WHERE email='ci-address-cleanup@example.invalid';
DELETE FROM members WHERE email='ci-address-cleanup@example.invalid';
DO $verify$
BEGIN
 IF EXISTS (SELECT 1 FROM somang_shipping_addresses
            WHERE recipient_name='가상 주소 수령인') THEN
   RAISE EXCEPTION 'Orphaned saved shipping address after hard member deletion';
 END IF;
END $verify$;
-- Simulated overlapping checkout/account-deletion lifecycle with fake data.
-- This verifies the resulting state, not genuine cross-connection race ordering.
INSERT INTO members (email,password_hash,status,email_verified_at)
VALUES ('ci-exit-order@example.invalid','fake-hash-not-a-password','active',now());
INSERT INTO somang_shipping_addresses
 (member_id,recipient_name,recipient_phone,postal_code,address_line1)
SELECT id,'가상 탈퇴 회원','000-0000-0000','00000','가상 저장 주소'
FROM members WHERE email='ci-exit-order@example.invalid';
INSERT INTO somang_orders
 (order_number,member_id,customer_name,customer_phone,recipient_name,recipient_phone,
  postal_code,address_line1,merchandise_total_krw,shipping_fee_krw,payable_total_krw)
SELECT 'CI-EXIT-ORDER-001',id,'가상 주문자','000-0000-0000','가상 수령인','000-0000-0000',
       '00000','가상 거래 주소',18900,0,18900
FROM members WHERE email='ci-exit-order@example.invalid';
INSERT INTO somang_order_items
 (order_id,product_id,product_name,unit_price_krw,quantity,line_total_krw)
SELECT id,1,'가상 제품',18900,1,18900
FROM somang_orders WHERE order_number='CI-EXIT-ORDER-001';
-- Simulate the same locking order required by the dormant cleanup routine.
SELECT id FROM members WHERE email='ci-exit-order@example.invalid' FOR UPDATE;
UPDATE members SET status='deleted',email='deleted-ci-exit@invalid.local',
  password_hash='fake-invalidated-hash',deleted_at=now(),updated_at=now()
WHERE email='ci-exit-order@example.invalid';
DELETE FROM somang_shipping_addresses WHERE member_id=(
 SELECT id FROM members WHERE email='deleted-ci-exit@invalid.local');
DO $check_retention$
BEGIN
 IF EXISTS (SELECT 1 FROM somang_shipping_addresses a JOIN members m ON m.id=a.member_id
            WHERE m.email='deleted-ci-exit@invalid.local') THEN
   RAISE EXCEPTION 'Saved address retained after simulated account closure';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM somang_orders o JOIN somang_order_items i ON i.order_id=o.id
                WHERE o.order_number='CI-EXIT-ORDER-001' AND o.payable_total_krw=18900
                  AND i.quantity=1) THEN
   RAISE EXCEPTION 'Historical fake order lost on account closure';
 END IF;
 IF EXISTS (SELECT 1 FROM somang_orders o JOIN members m ON m.id=o.member_id
            WHERE o.order_number='CI-EXIT-ORDER-001' AND m.status='active'
              AND m.email_verified_at IS NOT NULL) THEN
   RAISE EXCEPTION 'Closed fake member still eligible for order lookup';
 END IF;
END $check_retention$;
-- No synthetic order persists after this test.
ROLLBACK;
