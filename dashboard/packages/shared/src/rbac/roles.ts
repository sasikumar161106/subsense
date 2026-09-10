import { z } from "zod";

export const UserRoleSchema = z.enum([
  "mine_operator",
  "geotech_planner",
  "dgms_regulator",
  "site_admin",
]);

export type UserRole = z.infer<typeof UserRoleSchema>;

export interface RoleMetadata {
  id: UserRole;
  title: string;
  scopeDescription: string;
  capabilities: string[];
  restrictedActions: string[];
  auditStandard: string;
}

export const ROLE_DEFINITIONS: Record<UserRole, RoleMetadata> = {
  mine_operator: {
    id: "mine_operator",
    title: "Mine Operator",
    scopeDescription: "Assigned mine sites and operational panels",
    capabilities: [
      "sensors:live_view",
      "alerts:view_active",
      "alerts:acknowledge",
      "siren:trigger_manual",
      "mesh:view_local_health",
      "alerts:flag_false_alarm",
    ],
    restrictedActions: [
      "Cannot alter baseline geotechnical thresholds",
      "Cannot access cross-site regulator overviews",
      "Cannot delete or modify historical telemetry records",
      "Cannot modify user authentication or MFA settings",
    ],
    auditStandard: "All acks, false alarm submissions, and sirens logged to tamper-proof cryptographic ledger with timestamp and user ID",
  },
  geotech_planner: {
    id: "geotech_planner",
    title: "Geotechnical Planner",
    scopeDescription: "Historical subsidence records, forecasting models, and mine panel simulation workspaces",
    capabilities: [
      "trends:query_history",
      "forecast:view_quantiles",
      "forecast:view_uncertainty_cone",
      "digital_twin:manipulate_3d",
      "simulation:run_what_if_sandbox",
      "sensors:view_geotech_analytics",
    ],
    restrictedActions: [
      "Read-only for production alert triggers and physical sirens",
      "Simulations strictly isolated to sandboxed compute space",
      "Cannot alter production emergency escalation ladders",
    ],
    auditStandard: "Simulation input parameter sets, downsample queries, and scenario executions tracked in planner audit logs",
  },
  dgms_regulator: {
    id: "dgms_regulator",
    title: "DGMS Safety Regulator",
    scopeDescription: "Jurisdiction-wide multi-operator safety oversight (e.g. DGMS Eastern Zone)",
    capabilities: [
      "reports:generate_statutory_compliance",
      "cross_mine:view_safety_rollups",
      "audit:inspect_chronological_ledger",
      "tenants:cross_boundary_inspection",
    ],
    restrictedActions: [
      "Strictly read-only access across all operational panels",
      "No operational acknowledgements permitted",
      "No network gateway or sensor reconfigurations permitted",
    ],
    auditStandard: "Statutory report export sessions and inspection query scopes cryptographically logged with jurisdictional permit validation",
  },
  site_admin: {
    id: "site_admin",
    title: "Site Administrator",
    scopeDescription: "Tenant platform configuration, edge gateway provisioning, and identity governance",
    capabilities: [
      "users:manage_lifecycle",
      "mfa:provision_tokens",
      "gateways:onboard_hardware",
      "sites:provision_zero_downtime",
      "notifications:configure_routing",
      "permits:view_active",
    ],
    restrictedActions: [
      "Cannot delete historical time-series sensor data",
      "Cannot suppress or erase confirmed alert records",
      "Cannot bypass emergency escalation fail-safes",
    ],
    auditStandard: "All configuration adjustments, user status changes, and site onboarding calls signed with administrator user ID",
  },
};
