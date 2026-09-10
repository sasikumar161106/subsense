-- SubSense Platform Database Schema (PostgreSQL 16 + TimescaleDB)
-- Multi-Tenancy with Row Level Security (RLS) & Dynamic Regulator Jurisdiction Scoping

-- 1. Jurisdictions (Regulator Tiers)
CREATE TABLE IF NOT EXISTS jurisdictions (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(32) NOT NULL UNIQUE,
    regional_office VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tenants (Operating Companies, e.g. ECL, BCCL)
CREATE TABLE IF NOT EXISTS tenants (
    id VARCHAR(64) PRIMARY KEY,
    jurisdiction_id VARCHAR(64) NOT NULL REFERENCES jurisdictions(id),
    name VARCHAR(255) NOT NULL,
    short_code VARCHAR(32) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Users (Multi-tenant with role & MFA support)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) REFERENCES tenants(id), -- Nullable for jurisdictional regulators
    jurisdiction_id VARCHAR(64) REFERENCES jurisdictions(id),
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(64) NOT NULL, -- mine_operator, geotech_planner, dgms_regulator, site_admin
    mfa_enabled BOOLEAN DEFAULT TRUE,
    mfa_secret VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Regulator Permits (Dynamic Cross-Tenant Scoping)
CREATE TABLE IF NOT EXISTS regulator_permits (
    id VARCHAR(64) PRIMARY KEY,
    regulator_user_id VARCHAR(64) NOT NULL REFERENCES users(id),
    jurisdiction_id VARCHAR(64) NOT NULL REFERENCES jurisdictions(id),
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
    granted_by VARCHAR(64) NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Mine Sites / Panels (Zero-Downtime Provisioned)
CREATE TABLE IF NOT EXISTS sites (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) DEFAULT 'active',
    node_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    gateway_credentials JSONB NOT NULL,
    seam_depth_meters NUMERIC(8,2) DEFAULT 240.0,
    extraction_method VARCHAR(64) DEFAULT 'bord_and_pillar',
    boundaries_geojson JSONB NOT NULL,
    s3_report_prefix VARCHAR(512) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Sensor Mesh Nodes
CREATE TABLE IF NOT EXISTS nodes (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
    site_id VARCHAR(64) NOT NULL REFERENCES sites(id),
    zone_id VARCHAR(64) NOT NULL,
    node_type VARCHAR(64) DEFAULT 'multi_sensor_extensometer',
    hardware_version VARCHAR(32) DEFAULT 'REV-C2',
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    status VARCHAR(32) DEFAULT 'online',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Real-Time Node Telemetry & Health (Contract 14.1, TimescaleDB hypertable candidate)
CREATE TABLE IF NOT EXISTS node_telemetry (
    time TIMESTAMPTZ NOT NULL,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
    site_id VARCHAR(64) NOT NULL REFERENCES sites(id),
    node_id VARCHAR(64) NOT NULL REFERENCES nodes(id),
    as_of TIMESTAMPTZ NOT NULL,
    is_stale BOOLEAN NOT NULL DEFAULT FALSE,
    tilt_deg NUMERIC(8,4) NOT NULL,
    vibration_rms_mm_s NUMERIC(8,4) NOT NULL,
    displacement_mm NUMERIC(8,4) NOT NULL,
    crack_index NUMERIC(8,4) NOT NULL,
    anomaly_score NUMERIC(8,4) NOT NULL,
    battery_pct NUMERIC(5,2) NOT NULL,
    rssi_dbm NUMERIC(6,2) NOT NULL,
    hop_count INT NOT NULL,
    predicted_maintenance_days NUMERIC(8,2) NOT NULL,
    raw_payload JSONB
);

-- 8. Alert Lifecycle Events (Contract 14.2)
CREATE TABLE IF NOT EXISTS alert_lifecycle_events (
    alert_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
    site_id VARCHAR(64) NOT NULL REFERENCES sites(id),
    zone_id VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL, -- info, warning, critical
    state VARCHAR(32) NOT NULL,    -- new, acknowledged, escalated, resolved, false_alarm
    raised_at TIMESTAMPTZ NOT NULL,
    acknowledged_by VARCHAR(64),
    acknowledged_at TIMESTAMPTZ,
    time_to_critical_min NUMERIC(8,2) NOT NULL,
    time_to_critical_max NUMERIC(8,2) NOT NULL,
    confidence_score NUMERIC(5,4) NOT NULL,
    contributing_sensors JSONB NOT NULL,
    explanation_summary TEXT NOT NULL,
    escalated_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(64),
    false_alarm_reason VARCHAR(64),
    false_alarm_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. DGMS Statutory Reports (Contract 14.3)
CREATE TABLE IF NOT EXISTS dgms_reports (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
    site_id VARCHAR(64) NOT NULL REFERENCES sites(id),
    report_type VARCHAR(128) NOT NULL,
    reporting_period_start TIMESTAMPTZ NOT NULL,
    reporting_period_end TIMESTAMPTZ NOT NULL,
    requested_by VARCHAR(64) NOT NULL,
    output_format VARCHAR(64) NOT NULL,
    include_kriging_risk_maps BOOLEAN DEFAULT TRUE,
    include_audit_trail BOOLEAN DEFAULT TRUE,
    s3_key VARCHAR(512),
    download_url TEXT,
    status VARCHAR(32) DEFAULT 'ready',
    hash_signature VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. Tamper-Proof Cryptographic Audit Ledger
CREATE TABLE IF NOT EXISTS tamper_proof_audit_ledger (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    action VARCHAR(128) NOT NULL,
    details_json JSONB NOT NULL,
    record_hash VARCHAR(128) NOT NULL,
    prev_hash VARCHAR(128) NOT NULL
);

-- =========================================================================
-- ROW LEVEL SECURITY (RLS) SETUP
-- Mandatory tenant isolation enforced by session context variable:
--   app.current_tenant_id
-- Dynamic regulator scoping via regulator_permits permit table:
--   app.is_regulator = 'true' AND current_user_id has active permit for tenant
-- =========================================================================

-- Application Role for RLS Enforcement (non-superuser)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'subsense_app_user') THEN
    CREATE ROLE subsense_app_user WITH LOGIN;
  END IF;
END
$$;
GRANT ALL ON ALL TABLES IN SCHEMA public TO subsense_app_user;

ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE node_telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_lifecycle_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dgms_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE tamper_proof_audit_ledger ENABLE ROW LEVEL SECURITY;

-- Dynamic Tenant RLS Policy for 'sites'
DROP POLICY IF EXISTS sites_tenant_isolation_policy ON sites;
CREATE POLICY sites_tenant_isolation_policy ON sites
FOR ALL
USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
  OR
  (
    current_setting('app.is_regulator', true) = 'true'
    AND EXISTS (
      SELECT 1 FROM regulator_permits rp
      WHERE rp.regulator_user_id = NULLIF(current_setting('app.current_user_id', true), '')
        AND rp.tenant_id = sites.tenant_id
        AND rp.active = true
        AND NOW() BETWEEN rp.valid_from AND rp.valid_to
    )
  )
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
);

-- Dynamic Tenant RLS Policy for 'nodes'
DROP POLICY IF EXISTS nodes_tenant_isolation_policy ON nodes;
CREATE POLICY nodes_tenant_isolation_policy ON nodes
FOR ALL
USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
  OR
  (
    current_setting('app.is_regulator', true) = 'true'
    AND EXISTS (
      SELECT 1 FROM regulator_permits rp
      WHERE rp.regulator_user_id = NULLIF(current_setting('app.current_user_id', true), '')
        AND rp.tenant_id = nodes.tenant_id
        AND rp.active = true
        AND NOW() BETWEEN rp.valid_from AND rp.valid_to
    )
  )
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
);

-- Dynamic Tenant RLS Policy for 'node_telemetry'
DROP POLICY IF EXISTS telemetry_tenant_isolation_policy ON node_telemetry;
CREATE POLICY telemetry_tenant_isolation_policy ON node_telemetry
FOR ALL
USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
  OR
  (
    current_setting('app.is_regulator', true) = 'true'
    AND EXISTS (
      SELECT 1 FROM regulator_permits rp
      WHERE rp.regulator_user_id = NULLIF(current_setting('app.current_user_id', true), '')
        AND rp.tenant_id = node_telemetry.tenant_id
        AND rp.active = true
        AND NOW() BETWEEN rp.valid_from AND rp.valid_to
    )
  )
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
);

-- Dynamic Tenant RLS Policy for 'alert_lifecycle_events'
DROP POLICY IF EXISTS alerts_tenant_isolation_policy ON alert_lifecycle_events;
CREATE POLICY alerts_tenant_isolation_policy ON alert_lifecycle_events
FOR ALL
USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
  OR
  (
    current_setting('app.is_regulator', true) = 'true'
    AND EXISTS (
      SELECT 1 FROM regulator_permits rp
      WHERE rp.regulator_user_id = NULLIF(current_setting('app.current_user_id', true), '')
        AND rp.tenant_id = alert_lifecycle_events.tenant_id
        AND rp.active = true
        AND NOW() BETWEEN rp.valid_from AND rp.valid_to
    )
  )
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
);

