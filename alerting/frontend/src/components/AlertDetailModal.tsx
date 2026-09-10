import React, { useState, useEffect } from 'react';
import { X, CheckCircle, AlertTriangle, Shield, Radio, RotateCcw, Hash, Send, FileText } from 'lucide-react';
import {
  AlertRecord,
  AlertSeverity,
  AlertStatus,
  AlertDeliveryRecord,
  FeedbackVerdict,
  UserContext,
  UserRole
} from '../types';

interface AlertDetailModalProps {
  alert: AlertRecord | null;
  user: UserContext | null;
  onClose: () => void;
  onFeedbackSubmitted: (updatedAlert: AlertRecord) => void;
}

export const AlertDetailModal: React.FC<AlertDetailModalProps> = ({
  alert,
  user,
  onClose,
  onFeedbackSubmitted
}) => {
  const [deliveries, setDeliveries] = useState<AlertDeliveryRecord[]>([]);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);

  const [verdict, setVerdict] = useState<FeedbackVerdict>(FeedbackVerdict.Confirmed);
  const [notes, setNotes] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const [retractionReason, setRetractionReason] = useState('');
  const [submittingRetract, setSubmittingRetract] = useState(false);
  const [retractError, setRetractError] = useState<string | null>(null);

  // Fetch per-channel deliveries from GET /api/v1/alerts/{id}/deliveries
  useEffect(() => {
    if (!alert) return;

    setLoadingDeliveries(true);
    const token = localStorage.getItem('subsense_jwt_token');

    fetch(`http://localhost:3000/api/v1/alerts/${alert.alert_id}/deliveries`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setDeliveries(data);
        }
      })
      .catch((err) => console.error('Failed to fetch deliveries:', err))
      .finally(() => setLoadingDeliveries(false));
  }, [alert]);

  if (!alert) return null;

  const isReadOnlyRegulator = user?.role === UserRole.RegulatorDGMS;
  const feedbacks = alert.feedbacks || [];
  const latestFeedback = feedbacks[feedbacks.length - 1];

  // Enforced safety condition: Alert can only be retracted after FalsePositive or HardwareDefect verdict
  const canRetract =
    alert.status !== AlertStatus.Retracted &&
    feedbacks.some(
      (f) =>
        f.verdict === FeedbackVerdict.FalsePositive ||
        f.verdict === FeedbackVerdict.HardwareDefect
    );

  const handleSubmitFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingFeedback(true);
    setFeedbackError(null);

    const token = localStorage.getItem('subsense_jwt_token');

    try {
      const res = await fetch(`http://localhost:3000/api/v1/alerts/${alert.alert_id}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          operator_id: user?.user_id || 'usr-operator-demo',
          verdict,
          notes
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to submit feedback');
      }

      onFeedbackSubmitted(data.alert);
      setNotes('');
    } catch (err: any) {
      setFeedbackError(err.message);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleRetractAlert = async () => {
    if (!canRetract) return;
    setSubmittingRetract(true);
    setRetractError(null);

    const token = localStorage.getItem('subsense_jwt_token');

    try {
      const res = await fetch(`http://localhost:3000/api/v1/alerts/${alert.alert_id}/retract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          operator_id: user?.user_id || 'usr-operator-demo',
          reason: retractionReason || 'False alarm verified by operator feedback'
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to retract alert');
      }

      onFeedbackSubmitted(data.alert);
    } catch (err: any) {
      setRetractError(err.message);
    } finally {
      setSubmittingRetract(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ padding: '24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px', marginBottom: '20px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{
                fontSize: '0.85rem',
                fontWeight: 800,
                textTransform: 'uppercase',
                padding: '4px 10px',
                borderRadius: '6px',
                color: '#fff',
                background: alert.severity === 'Critical' ? '#dc2626' : alert.severity === 'Warning' ? '#d97706' : '#0284c7'
              }}>
                {alert.severity}
              </span>
              <span style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '6px',
                background: alert.status === 'Retracted' ? 'rgba(148, 163, 184, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                color: alert.status === 'Retracted' ? '#94a3b8' : '#34d399'
              }}>
                STATUS: {alert.status.toUpperCase()}
              </span>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                ID: {alert.alert_id.substring(0, 13)}...
              </span>
            </div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
              {alert.explainability?.trigger_narrative || alert.explanation}
            </h2>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '4px'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Section 1: Full AI/ML Explainability Breakdown */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '10px' }}>
            AI/ML Explainability & Attributed Modalities
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '14px' }}>
            <div className="glass-panel" style={{ padding: '12px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Composite Confidence</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#38bdf8' }}>
                {alert.explainability?.composite_confidence || `${(alert.confidence_score * 100).toFixed(0)}%`}
              </div>
            </div>

            <div className="glass-panel" style={{ padding: '12px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Estimated Time To Critical</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: alert.time_to_critical_hours && alert.time_to_critical_hours < 6 ? '#ef4444' : '#f59e0b', fontFamily: 'var(--font-mono)' }}>
                {alert.explainability?.time_to_critical_hours !== null && alert.explainability?.time_to_critical_hours !== undefined
                  ? `${alert.explainability.time_to_critical_hours.toFixed(1)} hrs`
                  : alert.time_to_critical_hours
                  ? `${alert.time_to_critical_hours.toFixed(1)} hrs`
                  : 'Extrapolated'}
              </div>
            </div>

            <div className="glass-panel" style={{ padding: '12px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Correlated Sensors</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#34d399' }}>
                {alert.contributing_nodes?.length || 0} Nodes Correlated
              </div>
            </div>
          </div>

          {/* Sensor Attribution Table */}
          {alert.explainability?.contributing_sensor_attribution && alert.explainability.contributing_sensor_attribution.length > 0 && (
            <div style={{ background: 'rgba(0,0,0,0.25)', borderRadius: '8px', border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
                    <th style={{ padding: '8px 12px' }}>Sensor Node ID</th>
                    <th style={{ padding: '8px 12px' }}>Measurement Modality</th>
                    <th style={{ padding: '8px 12px' }}>Engineering Reading</th>
                  </tr>
                </thead>
                <tbody>
                  {alert.explainability.contributing_sensor_attribution.map((attr, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)' }}>{attr.node_id}</td>
                      <td style={{ padding: '8px 12px', textTransform: 'capitalize' }}>{attr.modality}</td>
                      <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#f8fafc' }}>
                        {attr.reading}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Section 2: Per-Channel Omni-Delivery Matrix */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '10px' }}>
            Per-Channel Delivery Audit Trail
          </h3>

          {loadingDeliveries ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Loading delivery rows...</div>
          ) : deliveries.length === 0 ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No delivery records recorded.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
              {deliveries.map((del) => {
                const isSiren = del.channel === 'Siren';
                const isSent = del.delivery_status === 'Sent' || del.delivery_status === 'Delivered';

                return (
                  <div
                    key={del.delivery_id}
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '8px',
                      padding: '10px 12px',
                      fontSize: '0.75rem'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 700, color: '#f8fafc' }}>{del.channel}</span>
                      <span style={{
                        fontWeight: 700,
                        color: isSent ? '#34d399' : '#f87171',
                        fontSize: '0.7rem'
                      }}>
                        {del.delivery_status}
                      </span>
                    </div>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                      {del.recipient_ref}
                    </div>
                    {isSiren && (
                      <div style={{ color: '#38bdf8', fontWeight: 600, fontSize: '0.68rem', marginTop: '2px' }}>
                        Autonomous Edge GPIO (&lt; 1.2s)
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Section 3: Closed-Loop Operator Feedback Form */}
        <div className="glass-panel" style={{ padding: '16px', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={16} color="#38bdf8" />
            <span>Operator Feedback Verdict (Cryptographically Linked)</span>
          </h3>

          {latestFeedback && (
            <div style={{ background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '8px', padding: '10px 12px', marginBottom: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Latest Verdict on File:</span>
                <span style={{ fontWeight: 800, color: '#38bdf8' }}>{latestFeedback.verdict}</span>
              </div>
              {latestFeedback.notes && (
                <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginBottom: '4px' }}>
                  Notes: "{latestFeedback.notes}"
                </div>
              )}
              {latestFeedback.feedback_hash && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  <Hash size={12} />
                  <span>SHA-256: {latestFeedback.feedback_hash}</span>
                </div>
              )}
            </div>
          )}

          {isReadOnlyRegulator ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              Regulator / DGMS mode active: Read-only access to feedback audit trail.
            </div>
          ) : (
            <form onSubmit={handleSubmitFeedback}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '8px', marginBottom: '12px' }}>
                {[
                  { value: FeedbackVerdict.Confirmed, label: 'Confirmed Ground Movement', color: '#10b981' },
                  { value: FeedbackVerdict.FalsePositive, label: 'False Positive (Noise/Blasting)', color: '#f59e0b' },
                  { value: FeedbackVerdict.HardwareDefect, label: 'Hardware Sensor Defect', color: '#ef4444' },
                  { value: FeedbackVerdict.Unclear, label: 'Unclear / Investigating', color: '#64748b' }
                ].map((option) => (
                  <label
                    key={option.value}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 10px',
                      background: verdict === option.value ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.2)',
                      border: verdict === option.value ? `1px solid ${option.color}` : '1px solid var(--border-subtle)',
                      borderRadius: '8px',
                      fontSize: '0.75rem',
                      cursor: 'pointer'
                    }}
                  >
                    <input
                      type="radio"
                      name="verdict"
                      value={option.value}
                      checked={verdict === option.value}
                      onChange={() => setVerdict(option.value)}
                    />
                    <span style={{ fontWeight: verdict === option.value ? 700 : 500, color: option.color }}>
                      {option.label}
                    </span>
                  </label>
                ))}
              </div>

              <div style={{ marginBottom: '12px' }}>
                <input
                  type="text"
                  placeholder="Operator notes (e.g., adjacent blasting confirmed at seam bench 4)..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  style={{
                    width: '100%',
                    background: '#090d16',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '8px 12px',
                    color: '#f8fafc',
                    fontSize: '0.8rem',
                    outline: 'none'
                  }}
                />
              </div>

              {feedbackError && (
                <div style={{ color: '#ef4444', fontSize: '0.75rem', marginBottom: '10px' }}>
                  {feedbackError}
                </div>
              )}

              <button
                type="submit"
                disabled={submittingFeedback}
                style={{
                  background: '#0284c7',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '8px 16px',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <Send size={14} />
                <span>{submittingFeedback ? 'Logging Feedback...' : 'Submit & Sign Feedback'}</span>
              </button>
            </form>
          )}
        </div>

        {/* Section 4: Retraction Notice Guard & Fanout */}
        {alert.status !== AlertStatus.Retracted && (
          <div style={{
            background: canRetract ? 'rgba(239, 68, 68, 0.08)' : 'rgba(255,255,255,0.02)',
            border: canRetract ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid var(--border-subtle)',
            borderRadius: '12px',
            padding: '16px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <RotateCcw size={16} color={canRetract ? '#ef4444' : 'var(--text-muted)'} />
                <span style={{ fontWeight: 700, fontSize: '0.9rem', color: canRetract ? '#f87171' : 'var(--text-muted)' }}>
                  De-Escalate & Retract Alert Notice
                </span>
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {canRetract ? 'Ready: False Alarm Verdict On File' : 'Locked: Requires FalsePositive/HardwareDefect'}
              </span>
            </div>

            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
              Enforced Safety Guard: Once retracted, a <b>Retraction Notice</b> will immediately be dispatched across
              EVERY channel originally utilized (SMS, Push, Email, Dashboard Banner) to cancel evacuation orders.
            </p>

            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                type="text"
                placeholder="Retraction reason for DGMS compliance..."
                value={retractionReason}
                onChange={(e) => setRetractionReason(e.target.value)}
                disabled={!canRetract || isReadOnlyRegulator}
                style={{
                  flex: 1,
                  background: '#090d16',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  color: '#f8fafc',
                  fontSize: '0.8rem',
                  outline: 'none'
                }}
              />

              <button
                onClick={handleRetractAlert}
                disabled={!canRetract || submittingRetract || isReadOnlyRegulator}
                style={{
                  background: canRetract ? '#dc2626' : 'rgba(255,255,255,0.08)',
                  color: canRetract ? '#ffffff' : 'var(--text-muted)',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '8px 18px',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: canRetract ? 'pointer' : 'not-allowed',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <RotateCcw size={14} />
                <span>{submittingRetract ? 'Dispatching Retraction...' : 'Retract Alert'}</span>
              </button>
            </div>

            {retractError && (
              <div style={{ color: '#ef4444', fontSize: '0.75rem', marginTop: '8px' }}>
                {retractError}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
