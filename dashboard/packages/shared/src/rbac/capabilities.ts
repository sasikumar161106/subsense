import { UserRole, ROLE_DEFINITIONS } from "./roles";

export type Capability =
  | "sensors:live_view"
  | "alerts:view_active"
  | "alerts:acknowledge"
  | "siren:trigger_manual"
  | "mesh:view_local_health"
  | "alerts:flag_false_alarm"
  | "trends:query_history"
  | "forecast:view_quantiles"
  | "forecast:view_uncertainty_cone"
  | "digital_twin:manipulate_3d"
  | "simulation:run_what_if_sandbox"
  | "sensors:view_geotech_analytics"
  | "reports:generate_statutory_compliance"
  | "cross_mine:view_safety_rollups"
  | "audit:inspect_chronological_ledger"
  | "tenants:cross_boundary_inspection"
  | "users:manage_lifecycle"
  | "mfa:provision_tokens"
  | "gateways:onboard_hardware"
  | "sites:provision_zero_downtime"
  | "notifications:configure_routing"
  | "permits:view_active";

export function hasCapability(role: UserRole, capability: Capability): boolean {
  const roleDef = ROLE_DEFINITIONS[role];
  if (!roleDef) return false;
  return roleDef.capabilities.includes(capability);
}

export function assertCapability(role: UserRole, capability: Capability): void {
  if (!hasCapability(role, capability)) {
    throw new Error(`Forbidden: Role '${role}' lacks capability '${capability}'`);
  }
}
