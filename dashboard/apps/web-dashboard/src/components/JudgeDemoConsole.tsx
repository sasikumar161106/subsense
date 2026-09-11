import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  Radio,
  Volume2,
  VolumeX,
  Zap,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Tv,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Phone,
} from "lucide-react";

export interface JudgeDemoConsoleProps {
  onTriggerScenario: (scenario: "normal" | "warning" | "critical" | "mesh_drop") => void;
  activeScenario: "normal" | "warning" | "critical" | "mesh_drop";
  packetsCount: number;
  isStreaming: boolean;
  onToggleStreaming: () => void;
  currentTilt: number;
  currentVib: number;
  currentAnomaly: number;
  sirenActive: boolean;
  onSilenceSiren: () => void;
  onToggleOledMirror: () => void;
  showOledMirror: boolean;
  onOpenSmsContacts?: () => void;
  activeSmsCount?: number;
}

export const JudgeDemoConsole: React.FC<JudgeDemoConsoleProps> = ({
  onTriggerScenario,
  activeScenario,
  packetsCount,
  isStreaming,
  onToggleStreaming,
  currentTilt,
  currentVib,
  currentAnomaly,
  sirenActive,
  onSilenceSiren,
  onToggleOledMirror,
  showOledMirror,
  onOpenSmsContacts,
  activeSmsCount,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  return (
    <div className="bg-gradient-to-r from-[#0E1726] via-[#111C35] to-[#0E1726] border-b border-amber-500/30 text-slate-100 shadow-xl relative z-40">
      {/* Top Banner Stripe */}
      <div className="max-w-7xl mx-auto px-4 py-2 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Left: Judge Demo Badge */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/20 border border-amber-500/50 text-amber-400 font-mono font-bold tracking-wider text-[11px] animate-pulse">
            <Zap className="w-3.5 h-3.5 fill-amber-400" />
            <span>SIH 2026 EVALUATION CONSOLE</span>
          </div>
          <span className="hidden sm:inline text-slate-400 font-medium">|</span>
          <div className="hidden sm:flex items-center gap-1.5 text-slate-300">
            <span className="text-slate-400">Mesh Stream:</span>
            <span className="font-mono font-bold text-emerald-400">{packetsCount} packets</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block ml-1"></span>
          </div>
        </div>

        {/* Center: Real-Time Scenario Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] text-slate-400 font-medium hidden md:inline">Trigger Drill:</span>
          
          {/* Scenario 1: Nominal */}
          <button
            onClick={() => onTriggerScenario("normal")}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all shadow-sm ${
              activeScenario === "normal" && !sirenActive
                ? "bg-emerald-600 text-white ring-2 ring-emerald-400/50 shadow-emerald-600/30"
                : "bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700"
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>1. Safe (Nominal)</span>
          </button>

          {/* Scenario 2: Strata Creep */}
          <button
            onClick={() => onTriggerScenario("warning")}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all shadow-sm ${
              activeScenario === "warning"
                ? "bg-amber-600 text-white ring-2 ring-amber-400/50 shadow-amber-600/30"
                : "bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span>2. Creep Warning</span>
          </button>

          {/* Scenario 3: CATASTROPHIC COLLAPSE */}
          <button
            onClick={() => onTriggerScenario("critical")}
            className={`px-3.5 py-1.5 rounded-lg text-[11px] font-extrabold flex items-center gap-1.5 transition-all transform hover:scale-105 shadow-md ${
              sirenActive || activeScenario === "critical"
                ? "bg-red-600 text-white ring-4 ring-red-500/60 animate-bounce shadow-red-600/50"
                : "bg-red-950/80 hover:bg-red-900/90 text-red-300 border border-red-700/60"
            }`}
          >
            <Flame className="w-3.5 h-3.5 text-red-200 fill-red-400" />
            <span>3. COLLAPSE DRILL</span>
          </button>

          {/* Hardware OLED Mirror Toggle */}
          <button
            onClick={onToggleOledMirror}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all border ${
              showOledMirror
                ? "bg-cyan-600 text-white border-cyan-400"
                : "bg-slate-800/80 hover:bg-slate-700/80 text-cyan-300 border-cyan-800/60"
            }`}
          >
            <Tv className="w-3.5 h-3.5" />
            <span>{showOledMirror ? "Hide OLED" : "Show OLED"}</span>
          </button>

          {/* Emergency SMS Broadcast List Button */}
          {onOpenSmsContacts && (
            <button
              onClick={onOpenSmsContacts}
              className="px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all bg-purple-950/80 hover:bg-purple-900/90 text-purple-200 border border-purple-600/60 shadow-sm hover:border-purple-400"
              title="Manage emergency phone numbers receiving real Termux SMS alerts"
            >
              <Phone className="w-3.5 h-3.5 text-purple-400" />
              <span>SMS List {activeSmsCount !== undefined ? `(${activeSmsCount})` : ""}</span>
            </button>
          )}
        </div>

        {/* Right: Controls & Siren Mute */}
        <div className="flex items-center gap-2">
          {sirenActive && (
            <button
              onClick={onSilenceSiren}
              className="px-2.5 py-1 rounded bg-red-900/90 hover:bg-red-800 text-white font-bold text-[10px] flex items-center gap-1 border border-red-500 animate-pulse"
            >
              <VolumeX className="w-3.5 h-3.5 text-red-400" />
              <span>SILENCE SIREN</span>
            </button>
          )}

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200"
            title="Toggle Live Metrics Drawer"
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expandable Live Metrics HUD */}
      {isExpanded && (
        <div className="bg-[#080D1A] border-t border-[#192642] px-4 py-2 text-xs">
          <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-[11px]">Active Physical Node:</span>
                <span className="font-mono font-bold text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/50">
                  SS-PANEL7-N042
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-[11px]">MPU6050 Pitch/Tilt:</span>
                <span className={`font-mono font-bold ${currentTilt >= 4.0 ? "text-red-400 font-extrabold text-sm" : currentTilt >= 1.5 ? "text-amber-400" : "text-emerald-400"}`}>
                  {currentTilt.toFixed(2)}°
                </span>
                <span className="text-[10px] text-slate-500">(Threshold: 4.00°)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-[11px]">Vibration RMS:</span>
                <span className={`font-mono font-bold ${currentVib >= 0.8 ? "text-red-400" : "text-slate-200"}`}>
                  {currentVib.toFixed(2)} mm/s
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-[11px]">On-Device TinyML Score:</span>
                <span className={`font-mono font-bold ${currentAnomaly >= 0.7 ? "text-red-400 text-sm" : "text-emerald-400"}`}>
                  {(currentAnomaly * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3 text-[11px] text-slate-400">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span>Zero-Fabrication Mode: Active (Displacement/Crack = null)</span>
              </div>
              <span className="text-slate-600">•</span>
              <div className="flex items-center gap-1.5">
                <span className="text-cyan-400 font-mono">ESP-NOW Hop: 0</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
