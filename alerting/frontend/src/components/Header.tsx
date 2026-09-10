import React from 'react';
import { Shield, Radio, Building2, UserCheck } from 'lucide-react';
import { UserContext, UserRole } from '../types';

interface HeaderProps {
  user: UserContext | null;
  wsConnected: boolean;
  onSwitchUser: (username: string, role: string) => void;
}

export const Header: React.FC<HeaderProps> = ({ user, wsConnected, onSwitchUser }) => {
  return (
    <header className="header-bar">
      <div className="brand-title">
        <div style={{
          background: 'linear-gradient(135deg, #ef4444 0%, #f59e0b 100%)',
          borderRadius: '10px',
          padding: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px rgba(239, 68, 68, 0.4)'
        }}>
          <Shield size={22} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1>SubSense Console</h1>
            <span className="badge-dgms">DGMS Compliant</span>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Real-Time Strata Control & Autonomous Subsidence Warning System
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
        {/* WebSocket Real-time Edge Channel Status */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 14px',
          borderRadius: '20px',
          background: wsConnected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.15)',
          border: wsConnected ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
          fontSize: '0.8rem',
          fontWeight: 600,
          color: wsConnected ? '#34d399' : '#f87171'
        }}>
          <Radio size={14} className={wsConnected ? 'animate-pulse' : ''} />
          <span>{wsConnected ? 'Edge WS Stream: LIVE' : 'Edge WS Stream: CONNECTING'}</span>
        </div>

        {/* Multi-Tenancy / RBAC Live Switcher for Judges */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '6px 12px',
          borderRadius: '10px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)'
        }}>
          <Building2 size={16} color="var(--text-secondary)" />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Demo Role:</span>
          <select
            value={user?.username || 'officer_jharia'}
            onChange={(e) => {
              const val = e.target.value;
              onSwitchUser(val, val === 'dgms_inspector' ? 'dgms2026' : 'subsense123');
            }}
            style={{
              background: '#090d16',
              color: '#f8fafc',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              padding: '4px 10px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none'
            }}
          >
            <option value="officer_jharia">Officer Jharia (Mine Safety Officer - Jharia Block II)</option>
            <option value="officer_raniganj">Officer Raniganj (Mine Safety Officer - Raniganj Complex)</option>
            <option value="dgms_inspector">DGMS Inspector (Regulator - Multi-Tenant Read-Only)</option>
          </select>
        </div>

        {/* Active User Pill */}
        {user && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            borderRadius: '8px',
            background: user.role === UserRole.RegulatorDGMS ? 'rgba(56, 189, 248, 0.15)' : 'rgba(245, 158, 11, 0.15)',
            border: user.role === UserRole.RegulatorDGMS ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid rgba(245, 158, 11, 0.3)',
            fontSize: '0.8rem'
          }}>
            <UserCheck size={14} color={user.role === UserRole.RegulatorDGMS ? '#38bdf8' : '#fbbf24'} />
            <div>
              <div style={{ fontWeight: 600, color: user.role === UserRole.RegulatorDGMS ? '#38bdf8' : '#fbbf24' }}>
                {user.role === UserRole.RegulatorDGMS ? 'Regulator / DGMS' : 'Mine Safety Officer'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {user.tenant_name || 'All Entitled Coalfields'}
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
