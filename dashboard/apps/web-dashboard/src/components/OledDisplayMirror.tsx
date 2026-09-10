import React from "react";
import { Cpu, X, Battery, Wifi, ShieldAlert, CheckCircle2 } from "lucide-react";

export interface OledDisplayMirrorProps {
  nodeId: string;
  tilt: number;
  vib: number;
  anomalyScore: number;
  packetsCount: number;
  sirenActive: boolean;
  onClose: () => void;
}

export const OledDisplayMirror: React.FC<OledDisplayMirrorProps> = ({
  nodeId,
  tilt,
  vib,
  anomalyScore,
  packetsCount,
  sirenActive,
  onClose,
}) => {
  const isCritical = sirenActive || tilt >= 4.0 || anomalyScore >= 0.75;
  const statusText = isCritical ? "CRITICAL" : tilt >= 1.5 ? "WARNING" : "NOMINAL";
  const mlScoreInt8 = Math.min(255, Math.round(anomalyScore * 255));

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 duration-300">
      {/* Outer Enclosure (Simulating IP67 ABS Mining Node Housing) */}
      <div className="bg-[#1C2433] p-3 rounded-2xl border-2 border-[#2E3C52] shadow-2xl w-[320px] text-white">
        {/* Enclosure Header */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#2E3C52]/70 text-[11px] font-mono">
          <div className="flex items-center gap-1.5 text-cyan-400 font-bold">
            <Cpu className="w-3.5 h-3.5" />
            <span>SENSOR NODE OLED MIRROR</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-slate-700/80 text-slate-400 hover:text-white"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* OLED Glass Screen (128x64 Aspect Ratio with Blue/Yellow OLED Aesthetic) */}
        <div
          className={`relative rounded-lg p-3 font-mono text-[11px] leading-tight border transition-colors duration-150 overflow-hidden shadow-inner ${
            isCritical
              ? "bg-[#003B46] text-[#E0F7FA] border-[#00BCD4] animate-pulse"
              : "bg-[#020B14] text-[#4DEEEA] border-[#00E5FF]/40"
          }`}
          style={{
            boxShadow: isCritical
              ? "0 0 25px rgba(0, 229, 255, 0.4), inset 0 0 15px rgba(0, 229, 255, 0.3)"
              : "inset 0 0 10px rgba(0, 229, 255, 0.15)",
          }}
        >
          {/* Subtle OLED scanline effect */}
          <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%)] bg-[length:100%_4px] opacity-30"></div>

          {isCritical ? (
            /* Emergency Inverted OLED Banner */
            <div className="py-2 text-center space-y-1">
              <div className="bg-[#E0F7FA] text-[#002E38] font-extrabold px-1 py-0.5 tracking-wider text-[11px] uppercase">
                *** CRITICAL ALARM ***
              </div>
              <div className="text-[13px] font-extrabold text-white tracking-wide pt-1">
                EVACUATE MINE PANEL!
              </div>
              <div className="text-[10px] text-cyan-200">
                TILT: {tilt.toFixed(2)}° &gt; 4.00° LIMIT
              </div>
              <div className="bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded mt-1 inline-block">
                LOCAL SIREN ON (&lt;5µs)
              </div>
            </div>
          ) : (
            /* Normal OLED Telemetry Screen */
            <div className="space-y-1">
              {/* Row 1: Node ID + Battery + RSSI */}
              <div className="flex justify-between items-center text-[10px] text-cyan-300 border-b border-cyan-500/30 pb-1">
                <span className="font-bold">{nodeId}</span>
                <div className="flex items-center gap-1.5">
                  <span>[BATT 94%]</span>
                  <span>[|||]</span>
                </div>
              </div>

              {/* Row 2: Health Status + Hop */}
              <div className="flex justify-between items-center pt-0.5">
                <span className="text-white font-bold">
                  HEALTH: <span className={statusText === "WARNING" ? "text-amber-300" : "text-emerald-300"}>{statusText}</span>
                </span>
                <span className="text-[10px] text-cyan-400">Hop: 0</span>
              </div>

              {/* Row 3: Physical MPU6050 Readings */}
              <div className="text-[10px] text-white">
                Tilt: <span className="font-bold text-cyan-200">{tilt.toFixed(2)}°</span> | Vib: <span className="font-bold text-cyan-200">{vib.toFixed(2)}mm/s</span>
              </div>

              {/* Row 4: On-Device TinyML INT8 Score + MPU Status */}
              <div className="text-[10px] flex justify-between text-cyan-300">
                <span>ML: {mlScoreInt8}/255</span>
                <span>MPU6050: OK</span>
              </div>

              {/* Row 5: Packets Sent + Uptime */}
              <div className="text-[9px] text-cyan-500 flex justify-between pt-0.5 border-t border-cyan-500/20">
                <span>Mesh Tx: #{packetsCount}</span>
                <span>I2C: 0x3C</span>
              </div>
            </div>
          )}
        </div>

        {/* Physical Node Pinout Guide for Judge */}
        <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-700/50">
          <span className="font-mono">ESP32 I2C: SDA=21, SCL=22</span>
          <span className="text-emerald-400 font-bold">Sensor Node Only</span>
        </div>
      </div>
    </div>
  );
};
