-- Durable commerce data: isolated from all SQLite preview/demo tables.
ALTER TABLE members ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS commerce_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commerce_products (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
 price INTEGER NOT NULL CHECK(price>0),stock INTEGER NOT NULL CHECK(stock>=0),
 published INTEGER NOT NULL DEFAULT 0 CHECK(published IN (0,1)),
 compliance_checked INTEGER NOT NULL DEFAULT 0 CHECK(compliance_checked IN (0,1)),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS commerce_orders (
 number TEXT PRIMARY KEY,mode TEXT NOT NULL CHECK(mode IN ('test','live')),member_id BIGINT NOT NULL REFERENCES members(id),
 request_key TEXT NOT NULL UNIQUE,customer_email TEXT NOT NULL,
 recipient TEXT NOT NULL,phone TEXT NOT NULL,postal_code TEXT NOT NULL,address TEXT NOT NULL,address_detail TEXT NOT NULL DEFAULT '',
 subtotal BIGINT NOT NULL CHECK(subtotal>=0),shipping INTEGER NOT NULL CHECK(shipping>=0),
 total BIGINT NOT NULL CHECK(total=subtotal+shipping AND total>0),
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','checking','paid','preparing','shipped','delivered','cancelled','refunded','review')),
 stock_released INTEGER NOT NULL DEFAULT 0 CHECK(stock_released IN (0,1)),payment_key TEXT UNIQUE,receipt_url TEXT NOT NULL DEFAULT '',courier TEXT NOT NULL DEFAULT '',tracking TEXT NOT NULL DEFAULT '',
 consent_version TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS commerce_orders_member ON commerce_orders(member_id,created_at);
CREATE TABLE IF NOT EXISTS commerce_items (
 order_number TEXT NOT NULL REFERENCES commerce_orders(number),product_id BIGINT NOT NULL REFERENCES commerce_products(id),
 name TEXT NOT NULL,price INTEGER NOT NULL CHECK(price>0),quantity INTEGER NOT NULL CHECK(quantity>0),
 PRIMARY KEY(order_number,product_id)
);
CREATE TABLE IF NOT EXISTS commerce_audit (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,reference TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS commerce_consents (
 member_id BIGINT NOT NULL REFERENCES members(id),version TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(member_id,version)
);
CREATE TABLE IF NOT EXISTS commerce_rate (bucket TEXT PRIMARY KEY,hits INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS commerce_tokens (
 digest TEXT PRIMARY KEY,member_id BIGINT NOT NULL REFERENCES members(id),purpose TEXT NOT NULL,
 expires_at BIGINT NOT NULL,consumed INTEGER NOT NULL DEFAULT 0 CHECK(consumed IN (0,1))
);
CREATE TABLE IF NOT EXISTS commerce_returns (
 order_number TEXT PRIMARY KEY REFERENCES commerce_orders(number),reason TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'requested' CHECK(state IN ('requested','reviewed','refunded')),
 received INTEGER NOT NULL DEFAULT 0 CHECK(received IN (0,1)),
 restock INTEGER NOT NULL DEFAULT 0 CHECK(restock IN (0,1)),created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
