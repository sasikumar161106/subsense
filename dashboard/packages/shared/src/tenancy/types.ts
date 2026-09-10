import { z } from "zod";

export interface Jurisdiction {
  id: string;
  name: string;
  code: string;
  regional_office: string;
}

export interface OperatingCompany {
  id: string;
  jurisdiction_id: string;
  name: string;
  short_code: string;
  active_sites_count?: number;
}

export const SiteProvisioningMetadataSchema = z.object({
  site_id: z.string().min(3).regex(/^[A-Z0-9_-]+$/, "site_id must be alphanumeric uppercase with dashes"),
  name: z.string().min(2),
  boundaries_geojson: z.record(z.any()).describe("GeoJSON Polygon or FeatureCollection of panel boundary"),
  gateway_credentials: z.object({
    gateway_eui: z.string().min(8),
    auth_key_hash: z.string().min(8),
    ip_or_domain: z.string().default("10.0.1.254"),
    protocol: z.enum(["lorawan_v1.0.4", "sub_ghz_mesh", "mqtts"]).default("sub_ghz_mesh"),
  }),
  node_ids: z.array(z.string()).min(1).describe("List of deployed mesh node IDs attached to this panel"),
  seam_depth_meters: z.number().positive().default(240),
  extraction_method: z.enum(["longwall", "bord_and_pillar", "opencast"]).default("bord_and_pillar"),
});

export type SiteProvisioningMetadata = z.infer<typeof SiteProvisioningMetadataSchema>;

export interface MineSite {
  id: string;
  tenant_id: string;
  name: string;
  status: "active" | "inactive" | "provisioning";
  node_ids: string[];
  gateway_credentials: {
    gateway_eui: string;
    protocol: string;
  };
  seam_depth_meters: number;
  extraction_method: string;
  boundaries_geojson: Record<string, any>;
  s3_report_prefix: string; // /tenants/{tenant_id}/{site_id}/reports/
  created_at: string;
}

export interface RegulatorPermit {
  id: string;
  regulator_user_id: string;
  jurisdiction_id: string;
  tenant_id: string;
  granted_by: string;
  valid_from: string;
  valid_to: string;
  active: boolean;
}
