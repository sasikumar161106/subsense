import React, { useState, useEffect } from "react";
import { AlertLifecycleEvent } from "@subsense/shared";
import { fetchApi } from "../services/api";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../contexts/AuthContext";
import {
  Bell,
  CheckCircle2,
  AlertTriangle,
  Flame,
  HelpCircle,
  Clock,
  ShieldAlert,
  Volume2,
  FileCheck,
} from "lucide-react";

interface AlertLogViewProps {
  onAcknowledgeClick: (alert: AlertLifecycleEvent) => void;
  onFalseAlarmClick: (alert: AlertLifecycleEvent) => void;
  onResolveClick: (alert: AlertLifecycleEvent) => void;
  onSimulateDrill: (severity: "warning" | "critical") => void;
}

export const AlertLogView: React.FC<AlertLogViewProps> = ({
  onAcknowledgeClick,
  onFalseAlarmClick,
  onResolveClick,
  onSimulateDrill,
}) => {
  const { currentTenantId, currentSiteId } = useTenant();
  const { currentUser } = useAuth();

  const [alerts, setAlerts] = useState<AlertLifecycleEvent[]>([]);
  const [filterState, setFilterState] = useState<string>("all");
  const [auditLedger, setAuditLedger] = useState<any[]>([]);
  const [showAuditDrawer, setShowAuditDrawer] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const loadAlerts = async () => {
    setIsLoading(true);
    try {
      const res = await fetchApi(`/alerts?site_id=${currentSiteId}`, {
        tenantId: currentTenantId,
        userRole: currentUser.role,
        userId: currentUser.userId,
      });
      if (res.alerts) {
        setAlerts(res.alerts);
      }
    } catch (err) {
      console.error("Failed to load alerts:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadAuditLedger = async () => {
    try {
      const res = await fetchApi("/regulator/audit-ledger", {
        tenantId: currentTenantId,
        userRole: currentUser.role,
        userId: currentUser.userId,
      });
      if (res.audit_trail) {
        setAuditLedger(res.audit_trail);
      }
    } catch (err) {
      console.error("Failed to load audit ledger:", err);
    }
  };

  useEffect(() => {
    loadAlerts();
    loadAuditLedger();
    const interval = setInterval(loadAlerts, 4000);
    return () => clearInterval(interval);
  }, [currentTenantId, currentSiteId]);

  const filteredAlerts = alerts.filter((a) => {
    if (filterState === "all") return true;
    return a.state === filterState;
  });

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800 font-mono">
        <div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <Bell className="w-4 h-4 text-red-400" />
            Closed-Loop Alert Lifecycle Management (Contract 14.2)
          </h2>
          <p className="text-[11px] text-slate-400 mt-0.5">
            State Machine: NEW → ACKNOWLEDGED → ESCALATED | RESOLVED | FALSE ALARM
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Filter buttons */}
          <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
            {["all", "new", "acknowledged", "escalated", "false_alarm", "resolved"].map((s) => (
              <button
                key={s}
                onClick={() => setFilterState(s)}
                className={`px-2.5 py-1 rounded capitalize font-mono text-[11px] transition-colors ${
                  filterState === s
                    ? "bg-slate-800 text-amber-400 font-bold"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {s.replace(/_/g, " ")}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowAuditDrawer(!showAuditDrawer)}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-mono flex items-center gap-1.5 border border-slate-700 transition-colors"
          >
            <FileCheck className="w-3.5 h-3.5 text-cyan-400" />
            {showAuditDrawer ? "Hide Audit Ledger" : "View Cryptographic Audit Ledger"}
          </button>
        </div>
      </div>

      {/* Audit Drawer if toggled */}
      {showAuditDrawer && (
        <div className="bg-slate-950 p-4 rounded-xl border border-cyan-800/60 font-mono text-xs space-y-3 animate-in fade-in duration-200">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-cyan-400 font-bold flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-cyan-400" />
              Tamper-Proof Audit Ledger (SHA-256 Chained Blocks)
            </span>
            <span className="text-[11px] text-slate-400">
              Verified Immutable • All Acks &amp; Sirens Signed
            </span>
          </div>

          <div className="max-h-60 overflow-y-auto space-y-2">
            {auditLedger.map((block) => (
              <div
                key={block.id}
                className="p-2.5 rounded bg-slate-900 border border-slate-800 text-[11px] space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-amber-400 font-bold">{block.action}</span>
                  <span className="text-slate-400">{new Date(block.timestamp).toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span>Signer: {block.user_id}</span>
                  <span className="text-slate-500">Tenant: {block.tenant_id}</span>
                </div>
                <div className="text-[10px] text-slate-500 truncate">
                  SHA256: <span className="text-slate-400">{block.record_hash}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alert Lifecycle Events Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80">
        <table className="w-full text-left border-collapse text-xs font-mono">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/90 text-slate-400 uppercase text-[11px]">
              <th className="py-3 px-3.5">Alert ID &amp; Raised At</th>
              <th className="py-3 px-3">Severity</th>
              <th className="py-3 px-3">State</th>
              <th className="py-3 px-3">Location / Zone</th>
              <th className="py-3 px-3">Time to Critical</th>
              <th className="py-3 px-3">AI Explanation</th>
              <th className="py-3 px-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredAlerts.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-slate-500">
                  No alerts match the selected state filter.
                </td>
              </tr>
            ) : (
              filteredAlerts.map((alert) => {
                const isCrit = alert.severity === "critical";
                return (
                  <tr key={alert.alert_id} className="hover:bg-slate-900/50 transition-colors">
                    <td className="py-3 px-3.5">
                      <div className="font-bold text-slate-200">{alert.alert_id}</div>
                      <div className="text-[10px] text-slate-400">
                        {new Date(alert.raised_at).toLocaleString()}
                      </div>
                    </td>

                    <td className="py-3 px-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          isCrit
                            ? "bg-red-950 text-red-300 border border-red-800"
                            : alert.severity === "warning"
                            ? "bg-amber-950 text-amber-300 border border-amber-800"
                            : "bg-blue-950 text-blue-300 border border-blue-800"
                        }`}
                      >
                        {isCrit && <Flame className="w-3 h-3 text-red-400" />}
                        {alert.severity}
                      </span>
                    </td>

                    <td className="py-3 px-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[10px] uppercase font-bold ${
                          alert.state === "new"
                            ? "bg-red-950/80 text-red-300 border border-red-700 animate-pulse"
                            : alert.state === "acknowledged"
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                            : alert.state === "escalated"
                            ? "bg-purple-950 text-purple-300 border border-purple-700 animate-pulse"
                            : alert.state === "false_alarm"
                            ? "bg-slate-800 text-slate-300 border border-slate-700"
                            : "bg-blue-950 text-blue-300 border border-blue-700"
                        }`}
                      >
                        {alert.state.replace(/_/g, " ")}
                      </span>
                      {alert.acknowledged_by && (
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          Ack: {alert.acknowledged_by}
                        </div>
                      )}
                    </td>

                    <td className="py-3 px-3">
                      <div className="text-slate-200">{alert.site_id}</div>
                      <div className="text-[10px] text-slate-400">{alert.zone_id}</div>
                    </td>

                    <td className="py-3 px-3 font-bold text-amber-300">
                      {alert.time_to_critical_hours[0]}h – {alert.time_to_critical_hours[1]}h
                    </td>

                    <td className="py-3 px-3 max-w-xs text-slate-300 text-[11px]">
                      {alert.explanation_summary}
                      {alert.false_alarm_reason && (
                        <div className="text-[10px] text-purple-400 mt-1">
                          Reason: {alert.false_alarm_reason}
                        </div>
                      )}
                    </td>

                    <td className="py-3 px-3.5 text-right space-x-1.5">
                      {alert.state === "new" && currentUser.role === "mine_operator" && (
                        <button
                          onClick={() => onAcknowledgeClick(alert)}
                          className="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold"
                        >
                          Acknowledge
                        </button>
                      )}
                      {alert.state !== "resolved" && alert.state !== "false_alarm" && currentUser.role === "mine_operator" && (
                        <>
                          <button
                            onClick={() => onFalseAlarmClick(alert)}
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-[11px]"
                          >
                            False Alarm
                          </button>
                          <button
                            onClick={() => onResolveClick(alert)}
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-emerald-400 text-[11px]"
                          >
                            Resolve
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
