import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { SirenBanner } from './components/SirenBanner';
import { MineMap } from './components/Map';
import { LiveFeed } from './components/LiveFeed';
import { HistoricalLog } from './components/HistoricalLog';
import { AlertDetailModal } from './components/AlertDetailModal';
import {
  AlertRecord,
  AlertSeverity,
  EdgeSirenEvent,
  RiskZoneMetadata,
  UserContext,
  UserRole
} from './types';

const API_BASE = 'http://localhost:3000/api/v1';
const WS_URL = 'ws://localhost:3000/ws/alerts';

export const App: React.FC = () => {
  const [user, setUser] = useState<UserContext | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('subsense_jwt_token'));
  const [wsConnected, setWsConnected] = useState(false);

  const [zones, setZones] = useState<RiskZoneMetadata[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<AlertRecord | null>(null);

  const [activeSirenEvent, setActiveSirenEvent] = useState<EdgeSirenEvent | null>(null);

  // Authenticate user
  const handleLogin = useCallback(async (username: string, password: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (res.ok) {
        setUser(data.user);
        setToken(data.token);
        localStorage.setItem('subsense_jwt_token', data.token);
      }
    } catch (err) {
      console.error('Login failed:', err);
    }
  }, []);

  // Initialize with default demo user (Officer Jharia)
  useEffect(() => {
    handleLogin('officer_jharia', 'subsense123');
  }, [handleLogin]);

  // Fetch zones and alerts whenever user / token changes
  useEffect(() => {
    if (!token) return;

    // 1. Fetch entitled zones
    fetch(`${API_BASE}/auth/zones`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setZones(data);
      })
      .catch((err) => console.error('Failed to fetch zones:', err));

    // 2. Fetch entitled alerts
    fetch(`${API_BASE}/alerts`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setAlerts(data);
      })
      .catch((err) => console.error('Failed to fetch alerts:', err));
  }, [token, user]);

  // Connect to Phase 2 WebSocket feed
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWs = () => {
      try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
          console.log('[WEBSOCKET] Connected to SubSense alert bus');
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            // Handle pure edge siren event
            if (data.type === 'SIREN_ACTIVE' || data.event === 'siren_actuated') {
              console.log('[WEBSOCKET] Autonomous edge siren event received:', data);
              setActiveSirenEvent({
                type: 'SIREN_ACTIVATION',
                alert_id: data.alert_id || 'edge-trigger',
                zone_id: data.zone_id || data.risk_zone_id || 'zone-jharia-alpha',
                severity: AlertSeverity.Critical,
                source: 'EdgeAutonomousGPIO',
                timestamp: new Date().toISOString()
              });
              return;
            }

            // Handle incoming alert broadcast
            if (data.alert_id) {
              setAlerts((prev) => {
                // If alert already exists, update it; otherwise prepend
                const idx = prev.findIndex((a) => a.alert_id === data.alert_id);
                if (idx >= 0) {
                  const updated = [...prev];
                  updated[idx] = data;
                  return updated;
                }
                return [data, ...prev];
              });
            }
          } catch (err) {
            console.error('Error parsing WS message:', err);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = setTimeout(connectWs, 3000);
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch (err) {
        console.warn('WS connection attempt failed:', err);
        reconnectTimeout = setTimeout(connectWs, 3000);
      }
    };

    connectWs();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  const handleFeedbackSuccess = (updatedAlert: AlertRecord) => {
    setAlerts((prev) => prev.map((a) => (a.alert_id === updatedAlert.alert_id ? updatedAlert : a)));
    setSelectedAlert(updatedAlert);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Header */}
      <Header
        user={user}
        wsConnected={wsConnected}
        onSwitchUser={(uname, pwd) => handleLogin(uname, pwd)}
      />

      {/* Autonomous Edge Siren Emergency Banner (Pure WebSocket driven) */}
      <SirenBanner
        sirenEvent={activeSirenEvent}
        onDismiss={() => setActiveSirenEvent(null)}
      />

      {/* Main Dashboard Workspace */}
      <main style={{ flex: 1, padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Top Split: Leaflet Map & Live Feed */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '20px', minHeight: '440px' }}>
          <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ fontWeight: 700, fontSize: '1rem', color: '#f8fafc' }}>
                GIS Risk Zone Telemetry Map ({user?.tenant_name || 'Multi-Coalfield'})
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {zones.length} Strata Zones Monitored
              </span>
            </div>
            <div style={{ flex: 1, minHeight: '380px' }}>
              <MineMap
                zones={zones}
                activeAlerts={alerts}
                activeSirenZoneId={activeSirenEvent?.zone_id || null}
                onSelectAlert={(a) => setSelectedAlert(a)}
              />
            </div>
          </div>

          <div style={{ minHeight: '440px' }}>
            <LiveFeed
              alerts={alerts}
              onSelectAlert={(a) => setSelectedAlert(a)}
            />
          </div>
        </div>

        {/* Bottom Section: Historical Subsidence Log & CSV Export */}
        <div style={{ minHeight: '360px' }}>
          <HistoricalLog
            alerts={alerts}
            zones={zones}
            tenantId={user?.tenant_id || null}
            onSelectAlert={(a) => setSelectedAlert(a)}
          />
        </div>
      </main>

      {/* Alert Detail & Explainability Modal */}
      {selectedAlert && (
        <AlertDetailModal
          alert={selectedAlert}
          user={user}
          onClose={() => setSelectedAlert(null)}
          onFeedbackSubmitted={handleFeedbackSuccess}
        />
      )}
    </div>
  );
};

export default App;
