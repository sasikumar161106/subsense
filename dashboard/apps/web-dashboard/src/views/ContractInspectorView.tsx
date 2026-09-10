import React, { useState } from "react";
import { fetchApi } from "../services/api";
import { FileCode2, CheckCircle2, AlertOctagon, Send, Copy, Check } from "lucide-react";

export const ContractInspectorView: React.FC = () => {
  const [activeContract, setActiveContract] = useState<"14.1" | "14.2" | "14.3">("14.1");
  const [payloadText, setPayloadText] = useState<string>("");
  const [validationResult, setValidationResult] = useState<any>(null);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  // Canonical payloads from Prompt section 5
  const CANONICAL_PAYLOADS = {
    "14.1": {
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      node_id: "SS-PANEL7-N042",
      as_of: "2026-09-09T04:15:00.000Z",
      is_stale: false,
      readings: {
        tilt_deg: 0.183,
        vibration_rms_mm_s: 1.42,
        displacement_mm: 3.7,
        crack_index: 0.02,
      },
      anomaly_score: 0.86,
      health: {
        battery_pct: 78,
        rssi_dbm: -71,
        hop_count: 3,
        predicted_maintenance_days: 21,
      },
    },
    "14.2": {
      alert_id: "ALERT-PANEL7-20260909-0412",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "warning",
      state: "acknowledged",
      raised_at: "2026-09-09T04:12:00.000Z",
      acknowledged_by: "USR-OP-8492",
      acknowledged_at: "2026-09-09T04:14:10.000Z",
      time_to_critical_hours: [6.0, 14.0],
      confidence_score: 0.79,
      contributing_sensors: ["tilt_deg", "displacement_mm"],
      explanation_summary:
        "Sustained tilt increase at N042, corroborated by 3 neighboring nodes over 40 minutes.",
    },
    "14.3": {
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      report_type: "dgms_statutory_subsidence_summary_v2",
      reporting_period: {
        start_date: "2026-08-01T00:00:00.000Z",
        end_date: "2026-08-31T23:59:59.000Z",
      },
      requested_by: "USR-REG-4412",
      output_format: "application/pdf",
      include_kriging_risk_maps: true,
      include_audit_trail: true,
    },
  };

  // Switch active contract
  const handleSelectContract = (key: "14.1" | "14.2" | "14.3") => {
    setActiveContract(key);
    setPayloadText(JSON.stringify(CANONICAL_PAYLOADS[key], null, 2));
    setValidationResult(null);
  };

  React.useEffect(() => {
    setPayloadText(JSON.stringify(CANONICAL_PAYLOADS["14.1"], null, 2));
  }, []);

  const handleValidate = async () => {
    setIsValidating(true);
    try {
      const parsed = JSON.parse(payloadText);
      const endpoint =
        activeContract === "14.1"
          ? "/contracts/validate/14.1-telemetry"
          : activeContract === "14.2"
          ? "/contracts/validate/14.2-alert"
          : "/contracts/validate/14.3-dgms-report";

      const res = await fetchApi(endpoint, {
        method: "POST",
        body: JSON.stringify(parsed),
      });

      setValidationResult(res);
    } catch (err: any) {
      setValidationResult({
        valid: false,
        error: err.message,
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(payloadText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Header */}
      <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-xl flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-cyan-950 text-cyan-400 border border-cyan-800">
            <FileCode2 className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white uppercase tracking-wider">
              Data Contracts &amp; Schema Validation Engine
            </h2>
            <p className="text-xs text-slate-300">
              Shared TypeScript Types &amp; Zod Runtime Backend Validators (Contracts 14.1, 14.2, 14.3)
            </p>
          </div>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800">
          <button
            id="tab-contract-14-1"
            onClick={() => handleSelectContract("14.1")}
            className={`px-3 py-1.5 rounded font-bold transition-colors ${
              activeContract === "14.1" ? "bg-cyan-500 text-slate-950" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            14.1 Telemetry
          </button>
          <button
            id="tab-contract-14-2"
            onClick={() => handleSelectContract("14.2")}
            className={`px-3 py-1.5 rounded font-bold transition-colors ${
              activeContract === "14.2" ? "bg-cyan-500 text-slate-950" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            14.2 Alert Lifecycle
          </button>
          <button
            id="tab-contract-14-3"
            onClick={() => handleSelectContract("14.3")}
            className={`px-3 py-1.5 rounded font-bold transition-colors ${
              activeContract === "14.3" ? "bg-cyan-500 text-slate-950" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            14.3 DGMS Report
          </button>
        </div>
      </div>

      {/* Editor & Validation Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* JSON Editor */}
        <div className="lg:col-span-7 bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-slate-300 font-bold uppercase">
              Payload Payload Buffer (JSON):
            </span>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-slate-400 hover:text-slate-200"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>

          <textarea
            value={payloadText}
            onChange={(e) => setPayloadText(e.target.value)}
            rows={17}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500"
          />

          <button
            id="btn-validate-contract"
            onClick={handleValidate}
            disabled={isValidating}
            className="w-full py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg transition-colors"
          >
            <Send className="w-4 h-4" />
            {isValidating ? "Validating against Zod Schema..." : "Test Validation with Fastify BFF"}
          </button>
        </div>

        {/* Validation Result Box */}
        <div className="lg:col-span-5 bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="border-b border-slate-800 pb-2 font-bold text-slate-300 uppercase">
            BFF Validation Response:
          </div>

          {validationResult ? (
            <div
              className={`p-4 rounded-lg border space-y-2 ${
                validationResult.valid
                  ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
                  : "bg-red-950/40 border-red-800 text-red-300"
              }`}
            >
              <div className="flex items-center gap-2 font-bold text-sm">
                {validationResult.valid ? (
                  <>
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span>Schema Validation Passed</span>
                  </>
                ) : (
                  <>
                    <AlertOctagon className="w-5 h-5 text-red-400" />
                    <span>Schema Validation Rejected</span>
                  </>
                )}
              </div>

              <div className="text-[11px] text-slate-300">
                {validationResult.valid ? (
                  <div>
                    Validated against contract: <span className="font-bold">{validationResult.contract}</span>
                    <div className="mt-2 p-2 bg-slate-900/90 rounded border border-emerald-900/60 overflow-x-auto text-slate-200">
                      <pre>{JSON.stringify(validationResult.validated_payload, null, 2)}</pre>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <div>Error details:</div>
                    <pre className="p-2 bg-slate-900/90 rounded border border-red-900/60 text-red-300 overflow-x-auto">
                      {JSON.stringify(validationResult.errors || validationResult.error, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-500 font-mono">
              Click &quot;Test Validation with Fastify BFF&quot; to execute schema validation against the backend Zod contract.
            </div>
          )}

          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="font-bold text-slate-300">Contract Integrity Guarantee:</div>
            <div>• Real-time node telemetry &amp; health (14.1) broadcasts via WebSocket.</div>
            <div>• Alert lifecycle event (14.2) enforces state machine &amp; audible ack.</div>
            <div>• DGMS statutory report (14.3) binds to S3 path isolation &amp; audit signing.</div>
          </div>
        </div>
      </div>
    </div>
  );
};