-- Dynamic Tenant RLS Policy for 'dgms_reports'
DROP POLICY IF EXISTS reports_tenant_isolation_policy ON dgms_reports;
CREATE POLICY reports_tenant_isolation_policy ON dgms_reports
FOR ALL
USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
  OR
  (
    current_setting('app.is_regulator', true) = 'true'
    AND EXISTS (
      SELECT 1 FROM regulator_permits rp
      WHERE rp.regulator_user_id = NULLIF(current_setting('app.current_user_id', true), '')
        AND rp.tenant_id = dgms_reports.tenant_id
        AND rp.active = true
        AND NOW() BETWEEN rp.valid_from AND rp.valid_to
    )
  )
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
);

-- Dynamic Tenant RLS Policy for 'tamper_proof_audit_ledger'
DROP POLICY IF EXISTS audit_tenant_isolation_policy ON tamper_proof_audit_ledger;
CREATE POLICY audit_tenant_isolation_policy ON tamper_proof_audit_ledger
FOR ALL
USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
  OR
  (
    current_setting('app.is_regulator', true) = 'true'
    AND EXISTS (
      SELECT 1 FROM regulator_permits rp
      WHERE rp.regulator_user_id = NULLIF(current_setting('app.current_user_id', true), '')
        AND rp.tenant_id = tamper_proof_audit_ledger.tenant_id
        AND rp.active = true
        AND NOW() BETWEEN rp.valid_from AND rp.valid_to
    )
  )
)
WITH CHECK (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
);
