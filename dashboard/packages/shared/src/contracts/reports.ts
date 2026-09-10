import { z } from "zod";

export const ReportingPeriodSchema = z.object({
  start_date: z.string().datetime().describe("Start timestamp ISO 8601"),
  end_date: z.string().datetime().describe("End timestamp ISO 8601"),
});

// Contract 14.3: DGMS statutory report request payload
export const DgmsReportRequestPayloadSchema = z.object({
  tenant_id: z.string().min(1).describe("Operating company tenant identifier (e.g. OPCO-ECL-01)"),
  site_id: z.string().min(1).describe("Mine site/panel identifier (e.g. PANEL7-JHARIA)"),
  report_type: z.string().min(1).describe("Report template identifier (e.g. dgms_statutory_subsidence_summary_v2)"),
  reporting_period: ReportingPeriodSchema,
  requested_by: z.string().min(1).describe("Regulator or Auditor User ID (e.g. USR-REG-4412)"),
  output_format: z.enum(["application/pdf", "application/json", "text/csv"]).describe("MIME format of report"),
  include_kriging_risk_maps: z.boolean().describe("Whether to attach 2D kriging spatial interpolation risk heatmaps"),
  include_audit_trail: z.boolean().describe("Whether to append cryptographically signed audit ledger"),
});

export const DgmsReportResponseSchema = z.object({
  report_id: z.string(),
  tenant_id: z.string(),
  site_id: z.string(),
  report_type: z.string(),
  status: z.enum(["pending", "generating", "ready", "failed"]),
  download_url: z.string().nullable(),
  s3_key: z.string().nullable(),
  generated_at: z.string().datetime().nullable(),
  file_size_bytes: z.number().nullable(),
  hash_signature: z.string().nullable(),
});

export type ReportingPeriod = z.infer<typeof ReportingPeriodSchema>;
export type DgmsReportRequestPayload = z.infer<typeof DgmsReportRequestPayloadSchema>;
export type DgmsReportResponse = z.infer<typeof DgmsReportResponseSchema>;
