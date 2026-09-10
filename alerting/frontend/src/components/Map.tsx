import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { AlertRecord, AlertSeverity, RiskZoneMetadata } from '../types';

interface MapProps {
  zones: RiskZoneMetadata[];
  activeAlerts: AlertRecord[];
  activeSirenZoneId: string | null;
  onSelectAlert: (alert: AlertRecord) => void;
}

export const MineMap: React.FC<MapProps> = ({
  zones,
  activeAlerts,
  activeSirenZoneId,
  onSelectAlert
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Center on Eastern India Coalfields (Jharia / Raniganj belt)
    const map = L.map(mapContainerRef.current, {
      center: [23.7483, 86.4175],
      zoom: 11,
      zoomControl: true
    });

    // Dark-styled OpenStreetMap tile layer (CartoDB Dark Matter / OSM)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    markersLayerRef.current = markersGroup;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Markers when zones or activeAlerts change
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();

    if (zones.length === 0) return;

    const bounds = L.latLngBounds([]);

    zones.forEach((zone) => {
      const zoneAlerts = activeAlerts.filter((a) => a.risk_zone_id === zone.zone_id);
      const mostSevere = zoneAlerts.find((a) => a.severity === AlertSeverity.Critical) ||
        zoneAlerts.find((a) => a.severity === AlertSeverity.Warning) ||
        zoneAlerts.find((a) => a.severity === AlertSeverity.Advisory);

      const severity = mostSevere?.severity;
      const isSirenActive = activeSirenZoneId === zone.zone_id;

      let markerClass = 'pulsing-marker-normal';
      let ringColor = '#10b981';

      if (severity === AlertSeverity.Critical) {
        markerClass = 'pulsing-marker-critical';
        ringColor = '#ef4444';
      } else if (severity === AlertSeverity.Warning) {
        markerClass = 'pulsing-marker-warning';
        ringColor = '#f59e0b';
      } else if (severity === AlertSeverity.Advisory) {
        markerClass = 'pulsing-marker-advisory';
        ringColor = '#38bdf8';
      }

      // Create Custom Pulsing HTML Marker
      const customIcon = L.divIcon({
        className: 'custom-leaflet-marker',
        html: `<div class="${markerClass}" title="${zone.zone_name}"></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
      });

      const marker = L.marker([zone.latitude, zone.longitude], { icon: customIcon });

      // Add geofence hazard circle radius
      const circle = L.circle([zone.latitude, zone.longitude], {
        radius: severity === AlertSeverity.Critical ? 1200 : 700,
        color: ringColor,
        fillColor: ringColor,
        fillOpacity: severity === AlertSeverity.Critical ? 0.25 : 0.1,
        weight: severity === AlertSeverity.Critical ? 2 : 1
      });

      // Popup Content with Glassmorphic Styling
      const popupHtml = document.createElement('div');
      popupHtml.style.color = '#0f172a';
      popupHtml.style.fontFamily = 'Inter, sans-serif';
      popupHtml.style.minWidth = '220px';

      popupHtml.innerHTML = `
        <div style="font-weight: 700; font-size: 0.95rem; margin-bottom: 4px; color: #0f172a;">
          ${zone.zone_name}
        </div>
        <div style="font-size: 0.75rem; color: #475569; margin-bottom: 8px;">
          Depth: ${zone.seam_depth_m}m | ${zone.strata_profile}
        </div>
        ${
          severity
            ? `<div style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; margin-bottom: 8px; color: #fff; background: ${
                severity === 'Critical' ? '#dc2626' : severity === 'Warning' ? '#d97706' : '#2563eb'
              }">
                ACTIVE ${severity.toUpperCase()} ALERT
              </div>`
            : `<div style="color: #059669; font-weight: 600; font-size: 0.8rem; margin-bottom: 8px;">
                Status: Normal / Strata Stable
              </div>`
        }
        ${isSirenActive ? '<div style="color: #dc2626; font-weight: 800; font-size: 0.75rem; margin-bottom: 6px;">SIREN ACTIVE (Edge Triggered)</div>' : ''}
        ${
          mostSevere
            ? `<div style="font-size: 0.75rem; color: #334155; margin-bottom: 8px;">
                TTC: <b>${mostSevere.time_to_critical_hours ? mostSevere.time_to_critical_hours.toFixed(1) + 'h' : 'N/A'}</b> | Confidence: <b>${(mostSevere.confidence_score * 100).toFixed(0)}%</b>
              </div>
              <button id="btn-inspect-${mostSevere.alert_id}" style="width: 100%; background: #0f172a; color: #ffffff; border: none; border-radius: 6px; padding: 6px 12px; font-weight: 600; font-size: 0.75rem; cursor: pointer;">
                Inspect Alert Details &rarr;
              </button>`
            : ''
        }
      `;

      if (mostSevere) {
        popupHtml.querySelector(`#btn-inspect-${mostSevere.alert_id}`)?.addEventListener('click', () => {
          onSelectAlert(mostSevere);
        });
      }

      marker.bindPopup(popupHtml);
      markersLayerRef.current?.addLayer(marker);
      markersLayerRef.current?.addLayer(circle);

      bounds.extend([zone.latitude, zone.longitude]);
    });

    if (zones.length > 0 && bounds.isValid()) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
    }
  }, [zones, activeAlerts, activeSirenZoneId, onSelectAlert]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '380px' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', borderRadius: '12px' }} />
      {/* Map Legend Overlay */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '8px',
        padding: '10px 14px',
        fontSize: '0.75rem',
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        gap: '6px'
      }}>
        <div style={{ fontWeight: 700, color: '#f8fafc', marginBottom: '2px' }}>Strata Risk Legend</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }} />
          <span>Critical (Evacuation / Siren)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f59e0b' }} />
          <span>Warning (SMS / Push / Banner)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38bdf8' }} />
          <span>Advisory (Daily Digest Batch)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#10b981' }} />
          <span>Normal (Stable Ground)</span>
        </div>
      </div>
    </div>
  );
};
