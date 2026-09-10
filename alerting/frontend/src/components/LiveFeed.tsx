import React, { useState, useEffect } from 'react';
import { Clock, AlertTriangle, ChevronRight, Activity, Cpu } from 'lucide-react';
import { AlertRecord, AlertSeverity, AlertStatus } from '../types';

interface LiveFeedProps {
  alerts: AlertRecord[];
  onSelectAlert: (alert: AlertRecord) => void;
}

/**
 * Client-side ticking countdown component:
 * Computes remaining seconds based on initial time_to_critical_hours and createdAt,
 * ticking down every second to display real-time urgency.
 */
const TickingCountdown: React.FC<{ ttcHours: number | null; createdAt: string }> = ({
  ttcHours,
  createdAt
}) => {
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(() => {
    if (ttcHours === null || ttcHours === undefined) return null;
    const elapsedSeconds = (Date.now() - new Date(createdAt).getTime()) / 1000;
    const totalTtcSeconds = ttcHours * 3600;
    return Math.max(0, Math.floor(totalTtcSeconds - elapsedSeconds));
  });

  useEffect(() => {
    if (ttcHours === null || ttcHours === undefined) return;

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev === null || prev <= 0) return 0;
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [ttcHours, createdAt]);

  if (secondsRemaining === null) {
    return <span style={{ color: 'var(--text-muted)' }}>TTC: N/A</span>;
  }

  if (secondsRemaining <= 0) {
    return (
      <span style={{ color: '#ef4444', fontWeight: 700 }}>
        CRITICAL TIMEOUT EXPIRED
      </span>
    );
  }

  const hours = Math.floor(secondsRemaining / 3600);
  const minutes = Math.floor((secondsRemaining % 3600) / 60);
  const seconds = secondsRemaining % 60;

  const isEmergency = hours < 6;
  const isWarning = hours < 24;

  const color = isEmergency ? '#ef4444' : isWarning ? '#f59e0b' : '#38bdf8';

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: '0.8rem',
      color,
      background: 'rgba(0,0,0,0.3)',
      padding: '3px 8px',
      borderRadius: '6px',
      border: `1px solid ${color}40`
    }}>
      <Clock size={13} className={isEmergency ? 'animate-pulse' : ''} />
      <span>
        {String(hours).padStart(2, '0')}h {String(minutes).padStart(2, '0')}m {String(seconds).padStart(2, '0')}s
      </span>
    </div>
  );
};

export const LiveFeed: React.FC<LiveFeedProps> = ({ alerts, onSelectAlert }) => {
  // Sort newest on top
  const sortedAlerts = [...alerts].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="glass-panel" style={{ padding: '18px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={18} color="var(--critical-red)" />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Live Telemetry Stream</h2>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          {sortedAlerts.length} Active Events
        </span>
      </div>

      <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '10px', paddingRight: '4px' }}>
        {sortedAlerts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            No active strata deformation events detected. Sensors healthy.
          </div>
        ) : (
          sortedAlerts.map((alert) => {
            const isCritical = alert.severity === AlertSeverity.Critical;
            const isWarning = alert.severity === AlertSeverity.Warning;
            const borderColor = isCritical ? 'rgba(239, 68, 68, 0.4)' : isWarning ? 'rgba(245, 158, 11, 0.3)' : 'rgba(56, 189, 248, 0.2)';
            const bgGlow = isCritical ? 'rgba(239, 68, 68, 0.08)' : isWarning ? 'rgba(245, 158, 11, 0.05)' : 'rgba(15, 23, 42, 0.6)';

            return (
              <div
                key={alert.alert_id}
                onClick={() => onSelectAlert(alert)}
                style={{
                  background: bgGlow,
                  border: `1px solid ${borderColor}`,
                  borderRadius: '10px',
                  padding: '14px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
                onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      color: '#ffffff',
                      background: isCritical ? '#dc2626' : isWarning ? '#d97706' : '#0284c7',
                      boxShadow: isCritical ? '0 0 10px rgba(239, 68, 68, 0.5)' : undefined
                    }}>
                      {alert.severity}
                    </span>

                    {alert.status === AlertStatus.Escalated && (
                      <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: 'rgba(239, 68, 68, 0.2)',
                        color: '#f87171',
                        border: '1px solid rgba(239, 68, 68, 0.4)'
                      }}>
                        AUTO-ESCALATED
                      </span>
                    )}

                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      Confidence: <b>{alert.explainability?.composite_confidence || `${(alert.confidence_score * 100).toFixed(0)}%`}</b>
                    </span>
                  </div>

                  {/* Real-time Ticking Countdown */}
                  <TickingCountdown
                    ttcHours={alert.explainability?.time_to_critical_hours ?? alert.time_to_critical_hours}
                    createdAt={alert.created_at}
                  />
                </div>

                {/* Narrative text */}
                <p style={{
                  fontSize: '0.85rem',
                  color: 'var(--text-primary)',
                  marginBottom: '10px',
                  lineHeight: 1.4
                }}>
                  {alert.explainability?.trigger_narrative || alert.explanation}
                </p>

                {/* Contributing Sensor Attribution Badges */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <Cpu size={14} color="var(--text-muted)" />
                    {alert.explainability?.contributing_sensor_attribution?.slice(0, 3).map((attr, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: '0.7rem',
                          background: 'rgba(255, 255, 255, 0.06)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '4px',
                          padding: '2px 6px',
                          color: '#cbd5e1',
                          fontFamily: 'var(--font-mono)'
                        }}
                      >
                        {attr.node_id.substring(0, 7)}: <b>{attr.reading}</b> ({attr.modality})
                      </span>
                    )) || (
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {alert.contributing_nodes?.length || 0} nodes correlated
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    <span>Inspect</span>
                    <ChevronRight size={14} />
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
