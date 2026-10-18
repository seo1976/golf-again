-- Somang Pharmacy order and shipping schema (design only).
-- Do not run against production until privacy, retention and checkout are approved.
CREATE TABLE IF NOT EXISTS somang_shipping_addresses (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 member_id BIGINT,
 recipient_name TEXT NOT NULL,
 recipient_phone TEXT NOT NULL,
 postal_code VARCHAR(12) NOT NULL,
 address_line1 TEXT NOT NULL,
 address_line2 TEXT,
 delivery_instructions TEXT,
 is_default BOOLEAN NOT NULL DEFAULT FALSE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS somang_shipping_addresses_member_idx ON somang_shipping_addresses(member_id);
CREATE TABLE IF NOT EXISTS somang_orders (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 order_number VARCHAR(40) NOT NULL UNIQUE,
 member_id BIGINT,
 customer_name TEXT NOT NULL,
 customer_phone TEXT NOT NULL,
 customer_email TEXT,
 recipient_name TEXT NOT NULL,
 recipient_phone TEXT NOT NULL,
 postal_code VARCHAR(12) NOT NULL,
 address_line1 TEXT NOT NULL,
 address_line2 TEXT,
 delivery_instructions TEXT,
 merchandise_total_krw BIGINT NOT NULL CHECK(merchandise_total_krw>=0),
 shipping_fee_krw BIGINT NOT NULL CHECK(shipping_fee_krw>=0),
 payable_total_krw BIGINT NOT NULL CHECK(payable_total_krw=merchandise_total_krw+shipping_fee_krw),
 order_status VARCHAR(32) NOT NULL DEFAULT 'pending',
 payment_status VARCHAR(32) NOT NULL DEFAULT 'not_started',
 shipping_status VARCHAR(32) NOT NULL DEFAULT 'not_started',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS somang_orders_member_idx ON somang_orders(member_id);
CREATE INDEX IF NOT EXISTS somang_orders_created_idx ON somang_orders(created_at DESC);
CREATE TABLE IF NOT EXISTS somang_order_items (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 order_id BIGINT NOT NULL REFERENCES somang_orders(id) ON DELETE RESTRICT,
 product_id BIGINT NOT NULL,
 product_name TEXT NOT NULL,
 unit_price_krw BIGINT NOT NULL CHECK(unit_price_krw>=0),
 quantity INTEGER NOT NULL CHECK(quantity>0),
 line_total_krw BIGINT NOT NULL CHECK(line_total_krw=unit_price_krw*quantity)
);
CREATE INDEX IF NOT EXISTS somang_order_items_order_idx ON somang_order_items(order_id);
-- Pending: data retention, access controls, encryption, consent and payment verification.
