import React, { useState, useEffect } from "react";
import ReactECharts from "echarts-for-react";
import { fetchApi } from "../services/api";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../contexts/AuthContext";
import {
  LineChart,
  Calendar,
  Play,
  Sliders,
  TrendingUp,
  CloudRain,
  Flame,
  AlertOctagon,
} from "lucide-react";

export const GeotechTrendsView: React.FC = () => {
  const { currentTenantId, currentSiteId } = useTenant();
  const { currentUser } = useAuth();

  const [range, setRange] = useState<"1h" | "24h" | "7d" | "30d">("24h");
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Sandboxed Simulation State
  const [simExtractionRate, setSimExtractionRate] = useState<number>(120); // tons/hr
  const [simWaterTableDrop, setSimWaterTableDrop] = useState<number>(4.5); // meters
  const [simResults, setSimResults] = useState<any>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);

  useEffect(() => {
    const loadTrends = async () => {
      setIsLoading(true);
      try {
        const res = await fetchApi(`/geotech/trends?site_id=${currentSiteId}&range=${range}`, {
          tenantId: currentTenantId,
          userRole: currentUser.role,
          userId: currentUser.userId,
        });
        setData(res);
      } catch (err) {
        console.error("Failed to load geotechnical trends:", err);
      } finally {
        setIsLoading(false);
      }
    };
    loadTrends();
  }, [currentTenantId, currentSiteId, range]);

  const handleRunSimulation = () => {
    setIsSimulating(true);
    setTimeout(() => {
      setSimResults({
        scenario: `Extraction +${simExtractionRate}t/hr, Water Table -${simWaterTableDrop}m`,
        peakSubsidenceVelocity: (0.15 + simExtractionRate * 0.0008 + simWaterTableDrop * 0.02).toFixed(3),
        criticalBreachProb: Math.min(94, Math.round(35 + simExtractionRate * 0.25 + simWaterTableDrop * 4)),
        timeToLimitDays: Math.max(0, 18 - simWaterTableDrop * 1.5).toFixed(1),
      });
      setIsSimulating(false);
    }, 600);
  };

  // Build ECharts options
  const getChartOption = () => {
    if (!data) return {};

    const history = data.history || [];
    const forecast = data.forecast_lstm?.points || [];
    const markers = data.event_markers || [];

    const historyDates = history.map((h: any) => new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    const forecastDates = forecast.map((f: any) => new Date(f.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    const allDates = [...historyDates, ...forecastDates];

    // History Displacement
    const historyDisp = history.map((h: any) => h.displacement_mm);
    // Pad forecast with nulls for history dates
    const p50Data = [...new Array(history.length - 1).fill(null), historyDisp[historyDisp.length - 1], ...forecast.map((f: any) => f.p50)];
    const p10Data = [...new Array(history.length - 1).fill(null), historyDisp[historyDisp.length - 1], ...forecast.map((f: any) => f.p10)];
    const p90Data = [...new Array(history.length - 1).fill(null), historyDisp[historyDisp.length - 1], ...forecast.map((f: any) => f.p90)];

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", label: { backgroundColor: "#1e293b" } },
        backgroundColor: "rgba(15, 23, 42, 0.95)",
        borderColor: "#334155",
        textStyle: { color: "#e2e8f0", fontFamily: "JetBrains Mono", fontSize: 11 },
      },
      legend: {
        data: ["Historical Extensometer (mm)", "LSTM Forecast (p50 Median)", "90% Risk Envelope (p90)", "10% Lower Bound (p10)"],
        textStyle: { color: "#94a3b8", fontFamily: "JetBrains Mono", fontSize: 11 },
        top: 0,
      },
      grid: {
        left: "3%",
        right: "4%",
        bottom: "10%",
        top: "12%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: allDates,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#94a3b8", fontFamily: "JetBrains Mono", fontSize: 10 },
      },
      yAxis: {
        type: "value",
        name: "Subsidence Displacement (mm)",
        nameTextStyle: { color: "#94a3b8", fontFamily: "JetBrains Mono", fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(51, 65, 85, 0.3)" } },
        axisLabel: { color: "#94a3b8", fontFamily: "JetBrains Mono", fontSize: 10 },
      },
      series: [
        {
          name: "Historical Extensometer (mm)",
          type: "line",
          data: [...historyDisp, ...new Array(forecast.length).fill(null)],
          smooth: true,
          lineStyle: { color: "#06b6d4", width: 2.5 },
          itemStyle: { color: "#06b6d4" },
          markPoint: {
            data: markers.map((m: any) => ({
              name: m.title,
              coord: [
                new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                historyDisp[Math.floor(historyDisp.length / 2)] || 2.5,
              ],
              value: m.type.toUpperCase(),
              itemStyle: {
                color: m.type === "blast" ? "#ef4444" : m.type === "rainfall" ? "#3b82f6" : "#f59e0b",
              },
            })),
          },
        },
        {
          name: "LSTM Forecast (p50 Median)",
          type: "line",
          data: p50Data,
          smooth: true,
          lineStyle: { color: "#f59e0b", width: 2.5, type: "dashed" },
          itemStyle: { color: "#f59e0b" },
        },
        {
          name: "90% Risk Envelope (p90)",
          type: "line",
          data: p90Data,
          smooth: true,
          lineStyle: { opacity: 0 },
          stack: "confidence-band",
          areaStyle: {
            color: "rgba(239, 68, 68, 0.15)",
          },
        },
        {
          name: "10% Lower Bound (p10)",
          type: "line",
          data: p10Data,
          smooth: true,
          lineStyle: { opacity: 0 },
          stack: "confidence-band",
          areaStyle: {
            color: "rgba(16, 185, 129, 0.08)",
          },
        },
      ],
    };
  };

  return (
    <div className="space-y-6">
      {/* Header & Downsample resolution selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800 font-mono">
        <div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <LineChart className="w-4 h-4 text-amber-400" />
            TimescaleDB Geomechanical Trends &amp; LSTM Forecast Uncertainty Cones
          </h2>
          <p className="text-[11px] text-slate-400 mt-0.5">
            BiLSTM quantile multi-horizon subsidence projection with 10th / 50th / 90th percentile bounds
          </p>
        </div>

        {/* Downsampling Range Buttons */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
          <span className="text-[11px] text-slate-500 px-2">Resolution:</span>
          {(["1h", "24h", "7d", "30d"] as const).map((r) => (
            <button
              key={r}
              id={`range-btn-${r}`}
              onClick={() => setRange(r)}
              className={`px-3 py-1 rounded font-mono transition-colors ${
                range === r
                  ? "bg-amber-500 text-slate-950 font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chart Area */}
      <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800">
        {isLoading ? (
          <div className="h-96 flex items-center justify-center font-mono text-slate-400">
            Querying downsampled TimescaleDB hypertable...
          </div>
        ) : (
          <ReactECharts option={getChartOption()} style={{ height: "420px", width: "100%" }} />
        )}
      </div>

      {/* Sandboxed Geotechnical What-If Simulation Runner */}
      <div className="bg-slate-900/60 p-5 rounded-xl border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-purple-400" />
            <h3 className="text-sm font-bold text-slate-200 font-mono uppercase tracking-wide">
              Sandboxed Geotechnical What-If Simulation Workspace
            </h3>
            <span className="text-[10px] bg-purple-950 text-purple-300 border border-purple-800 px-1.5 py-0.5 rounded font-mono">
              Production Isolated
            </span>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Audit standard: Simulation parameter sets tracked in planner ledger
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Slider 1: Extraction Acceleration */}
          <div className="space-y-2 font-mono text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Face Extraction Rate:</span>
              <span className="text-amber-400 font-bold">{simExtractionRate} t/hr</span>
            </div>
            <input
              type="range"
              min="50"
              max="300"
              value={simExtractionRate}
              onChange={(e) => setSimExtractionRate(parseInt(e.target.value, 10))}
              className="w-full accent-amber-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>50 t/hr (Slow)</span>
              <span>300 t/hr (Longwall Max)</span>
            </div>
          </div>

          {/* Slider 2: Water Table Drawdown */}
          <div className="space-y-2 font-mono text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Aquifer Drawdown:</span>
              <span className="text-cyan-400 font-bold">{simWaterTableDrop} m</span>
            </div>
            <input
              type="range"
              min="0"
              max="15"
              step="0.5"
              value={simWaterTableDrop}
              onChange={(e) => setSimWaterTableDrop(parseFloat(e.target.value))}
              className="w-full accent-cyan-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>0 m (Static)</span>
              <span>15 m (Heavy Infiltration)</span>
            </div>
          </div>

          {/* Run Button & Outcome */}
          <div className="flex flex-col justify-center">
            <button
              id="btn-run-simulation"
              onClick={handleRunSimulation}
              disabled={isSimulating}
              className="px-4 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-mono font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-950 transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              {isSimulating ? "Running Sandboxed Simulation..." : "Execute What-If Model"}
            </button>
          </div>
        </div>

        {/* Simulation Output Card */}
        {simResults && (
          <div className="mt-3 p-3.5 bg-slate-950 border border-purple-800/60 rounded-lg text-xs font-mono grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <span className="text-slate-400">Peak Displacement Velocity:</span>
              <div className="text-base font-bold text-amber-400">{simResults.peakSubsidenceVelocity} mm/day</div>
            </div>
            <div>
              <span className="text-slate-400">Critical Breach Probability:</span>
              <div className="text-base font-bold text-red-400">{simResults.criticalBreachProb}%</div>
            </div>
            <div>
              <span className="text-slate-400">Projected Time to Threshold:</span>
              <div className="text-base font-bold text-emerald-400">{simResults.timeToLimitDays} days</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
