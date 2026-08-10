CREATE TABLE claims (
    claim_id             BIGSERIAL PRIMARY KEY,
    claim_no             VARCHAR(20) UNIQUE NOT NULL,
    risk_id              VARCHAR(20),                  -- policy number
    date_of_loss         DATE,
    insured_name         VARCHAR(191),
    agency_name          VARCHAR(191),
    claim_type_code      VARCHAR(30),                  -- 'auto','property','liability'
    loss_type_code       VARCHAR(30),                  -- 'property' / 'liability'
    amount_claimed       DECIMAL(14,2),
    claim_status_code    VARCHAR(20),                  -- 'open','closed','reopened'
    claim_substatus_code VARCHAR(20),
    date_close            TIMESTAMP,
    -- DENORMALIZED CACHE — deliberately kept in sync only approximately
    -- (see generator note below). This is a genuine real-world ambiguity
    -- source: "total paid" could mean this cached field, or the sum of
    -- actual payment transactions in claim_reserves, and they can differ.
    total_paid_amount    DECIMAL(14,2) DEFAULT 0.00,
    catastrophe_yn        CHAR(1) DEFAULT 'N',
    event_name             VARCHAR(30),
    tenant_id               VARCHAR(20) NOT NULL,       -- multi-tenant scoping
    inserted_userid_fk      INTEGER NOT NULL,
    inserted_date             TIMESTAMP DEFAULT now(),
    updated_userid_fk         INTEGER,
    updated_date               TIMESTAMP,
    metadata                  JSONB
);

CREATE TABLE claim_reserves (
    claim_reserve_id      BIGSERIAL PRIMARY KEY,
    claim_id               BIGINT NOT NULL REFERENCES claims(claim_id),
    risk_id                 VARCHAR(50),
    reserve_date             DATE NOT NULL,
    tran_type_code            VARCHAR(20) NOT NULL,   -- 'Loss Reserve' / 'Loss Payment'
    tran_subtype_code          VARCHAR(20) NOT NULL,   -- 'Claim Expense','Legal Expense','Mitigation','Reset Reserves','LAE'
    reserve_description         VARCHAR(191),
    amount                     DECIMAL(14,2) NOT NULL,
    gross_amount                 DECIMAL(14,2),
    tax_amount                    DECIMAL(14,2),
    payment_approved                VARCHAR(10),
    approved_date                    TIMESTAMP,
    status                          VARCHAR(10),        -- e.g. 'active','reversed'
    inserted_userid_fk               INTEGER NOT NULL,
    inserted_date                     TIMESTAMP DEFAULT now(),
    updated_userid_fk                 INTEGER,
    updated_date                       TIMESTAMP,
    metadata                          JSONB
);

CREATE INDEX idx_reserves_claim_id ON claim_reserves(claim_id);
CREATE INDEX idx_reserves_tran_type ON claim_reserves(tran_type_code);
CREATE INDEX idx_reserves_tran_subtype ON claim_reserves(tran_subtype_code);
CREATE INDEX idx_claims_tenant_id ON claims(tenant_id);
CREATE INDEX idx_claims_status ON claims(claim_status_code);