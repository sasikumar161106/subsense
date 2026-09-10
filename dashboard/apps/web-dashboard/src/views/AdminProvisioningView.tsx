import React, { useState } from "react";
import { fetchApi } from "../services/api";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../contexts/AuthContext";
import {
  Settings,
  PlusCircle,
  Database,
  CheckCircle,
  Server,
  Layers,
  KeyRound,
  ShieldAlert,
} from "lucide-react";

export const AdminProvisioningView: React.FC = () => {
  const { currentTenantId, refreshSites, availableSites } = useTenant();
  const { currentUser } = useAuth();

  const [siteId, setSiteId] = useState<string>("PANEL9-RANIGANJ");
  const [siteName, setSiteName] = useState<string>("Raniganj Panel 9 Highwall Expansion");
  const [seamDepth, setSeamDepth] = useState<number>(280);
  const [extractionMethod, setExtractionMethod] = useState<string>("longwall");
  const [gatewayEui, setGatewayEui] = useState<string>("GW-ECL-RN-009");
  const [nodeIdsInput, setNodeIdsInput] = useState<string>("SS-RANI-N091, SS-RANI-N092, SS-RANI-N093");
  const [isProvisioning, setIsProvisioning] = useState<boolean>(false);
  const [result, setResult] = useState<any>(null);

  const handleProvision = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProvisioning(true);
    try {
      const nodeIds = nodeIdsInput
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      const payload = {
        site_id: siteId,
        name: siteName,
        seam_depth_meters: seamDepth,
        extraction_method: extractionMethod,
        gateway_credentials: {
          gateway_eui: gatewayEui,
          auth_key_hash: "SHA256-GW-AUTH-KEY-2026-ACTIVE",
          protocol: "sub_ghz_mesh",
        },
        node_ids: nodeIds,
        boundaries_geojson: {
          type: "Polygon",
          coordinates: [
            [
              [87.15, 23.63],
              [87.16, 23.63],
              [87.16, 23.64],
              [87.15, 23.64],
              [87.15, 23.63],
            ],
          ],
        },
      };

      const res = await fetchApi(`/tenants/${currentTenantId}/sites`, {
        method: "POST",
        body: JSON.stringify(payload),
        tenantId: currentTenantId,
        userRole: currentUser.role,
        userId: currentUser.userId,
      });

      setResult(res);
      await refreshSites();
    } catch (err: any) {
      alert(`Provisioning failed: ${err.message}`);
    } finally {
      setIsProvisioning(false);
    }
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Admin Header */}
      <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-xl flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-slate-800 text-amber-400 border border-slate-700">
            <Settings className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white uppercase tracking-wider">
              Zero-Downtime Mining Panel Provisioning
            </h2>
            <p className="text-xs text-slate-300">
              Tenant: {currentTenantId} • Dynamic DB Metadata Injection (Zero Server Restart)
            </p>
          </div>
        </div>

        <div className="bg-amber-950/50 border border-amber-800/60 px-3 py-1.5 rounded-lg text-amber-300">
          Signed Administrator Session: {currentUser.userId}
        </div>
      </div>

      {/* Provisioning Form & Existing Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Form: Provisioning Parameters */}
        <div className="lg:col-span-7 bg-slate-950 p-5 rounded-xl border border-slate-800 space-y-4">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide flex items-center gap-2 border-b border-slate-800 pb-3">
            <PlusCircle className="w-4 h-4 text-cyan-400" />
            Panel Onboarding Metadata Specification
          </h3>

          <form onSubmit={handleProvision} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-slate-400 mb-1 font-medium">Panel Identifier (site_id):</label>
                <input
                  type="text"
                  value={siteId}
                  onChange={(e) => setSiteId(e.target.value.toUpperCase())}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-bold focus:outline-none focus:border-amber-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Sector Name:</label>
                <input
                  type="text"
                  value={siteName}
                  onChange={(e) => setSiteName(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 focus:outline-none focus:border-amber-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Seam Depth (Meters):</label>
                <input
                  type="number"
                  value={seamDepth}
                  onChange={(e) => setSeamDepth(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 focus:outline-none focus:border-amber-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Extraction Method:</label>
                <select
                  value={extractionMethod}
                  onChange={(e) => setExtractionMethod(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 focus:outline-none focus:border-amber-500"
                >
                  <option value="longwall">Longwall Retreating</option>
                  <option value="bord_and_pillar">Bord and Pillar (Continuous Miner)</option>
                  <option value="opencast">Opencast Highwall</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Mesh Gateway EUI:</label>
                <input
                  type="text"
                  value={gatewayEui}
                  onChange={(e) => setGatewayEui(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-bold focus:outline-none focus:border-amber-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Deployed Mesh Node IDs:</label>
                <input
                  type="text"
                  value={nodeIdsInput}
                  onChange={(e) => setNodeIdsInput(e.target.value)}
                  placeholder="SS-RANI-N091, SS-RANI-N092"
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 focus:outline-none focus:border-amber-500"
                  required
                />
              </div>
            </div>

            <button
              id="btn-submit-provisioning"
              type="submit"
              disabled={isProvisioning}
              className="w-full py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-amber-950 transition-colors"
            >
              <Database className="w-4 h-4" />
              {isProvisioning ? "Injecting Metadata into PostgreSQL..." : "Provision Panel with Zero Downtime"}
            </button>
          </form>

          {/* Provisioning Confirmation Result */}
          {result && (
            <div className="p-3.5 bg-emerald-950/60 border border-emerald-800 rounded-lg space-y-1.5 animate-in fade-in">
              <div className="text-emerald-300 font-bold flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4" />
                {result.message}
              </div>
              <div className="text-slate-300">
                Isolated S3 Report Prefix: <span className="text-cyan-400">{result.s3_storage?.report_prefix}</span>
              </div>
              <div className="text-[10px] text-slate-400">
                Audit Signature: {result.audit_signature}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Currently Provisioned Panels in Tenant Scope */}
        <div className="lg:col-span-5 bg-slate-950 p-5 rounded-xl border border-slate-800 space-y-3">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide flex items-center gap-2 border-b border-slate-800 pb-3">
            <Server className="w-4 h-4 text-emerald-400" />
            Live Provisioned Panels ({currentTenantId})
          </h3>

          <div className="space-y-2.5 max-h-[440px] overflow-y-auto">
            {availableSites.map((site) => (
              <div
                key={site.id}
                className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-100">{site.id}</span>
                  <span className="text-[10px] bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded uppercase font-bold">
                    {site.status}
                  </span>
                </div>
                <div className="text-slate-300">{site.name}</div>
                <div className="text-[10px] text-slate-500">
                  Nodes: {site.node_ids?.join(", ")}
                </div>
                <div className="text-[10px] text-cyan-400 truncate">
                  S3: {site.s3_report_prefix}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
