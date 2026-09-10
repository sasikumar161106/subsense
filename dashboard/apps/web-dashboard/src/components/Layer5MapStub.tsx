import React, { useState, useEffect } from "react";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize2,
  Compass,
  Layers,
  MapPin,
  Box,
} from "lucide-react";
import { NodeTelemetryRecord } from "@subsense/shared";

interface MapNode {
  id: string;
  x: number; // 0 to 100% SVG coordinates
  y: number;
  label: string;
  type: string;
  status: "nominal" | "warning" | "critical" | "stale";
}

interface Layer5MapStubProps {
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  telemetryMap: Map<string, NodeTelemetryRecord>;
  className?: string;
}

export const Layer5MapStub: React.FC<Layer5MapStubProps> = ({
  selectedNodeId,
  onSelectNode,
  telemetryMap,
  className = "",
}) => {
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [viewMode, setViewMode] = useState<"map" | "3d">("map");
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Nodes distributed across Jharia Panel 7 coordinates
  const nodes: MapNode[] = [
    { id: "SS-PANEL7-N042", x: 44, y: 40, label: "N042", type: "Extensometer", status: "critical" },
    { id: "SS-PANEL7-N043", x: 62, y: 32, label: "N043", type: "Repeater", status: "stale" },
    { id: "SS-PANEL7-N021", x: 32, y: 55, label: "N021", type: "Inclinometer", status: "nominal" },
    { id: "SS-PANEL7-N038", x: 74, y: 64, label: "N038", type: "Crack Gauge", status: "stale" },
    { id: "SS-PANEL7-N017", x: 25, y: 30, label: "N017", type: "Extensometer", status: "nominal" },
  ];

  // Auto pan to selected node when clicked in sensor table
  useEffect(() => {
    if (selectedNodeId) {
      const node = nodes.find((n) => n.id === selectedNodeId);
      if (node) {
        setPanOffset({
          x: (50 - node.x) * 4,
          y: (50 - node.y) * 4,
        });
        setZoomLevel(1.3);
      }
    }
  }, [selectedNodeId]);

  const handleZoomIn = () => setZoomLevel((z) => Math.min(2.5, z + 0.25));
  const handleZoomOut = () => setZoomLevel((z) => Math.max(0.8, z - 0.25));
  const handleReset = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  };

  return (
    <div
      id="gis-digital-twin-card"
      className={`bg-slate-900/70 border border-slate-800/90 rounded-xl overflow-hidden font-mono shadow-sm flex flex-col ${className}`}
    >
      {/* Card Header with Title and Mode Controls */}
      <div className="p-3.5 sm:p-4 border-b border-slate-800/80 flex items-center justify-between gap-3 bg-slate-950/60 select-none">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-amber-400" />
          <h2 className="text-xs font-bold text-white uppercase tracking-wider">
            GIS &amp; DIGITAL TWIN
          </h2>
        </div>

        {/* Map / 3D View Controls & Fullscreen */}
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center bg-slate-900 border border-slate-800 p-0.5 rounded-lg">
            <button
              onClick={() => setViewMode("map")}
              className={`px-2.5 py-1 rounded text-[11px] font-bold transition-colors ${
                viewMode === "map"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Map
            </button>
            <button
              onClick={() => setViewMode("3d")}
              className={`px-2.5 py-1 rounded text-[11px] font-bold flex items-center gap-1 transition-colors ${
                viewMode === "3d"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Box className="w-3 h-3" />
              <span>3D View</span>
            </button>
          </div>

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            title="Toggle fullscreen"
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Map Body Canvas */}
      <div className="relative flex-1 bg-slate-950 min-h-[360px] overflow-hidden select-none">
        {/* Floating Controls: Compass, Zoom In/Out, Reset */}
        <div className="absolute top-3 right-3 z-20 flex flex-col gap-1.5">
          <div className="p-2 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-300 flex items-center justify-center shadow-md">
            <Compass className="w-4 h-4 text-cyan-400 animate-pulse" />
          </div>
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="p-2 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-slate-800 text-slate-300 transition-colors shadow-md"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="p-2 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-slate-800 text-slate-300 transition-colors shadow-md"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleReset}
            title="Reset View"
            className="p-2 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-slate-800 text-slate-300 transition-colors shadow-md"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Floating Top Left Badge */}
        <div className="absolute top-3 left-3 z-20 bg-slate-900/90 backdrop-blur border border-slate-800 px-2.5 py-1.5 rounded-lg text-[10px] text-slate-300 flex items-center gap-2 shadow-md">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
          <span>Panel 7 Strata Basin</span>
          <span className="text-slate-500">|</span>
          <span className="text-amber-400 font-bold">Zoom: {zoomLevel.toFixed(1)}x</span>
        </div>

        {/* SVG GIS Layer */}
        <svg
          viewBox="0 0 1000 650"
          className="w-full h-full cursor-grab active:cursor-grabbing transition-transform duration-300"
          style={{
            transform: `scale(${zoomLevel}) translate(${panOffset.x}px, ${panOffset.y}px)`,
            transformOrigin: "center center",
          }}
        >
          <defs>
            <pattern id="gis-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(51, 65, 85, 0.2)" strokeWidth="1" />
            </pattern>
            <radialGradient id="delamination-core" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.75" />
              <stop offset="60%" stopColor="#ef4444" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="warning-perimeter" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Grid Background */}
          <rect width="1000" height="650" fill="#070b14" />
          <rect width="1000" height="650" fill="url(#gis-grid)" />

          {/* Panel Area Boundary Polygon */}
          <polygon
            points="180,110 820,130 840,530 140,510"
            fill="rgba(6, 182, 212, 0.04)"
            stroke="#06b6d4"
            strokeWidth="2"
            strokeDasharray="6 4"
          />

          {/* Contour Lines of Subsidence Trough */}
          <ellipse cx="480" cy="320" rx="340" ry="200" fill="none" stroke="#1e293b" strokeWidth="1.5" />
          <ellipse cx="460" cy="330" rx="240" ry="140" fill="none" stroke="#334155" strokeWidth="1.5" />
          <ellipse cx="450" cy="340" rx="160" ry="95" fill="url(#warning-perimeter)" stroke="#d97706" strokeWidth="1.5" />
          <ellipse cx="440" cy="350" rx="90" ry="55" fill="url(#delamination-core)" stroke="#ef4444" strokeWidth="2" />

          {/* Mesh Edges */}
          <line x1="620" y1="208" x2="440" y2="260" stroke="#0ea5e9" strokeWidth="1.5" strokeOpacity="0.6" />
          <line x1="440" y1="260" x2="320" y2="357" stroke="#0ea5e9" strokeWidth="1.5" strokeOpacity="0.6" />
          <line x1="440" y1="260" x2="740" y2="416" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4 4" strokeOpacity="0.5" />
          <line x1="440" y1="260" x2="250" y2="195" stroke="#0ea5e9" strokeWidth="1.5" strokeOpacity="0.6" />

          {/* Node Markers */}
          {nodes.map((node) => {
            const cx = node.x * 10;
            const cy = node.y * 6.5;
            const isSelected = selectedNodeId === node.id;
            const isCritical = node.status === "critical";
            const isStale = node.status === "stale";

            return (
              <g
                key={node.id}
                onClick={() => onSelectNode(node.id)}
                className="cursor-pointer group"
              >
                {/* Active Pulse Ring */}
                {(isSelected || isCritical) && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isSelected ? 30 : 22}
                    fill={isCritical ? "rgba(239, 68, 68, 0.35)" : "rgba(59, 130, 246, 0.3)"}
                    className="animate-pulse"
                  />
                )}

                {/* Node Center Dot */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isSelected ? 10 : 7}
                  fill={isCritical ? "#ef4444" : isStale ? "#f59e0b" : "#10b981"}
                  stroke={isSelected ? "#ffffff" : "#0f172a"}
                  strokeWidth={isSelected ? 3 : 2}
                  className="transition-all duration-150"
                />

                {/* Label Tag */}
                <rect
                  x={cx - 36}
                  y={cy + 12}
                  width="72"
                  height="18"
                  rx="3"
                  fill="#090d16"
                  fillOpacity="0.9"
                  stroke={isSelected ? "#38bdf8" : "#334155"}
                  strokeWidth="1"
                />
                <text
                  x={cx}
                  y={cy + 24}
                  textAnchor="middle"
                  fill={isSelected ? "#38bdf8" : "#cbd5e1"}
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight={isSelected ? "bold" : "normal"}
                >
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Scale Indicator Bar */}
        <div className="absolute bottom-11 right-4 z-20 flex flex-col items-end text-[9px] text-slate-400 font-mono">
          <div className="w-16 h-1 border-b-2 border-l-2 border-r-2 border-slate-400 mb-0.5"></div>
          <span>100 m</span>
        </div>
      </div>

      {/* Map Legend Footer */}
      <div className="p-2.5 sm:p-3 bg-slate-950/90 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-[11px] text-slate-300 select-none">
        <div className="flex flex-wrap items-center gap-3 sm:gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
            <span>Normal</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
            <span>Warning</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"></span>
            <span>Critical</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm border border-cyan-400"></span>
            <span>Node</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-0.5 bg-cyan-400 border-dashed"></span>
            <span>Panel Boundary</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 bg-red-500/20 rounded"></span>
            <span>Panel Area</span>
          </span>
        </div>

        <div className="text-[10px] text-slate-500 hidden md:block">
          Bidirectional Sync: Click map node to jump to table row
        </div>
      </div>
    </div>
  );
};
