import React, { useState } from 'react';
import { Download, Filter, Search, FileSpreadsheet } from 'lucide-react';
import { AlertRecord, AlertSeverity, AlertStatus, RiskZoneMetadata } from '../types';

interface HistoricalLogProps {
  alerts: AlertRecord[];
  zones: RiskZoneMetadata[];
  onSelectAlert: (alert: AlertRecord) => void;
  tenantId: string | null;
}

export const HistoricalLog: React.FC<HistoricalLogProps> = ({
  alerts,
  zones,
  onSelectAlert,
  tenantId
}) => {
  const [selectedZone, setSelectedZone] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [exporting, setExporting] = useState(false);

  // Filter alerts
  const filteredAlerts = alerts.filter((alert) => {
    if (selectedZone !== 'all' && alert.risk_zone_id !== selectedZone) return false;
    if (selectedSeverity !== 'all' && alert.severity !== selectedSeverity) return false;
    if (selectedStatus !== 'all' && alert.status !== selectedStatus) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const narrative = (alert.explainability?.trigger_narrative || alert.explanation || '').toLowerCase();
      const zoneId = alert.risk_zone_id.toLowerCase();
      if (!narrative.includes(q) && !zoneId.includes(q)) return false;
    }
    return true;
  });

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const token = localStorage.getItem('subsense_jwt_token');
      const url = new URL('http://localhost:3000/api/v1/audit/export');
      if (tenantId) url.searchParams.set('tenant_id', tenantId);

      const res = await fetch(url.toString(), {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });

      if (!res.ok) throw new Error('Failed to export CSV');

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `dgms_annual_safety_audit_${tenantId || 'all'}_${Date.now()}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: any) {
      console.error('Audit export failed:', err);
      alert('Failed to export DGMS safety audit CSV: ' + err.message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Top action bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileSpreadsheet size={18} color="#38bdf8" />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Historical Subsidence Audit Log</h2>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            ({filteredAlerts.length} records)
          </span>
        </div>

        {/* One-Click DGMS CSV Export Button */}
        <button
          onClick={handleExportCsv}
          disabled={exporting}
          style={{
            background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            padding: '8px 16px',
            fontSize: '0.8rem',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)'
          }}
          title="Extract official DGMS Annual Safety Audit Filings in CSV"
        >
          <Download size={15} />
          <span>{exporting ? 'Generating CSV...' : 'One-Click DGMS Audit Export (CSV)'}</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        marginBottom: '14px',
        flexWrap: 'wrap',
        background: 'rgba(0,0,0,0.2)',
        padding: '10px 12px',
        borderRadius: '8px',
        border: '1px solid var(--border-subtle)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, minWidth: '180px' }}>
          <Search size={14} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search narrative or zone..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              background: 'transparent',
              border: 'none',
              color: '#f8fafc',
              fontSize: '0.8rem',
              outline: 'none'
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Zone:</span>
          <select
            value={selectedZone}
            onChange={(e) => setSelectedZone(e.target.value)}
            style={{
              background: '#090d16',
              color: '#cbd5e1',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              padding: '4px 8px',
              fontSize: '0.75rem'
            }}
          >
            <option value="all">All Zones</option>
            {zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.zone_name}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Severity:</span>
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            style={{
              background: '#090d16',
              color: '#cbd5e1',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              padding: '4px 8px',
              fontSize: '0.75rem'
            }}
          >
            <option value="all">All</option>
            <option value={AlertSeverity.Critical}>Critical</option>
            <option value={AlertSeverity.Warning}>Warning</option>
            <option value={AlertSeverity.Advisory}>Advisory</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status:</span>
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            style={{
              background: '#090d16',
              color: '#cbd5e1',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              padding: '4px 8px',
              fontSize: '0.75rem'
            }}
          >
            <option value="all">All</option>
            <option value={AlertStatus.Active}>Active</option>
            <option value={AlertStatus.Escalated}>Escalated</option>
            <option value={AlertStatus.Retracted}>Retracted</option>
            <option value={AlertStatus.Resolved}>Resolved</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowY: 'auto', flex: 1, border: '1px solid var(--border-subtle)', borderRadius: '8px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: 'rgba(255, 255, 255, 0.04)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
              <th style={{ padding: '10px 14px' }}>Timestamp</th>
              <th style={{ padding: '10px 14px' }}>Risk Zone</th>
              <th style={{ padding: '10px 14px' }}>Severity</th>
              <th style={{ padding: '10px 14px' }}>Status</th>
              <th style={{ padding: '10px 14px' }}>Confidence</th>
              <th style={{ padding: '10px 14px' }}>TTC</th>
              <th style={{ padding: '10px 14px' }}>Trigger Narrative</th>
              <th style={{ padding: '10px 14px', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredAlerts.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No matching historical records found.
                </td>
              </tr>
            ) : (
              filteredAlerts.map((alert) => {
                const zone = zones.find((z) => z.zone_id === alert.risk_zone_id);
                const zoneName = zone?.zone_name || alert.risk_zone_id.substring(0, 8);

                return (
                  <tr
                    key={alert.alert_id}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.03)',
                      transition: 'background 0.15s ease'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {new Date(alert.created_at).toLocaleDateString()} {new Date(alert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: '#f8fafc' }}>
                      {zoneName}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        color: '#ffffff',
                        background: alert.severity === 'Critical' ? '#dc2626' : alert.severity === 'Warning' ? '#d97706' : '#0284c7'
                      }}>
                        {alert.severity}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        color: alert.status === 'Retracted' ? '#94a3b8' : alert.status === 'Escalated' ? '#f87171' : '#34d399'
                      }}>
                        {alert.status}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)' }}>
                      {alert.explainability?.composite_confidence || `${(alert.confidence_score * 100).toFixed(0)}%`}
                    </td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', color: alert.time_to_critical_hours && alert.time_to_critical_hours < 6 ? '#ef4444' : '#f59e0b' }}>
                      {alert.time_to_critical_hours ? `${alert.time_to_critical_hours.toFixed(1)}h` : 'N/A'}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#cbd5e1', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {alert.explainability?.trigger_narrative || alert.explanation}
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                      <button
                        onClick={() => onSelectAlert(alert)}
                        style={{
                          background: 'rgba(255, 255, 255, 0.08)',
                          color: '#f8fafc',
                          border: 'none',
                          borderRadius: '4px',
                          padding: '4px 10px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer'
                        }}
                      >
                        Inspect
                      </button>
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
