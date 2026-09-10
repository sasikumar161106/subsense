import React, { useState, useEffect } from 'react';
import { Bell, Volume2, VolumeX, CheckCircle, AlertOctagon } from 'lucide-react';
import { EdgeSirenEvent } from '../types';

interface SirenBannerProps {
  sirenEvent: EdgeSirenEvent | null;
  onDismiss: () => void;
}

export const SirenBanner: React.FC<SirenBannerProps> = ({ sirenEvent, onDismiss }) => {
  const [soundEnabled, setSoundEnabled] = useState(false);

  // Play browser emergency acoustic tone when siren event fires (if sound enabled)
  useEffect(() => {
    if (sirenEvent && soundEnabled && typeof window !== 'undefined' && window.AudioContext) {
      try {
        const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5
        osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.4);

        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);

        osc.connect(gain);
        gain.connect(audioCtx.destination);

        osc.start();
        osc.stop(audioCtx.currentTime + 0.45);
      } catch (err) {
        console.warn('Audio tone synthesis blocked by browser policy:', err);
      }
    }
  }, [sirenEvent, soundEnabled]);

  if (!sirenEvent) return null;

  return (
    <div className="siren-active-banner">
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          background: '#ffffff',
          color: '#dc2626',
          borderRadius: '50%',
          padding: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          animation: 'pulse 1s infinite'
        }}>
          <AlertOctagon size={24} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '1.05rem', letterSpacing: '0.02em' }}>
              AUTONOMOUS EDGE SIREN ACTIVE — ZONE: {sirenEvent.zone_id.toUpperCase()}
            </span>
            <span style={{
              background: 'rgba(0,0,0,0.3)',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              fontWeight: 500
            }}>
              Decoupled Edge GPIO Pin HIGH (&lt; 1.2s Latency)
            </span>
          </div>
          <div style={{ fontSize: '0.8rem', opacity: 0.9, marginTop: '2px' }}>
            Triggered at {new Date(sirenEvent.timestamp).toLocaleTimeString()} directly by on-ground hardware bus. Internet network calls bypassed.
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          onClick={() => setSoundEnabled(!soundEnabled)}
          style={{
            background: 'rgba(0,0,0,0.35)',
            border: '1px solid rgba(255,255,255,0.4)',
            color: '#ffffff',
            padding: '6px 12px',
            borderRadius: '8px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.8rem',
            fontWeight: 600
          }}
          title={soundEnabled ? 'Mute alert siren' : 'Enable audio tone'}
        >
          {soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          <span>{soundEnabled ? 'Audio ON' : 'Audio Muted'}</span>
        </button>

        <button
          onClick={onDismiss}
          style={{
            background: '#ffffff',
            color: '#b91c1c',
            border: 'none',
            padding: '7px 16px',
            borderRadius: '8px',
            fontWeight: 700,
            cursor: 'pointer',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
          }}
        >
          <CheckCircle size={16} />
          <span>Acknowledge Siren</span>
        </button>
      </div>
    </div>
  );
};
