import { getDb, withSystemScope } from "./client";

export async function seedDatabase(): Promise<void> {
  await getDb(); // ensures schema is created

  await withSystemScope(async (client) => {
    // Check if already seeded
    const check = await client.query("SELECT COUNT(*) as count FROM jurisdictions;");
    if (parseInt(check.rows[0].count, 10) > 0) {
      return; // already seeded
    }

    // 1. Jurisdictions
    await client.query(`
      INSERT INTO jurisdictions (id, name, code, regional_office)
      VALUES 
      ('JUR-DGMS-EAST', 'DGMS Eastern Zone', 'DGMS-EAST', 'Dhanbad Directorate, Jharkhand'),
      ('JUR-DGMS-CENTRAL', 'DGMS Central Zone', 'DGMS-CENTRAL', 'Nagpur Directorate, Maharashtra');
    `);

    // 2. Tenants (Operating Companies)
    await client.query(`
      INSERT INTO tenants (id, jurisdiction_id, name, short_code)
      VALUES 
      ('OPCO-ECL-01', 'JUR-DGMS-EAST', 'Eastern Coalfields Limited', 'ECL'),
      ('OPCO-BCCL-02', 'JUR-DGMS-EAST', 'Bharat Coking Coal Limited', 'BCCL');
    `);

    // 3. Users for all 4 Roles
    await client.query(`
      INSERT INTO users (id, tenant_id, jurisdiction_id, email, name, role, mfa_enabled, mfa_secret)
      VALUES 
      ('USR-OP-8492', 'OPCO-ECL-01', 'JUR-DGMS-EAST', 'operator.ecl@subsense.gov.in', 'Rajesh Kumar (Mine Operator)', 'mine_operator', true, 'JBSWY3DPEHPK3PXP'),
      ('USR-GEO-1021', 'OPCO-ECL-01', 'JUR-DGMS-EAST', 'geotech.ecl@subsense.gov.in', 'Dr. Ananya Sen (Geotech Planner)', 'geotech_planner', true, 'JBSWY3DPEHPK3PXP'),
      ('USR-REG-4412', NULL, 'JUR-DGMS-EAST', 'inspector.dgms@subsense.gov.in', 'S. K. Verma (DGMS Chief Inspector)', 'dgms_regulator', true, 'JBSWY3DPEHPK3PXP'),
      ('USR-ADM-001', 'OPCO-ECL-01', 'JUR-DGMS-EAST', 'admin.ecl@subsense.gov.in', 'Vikram Malhotra (Site Administrator)', 'site_admin', true, 'JBSWY3DPEHPK3PXP'),
      ('USR-OP-9901', 'OPCO-BCCL-02', 'JUR-DGMS-EAST', 'operator.bccl@subsense.gov.in', 'Manoj Hansda (BCCL Operator)', 'mine_operator', true, 'JBSWY3DPEHPK3PXP');
    `);

    // 4. Dynamic Regulator Permits
    await client.query(`
      INSERT INTO regulator_permits (id, regulator_user_id, jurisdiction_id, tenant_id, granted_by, valid_from, valid_to, active)
      VALUES 
      ('PERMIT-REG-ECL', 'USR-REG-4412', 'JUR-DGMS-EAST', 'OPCO-ECL-01', 'DIRECTOR-GENERAL-DGMS', '2026-01-01T00:00:00.000Z', '2027-12-31T23:59:59.000Z', true),
      ('PERMIT-REG-BCCL', 'USR-REG-4412', 'JUR-DGMS-EAST', 'OPCO-BCCL-02', 'DIRECTOR-GENERAL-DGMS', '2026-01-01T00:00:00.000Z', '2027-12-31T23:59:59.000Z', true);
    `);

    // 5. Mine Sites / Panels
    await client.query(`
      INSERT INTO sites (id, tenant_id, name, status, node_ids, gateway_credentials, seam_depth_meters, extraction_method, boundaries_geojson, s3_report_prefix)
      VALUES 
      (
        'PANEL7-JHARIA',
        'OPCO-ECL-01',
        'Jharia Seam 7 Subsidence Sector',
        'active',
        '["SS-PANEL7-N042", "SS-PANEL7-N043", "SS-PANEL7-N044", "SS-PANEL7-N045"]'::jsonb,
        '{"gateway_eui": "GW-ECL-JH-007", "protocol": "sub_ghz_mesh"}'::jsonb,
        240.0,
        'bord_and_pillar',
        '{"type": "Polygon", "coordinates": [[[86.415, 23.742], [86.425, 23.745], [86.422, 23.755], [86.410, 23.750], [86.415, 23.742]]]}'::jsonb,
        '/tenants/OPCO-ECL-01/PANEL7-JHARIA/reports/'
      ),
      (
        'RANIGANJ-SEAM-4',
        'OPCO-ECL-01',
        'Raniganj Seam 4 Longwall Sector',
        'active',
        '["SS-RANI-N011", "SS-RANI-N012"]'::jsonb,
        '{"gateway_eui": "GW-ECL-RN-004", "protocol": "lorawan_v1.0.4"}'::jsonb,
        310.0,
        'longwall',
        '{"type": "Polygon", "coordinates": [[[87.110, 23.610], [87.125, 23.615], [87.120, 23.625], [87.105, 23.620], [87.110, 23.610]]]}'::jsonb,
        '/tenants/OPCO-ECL-01/RANIGANJ-SEAM-4/reports/'
      ),
      (
        'MOONIDIH-SEAM-16',
        'OPCO-BCCL-02',
        'Moonidih Underground Deep Seam 16',
        'active',
        '["SS-MOON-N101", "SS-MOON-N102"]'::jsonb,
        '{"gateway_eui": "GW-BCCL-MN-016", "protocol": "sub_ghz_mesh"}'::jsonb,
        450.0,
        'longwall',
        '{"type": "Polygon", "coordinates": [[[86.340, 23.710], [86.355, 23.715], [86.350, 23.725], [86.335, 23.720], [86.340, 23.710]]]}'::jsonb,
        '/tenants/OPCO-BCCL-02/MOONIDIH-SEAM-16/reports/'
      );
    `);

    // 6. Sensor Mesh Nodes
    await client.query(`
      INSERT INTO nodes (id, tenant_id, site_id, zone_id, node_type, hardware_version, latitude, longitude, status)
      VALUES 
      ('SS-PANEL7-N042', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'PANEL7-ZONE-C', 'multi_sensor_extensometer', 'REV-C2', 23.7461, 86.4182, 'online'),
      ('SS-PANEL7-N043', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'PANEL7-ZONE-C', 'multi_sensor_extensometer', 'REV-C2', 23.7475, 86.4195, 'online'),
      ('SS-PANEL7-N044', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'PANEL7-ZONE-B', 'tilt_inclinometer_array', 'REV-C2', 23.7445, 86.4160, 'online'),
      ('SS-PANEL7-N045', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'PANEL7-ZONE-A', 'crack_displacement_gauge', 'REV-C2', 23.7430, 86.4140, 'stale'),
      ('SS-MOON-N101', 'OPCO-BCCL-02', 'MOONIDIH-SEAM-16', 'MOON-ZONE-1', 'multi_sensor_extensometer', 'REV-B4', 23.7145, 86.3450, 'online'),
      ('SS-MOON-N102', 'OPCO-BCCL-02', 'MOONIDIH-SEAM-16', 'MOON-ZONE-2', 'tilt_inclinometer_array', 'REV-B4', 23.7160, 86.3480, 'online');
    `);

    // 7. Seeded Telemetry Matching Schema 14.1
    await client.query(`
      INSERT INTO node_telemetry (
        time, tenant_id, site_id, node_id, as_of, is_stale,
        tilt_deg, vibration_rms_mm_s, displacement_mm, crack_index,
        anomaly_score, battery_pct, rssi_dbm, hop_count, predicted_maintenance_days, raw_payload
      )
      VALUES 
      (
        '2026-09-09T04:15:00.000Z', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'SS-PANEL7-N042',
        '2026-09-09T04:15:00.000Z', false,
        0.183, 1.420, 3.700, 0.020,
        0.86, 78.0, -71.0, 3, 21.0,
        '{"tenant_id": "OPCO-ECL-01", "site_id": "PANEL7-JHARIA", "node_id": "SS-PANEL7-N042", "as_of": "2026-09-09T04:15:00.000Z", "is_stale": false, "readings": {"tilt_deg": 0.183, "vibration_rms_mm_s": 1.42, "displacement_mm": 3.70, "crack_index": 0.02}, "anomaly_score": 0.86, "health": {"battery_pct": 78, "rssi_dbm": -71, "hop_count": 3, "predicted_maintenance_days": 21}}'::jsonb
      ),
      (
        '2026-09-09T04:14:30.000Z', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'SS-PANEL7-N043',
        '2026-09-09T04:14:30.000Z', false,
        0.125, 0.980, 2.450, 0.010,
        0.42, 85.0, -68.0, 2, 45.0,
        '{"tenant_id": "OPCO-ECL-01", "site_id": "PANEL7-JHARIA", "node_id": "SS-PANEL7-N043", "as_of": "2026-09-09T04:14:30.000Z", "is_stale": false, "readings": {"tilt_deg": 0.125, "vibration_rms_mm_s": 0.98, "displacement_mm": 2.45, "crack_index": 0.01}, "anomaly_score": 0.42, "health": {"battery_pct": 85, "rssi_dbm": -68, "hop_count": 2, "predicted_maintenance_days": 45}}'::jsonb
      ),
      (
        '2026-09-09T04:10:00.000Z', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'SS-PANEL7-N045',
        '2026-09-09T04:10:00.000Z', true,
        0.052, 0.320, 1.100, 0.000,
        0.15, 34.0, -89.0, 4, 8.0,
        '{"tenant_id": "OPCO-ECL-01", "site_id": "PANEL7-JHARIA", "node_id": "SS-PANEL7-N045", "as_of": "2026-09-09T04:10:00.000Z", "is_stale": true, "readings": {"tilt_deg": 0.052, "vibration_rms_mm_s": 0.32, "displacement_mm": 1.10, "crack_index": 0.00}, "anomaly_score": 0.15, "health": {"battery_pct": 34, "rssi_dbm": -89, "hop_count": 4, "predicted_maintenance_days": 8}}'::jsonb
      ),
      (
        '2026-09-09T04:15:00.000Z', 'OPCO-BCCL-02', 'MOONIDIH-SEAM-16', 'SS-MOON-N101',
        '2026-09-09T04:15:00.000Z', false,
        0.091, 0.650, 1.820, 0.005,
        0.31, 92.0, -64.0, 1, 60.0,
        '{"tenant_id": "OPCO-BCCL-02", "site_id": "MOONIDIH-SEAM-16", "node_id": "SS-MOON-N101", "as_of": "2026-09-09T04:15:00.000Z", "is_stale": false, "readings": {"tilt_deg": 0.091, "vibration_rms_mm_s": 0.65, "displacement_mm": 1.82, "crack_index": 0.005}, "anomaly_score": 0.31, "health": {"battery_pct": 92, "rssi_dbm": -64, "hop_count": 1, "predicted_maintenance_days": 60}}'::jsonb
      );
    `);

    // 8. Seeded Alerts Matching Schema 14.2
    await client.query(`
      INSERT INTO alert_lifecycle_events (
        alert_id, tenant_id, site_id, zone_id, severity, state,
        raised_at, acknowledged_by, acknowledged_at,
        time_to_critical_min, time_to_critical_max, confidence_score,
        contributing_sensors, explanation_summary
      )
      VALUES 
      (
        'ALERT-PANEL7-20260909-0412', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'PANEL7-ZONE-C',
        'warning', 'acknowledged',
        '2026-09-09T04:12:00.000Z', 'USR-OP-8492', '2026-09-09T04:14:10.000Z',
        6.0, 14.0, 0.79,
        '["tilt_deg", "displacement_mm"]'::jsonb,
        'Sustained tilt increase at N042, corroborated by 3 neighboring nodes over 40 minutes.'
      ),
      (
        'ALERT-PANEL7-20260909-0500', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'PANEL7-ZONE-C',
        'critical', 'new',
        '2026-09-09T05:00:00.000Z', NULL, NULL,
        2.5, 5.0, 0.94,
        '["displacement_mm", "vibration_rms_mm_s"]'::jsonb,
        'Accelerated extensometer displacement exceeding 3.7mm with continuous vibration pulses indicating impending strata delamination.'
      ),
      (
        'ALERT-MOONIDIH-20260909-0105', 'OPCO-BCCL-02', 'MOONIDIH-SEAM-16', 'MOON-ZONE-1',
        'warning', 'new',
        '2026-09-09T01:05:00.000Z', NULL, NULL,
        12.0, 24.0, 0.65,
        '["crack_index"]'::jsonb,
        'Micro-fracture expansion detected in longwall support pillar.'
      );
    `);

    // 9. DGMS Reports Matching Schema 14.3
    await client.query(`
      INSERT INTO dgms_reports (
        id, tenant_id, site_id, report_type, reporting_period_start, reporting_period_end,
        requested_by, output_format, include_kriging_risk_maps, include_audit_trail,
        s3_key, download_url, status, hash_signature
      )
      VALUES 
      (
        'RPT-ECL-202608-01', 'OPCO-ECL-01', 'PANEL7-JHARIA', 'dgms_statutory_subsidence_summary_v2',
        '2026-08-01T00:00:00.000Z', '2026-08-31T23:59:59.000Z',
        'USR-REG-4412', 'application/pdf', true, true,
        '/tenants/OPCO-ECL-01/PANEL7-JHARIA/reports/dgms_summary_202608.pdf',
        '/api/v1/reports/RPT-ECL-202608-01/download',
        'ready',
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
      );
    `);

    // 10. Initial Audit Ledger Genesis Block
    await client.query(`
      INSERT INTO tamper_proof_audit_ledger (
        id, timestamp, tenant_id, user_id, action, details_json, record_hash, prev_hash
      )
      VALUES 
      (
        'LEDGER-GENESIS', '2026-09-01T00:00:00.000Z', 'OPCO-ECL-01', 'SYSTEM',
        'GENESIS_BLOCK', '{"message": "SubSense Layer 6 Audit Ledger Initialized"}'::jsonb,
        '0000000000000000000000000000000000000000000000000000000000000000',
        '0000000000000000000000000000000000000000000000000000000000000000'
      );
    `);
  });
}
