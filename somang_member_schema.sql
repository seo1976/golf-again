-- Somang Pharmacy membership schema, PostgreSQL 18.
-- Apply ONLY to somang-pharmacy-members-db after private connection setup.
-- Do not use the existing ephemeral SQLite demo member table for real users.
CREATE TABLE IF NOT EXISTS members (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(254) NOT NULL,
    password_hash TEXT NOT NULL,
    email_verified_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
      CHECK (status IN ('pending','active','suspended','deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT members_email_lower CHECK (email = lower(email)),
    CONSTRAINT members_email_unique UNIQUE(email)
);
CREATE TABLE IF NOT EXISTS member_email_tokens (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id BIGINT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    purpose VARCHAR(20) NOT NULL CHECK(purpose IN ('verify','reset')),
    token_digest CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS member_email_tokens_lookup
    ON member_email_tokens(member_id, purpose, expires_at);
CREATE TABLE IF NOT EXISTS member_security_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    member_id BIGINT REFERENCES members(id) ON DELETE SET NULL,
    event_type VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- No plaintext passwords or raw verification tokens are stored.
-- Before activation: transactional email delivery, rate limits,
-- consent/version recording, privacy disclosures, session security,
-- data retention and deletion policy, and production regression tests.
