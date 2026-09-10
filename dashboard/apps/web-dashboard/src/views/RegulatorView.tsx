import React, { useState, useEffect } from "react";
import { fetchApi } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import {
  ShieldCheck,
  Building2,
  FileDown,
  Lock,
  CheckCircle,
  AlertTriangle,
  Flame,
  FileCheck2,
} from "lucide-react";

export const RegulatorView: React.FC = () => {
  const { currentUser } = useAuth();
  const [rollupData, setRollupData] = useState<any>(null);
  const [permits, setPermits] = useState<any[]>([]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generatedReport, setGeneratedReport] = useState<any>(null);

  useEffect(() => {
    const loadRegulatorData = async () => {
      try {
        const [rollupRes, permitsRes] = await Promise.all([
          fetchApi("/regulator/rollup", { userRole: currentUser.role, userId: currentUser.userId }),
          fetchApi("/regulator/permits", { userRole: currentUser.role, userId: currentUser.userId }),
        ]);
        setRollupData(rollupRes);
        setPermits(permitsRes.permits || []);
      } catch (err) {
        console.error("Failed to load regulator rollup:", err);
      }
    };
    loadRegulatorData();
  }, [currentUser]);

  const handleGenerateStatutoryReport = async (tenantId: string, siteId: string) => {
    setIsGenerating(true);
    try {
      const payload = {
        tenant_id: tenantId,
        site_id: siteId,
        report_type: "dgms_statutory_subsidence_summary_v2",
        reporting_period: {
          start_date: "2026-08-01T00:00:00.000Z",
          end_date: "2026-08-31T23:59:59.000Z",
        },
        requested_by: currentUser.userId,
        output_format: "application/pdf",
        include_kriging_risk_maps: true,
        include_audit_trail: true,
      };

      const res = await fetchApi("/regulator/reports/generate", {
        method: "POST",
        body: JSON.stringify(payload),
        userRole: currentUser.role,
        userId: currentUser.userId,
      });

      setGeneratedReport(res);
    } catch (err) {
      console.error("Failed to generate report:", err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6 font-mono">
      {/* Regulator Header Banner */}
      <div className="bg-slate-900/80 border border-purple-800/80 p-5 rounded-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-purple-950 text-purple-400 border border-purple-800">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white uppercase tracking-wider">
              DGMS Safety Regulator Jurisdictional Rollup
            </h2>
            <p className="text-xs text-slate-300">
              Jurisdiction: DGMS Eastern Zone (Dhanbad Directorate) • Dynamic Permit-Based Scoping
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 bg-purple-950/60 px-3 py-1.5 rounded-lg border border-purple-800/60 text-xs text-purple-300">
          <Lock className="w-3.5 h-3.5" />
          <span>Strictly Read-Only Operational Safeguard Enforced</span>
        </div>
      </div>

      {/* Active Permit Scopes */}
      <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
        <div className="text-xs text-slate-400 font-bold uppercase tracking-wide">
          Verified Jurisdictional Permits:
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {permits.map((p) => (
            <div
              key={p.id}
              className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs"
            >
              <div>
                <div className="font-bold text-slate-200">{p.tenant_name} ({p.tenant_code})</div>
                <div className="text-[10px] text-slate-400">Permit ID: {p.id}</div>
              </div>
              <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-2 py-0.5 rounded-full font-bold">
                ACTIVE JURISDICTION
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Cross-Mine Operator Safety Rollup */}
      <div className="space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide flex items-center gap-2">
          <Building2 className="w-4 h-4 text-cyan-400" />
          Cross-Mine Multi-Site Safety Rollup
        </h3>

        {rollupData?.rollup ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {rollupData.rollup.map((opco: any) => (
              <div
                key={opco.tenant_id}
                className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4"
              >
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h4 className="font-bold text-base text-slate-100">{opco.tenant_id}</h4>
                    <div className="text-xs text-slate-400">{opco.sites.length} Monitored Sectors</div>
                  </div>

                  <div className="flex items-center gap-3 text-xs">
                    <div className="text-right">
                      <div className="text-[10px] text-slate-400">Compliance</div>
                      <div className="text-emerald-400 font-bold">{opco.compliance_score_pct}%</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-slate-400">Critical</div>
                      <div className="text-red-400 font-bold">{opco.active_critical_alerts}</div>
                    </div>
                  </div>
                </div>

                {/* Site breakdown */}
                <div className="space-y-2.5">
                  {opco.sites.map((site: any) => (
                    <div
                      key={site.site_id}
                      className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs"
                    >
                      <div>
                        <div className="font-bold text-slate-200">{site.site_name}</div>
                        <div className="text-[10px] text-slate-400">
                          {site.site_id} • Depth: {site.seam_depth_meters}m • {site.extraction_method}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                            site.safety_status === "RED_CRITICAL"
                              ? "bg-red-950 text-red-300 border border-red-800 animate-pulse"
                              : site.safety_status === "AMBER_WARNING"
                              ? "bg-amber-950 text-amber-300 border border-amber-800"
                              : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          }`}
                        >
                          {site.safety_status.replace(/_/g, " ")}
                        </span>

                        <button
                          id={`btn-report-${site.site_id}`}
                          onClick={() => handleGenerateStatutoryReport(opco.tenant_id, site.site_id)}
                          disabled={isGenerating}
                          className="px-2.5 py-1 rounded bg-purple-700 hover:bg-purple-600 text-white font-bold text-[11px] flex items-center gap-1 shadow transition-colors"
                        >
                          <FileDown className="w-3 h-3" />
                          Generate 14.3 PDF
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-slate-400 text-xs">Querying multi-tenant permit scope...</div>
        )}
      </div>

      {/* Generated Report Output Banner */}
      {generatedReport && (
        <div className="bg-slate-900 border-2 border-emerald-500/80 rounded-xl p-4 flex items-center justify-between gap-4 animate-in fade-in">
          <div className="flex items-center gap-3">
            <FileCheck2 className="w-6 h-6 text-emerald-400" />
            <div>
              <div className="text-xs font-bold text-slate-100 uppercase">
                DGMS Statutory Subsidence Summary Generated (Contract 14.3)
              </div>
              <div className="text-[11px] text-slate-400">
                Report ID: {generatedReport.report_id} • S3 Path: {generatedReport.s3_key}
              </div>
              <div className="text-[10px] text-emerald-400">
                Cryptographic Signature: {generatedReport.hash_signature}
              </div>
            </div>
          </div>

          <a
            href={generatedReport.download_url}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 shadow transition-colors"
          >
            <FileDown className="w-3.5 h-3.5" />
            Download Signed PDF
          </a>
        </div>
      )}
    </div>
  );
};
