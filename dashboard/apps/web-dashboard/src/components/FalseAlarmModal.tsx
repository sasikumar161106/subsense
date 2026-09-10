import React, { useState } from "react";
import { AlertLifecycleEvent, FalseAlarmReason } from "@subsense/shared";
import { HelpCircle, BrainCircuit, X, Check } from "lucide-react";

interface FalseAlarmModalProps {
  alert: AlertLifecycleEvent | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmitFalseAlarm: (
    alertId: string,
    reason: FalseAlarmReason,
    notes: string,
    featureVector?: Record<string, any>
  ) => Promise<void>;
}

const FALSE_ALARM_REASONS: { value: FalseAlarmReason; label: string; description: string }[] = [
  {
    value: "surface_blasting",
    label: "Surface Blasting Noise",
    description: "Open-pit or adjacent bench detonation blast transient corroborated with blasting logs",
  },
  {
    value: "heavy_vehicle_impact",
    label: "Heavy Haulage Vehicle Impact",
    description: "60T dump truck or continuous miner impact vibration adjacent to borehole casing",
  },
  {
    value: "thermal_expansion_anomaly",
    label: "Thermal Expansion / Diurnal Swing",
    description: "Rapid surface solar heating causing borehole head displacement spike without sub-surface shear",
  },
  {
    value: "sensor_hardware_glitch",
    label: "Sensor Hardware / Inclinometer Glitch",
    description: "Intermittent ADC voltage fluctuation or potentiometer contact bounce",
  },
  {
    value: "telecom_packet_jitter",
    label: "Sub-GHz Mesh Re-transmit Jitter",
    description: "Out-of-order packet arrival causing artificial velocity calculation surge",
  },
  {
    value: "unrelated_seismic_activity",
    label: "Regional Distant Earthquake",
    description: "Regional tectonic tremor detected across geological survey stations",
  },
];

export const FalseAlarmModal: React.FC<FalseAlarmModalProps> = ({
  alert,
  isOpen,
  onClose,
  onSubmitFalseAlarm,
}) => {
  const [selectedReason, setSelectedReason] = useState<FalseAlarmReason>("surface_blasting");
  const [notes, setNotes] = useState<string>("Corroborated with shift foreman: scheduled bench charge detonated at 04:10.");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen || !alert) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSubmitFalseAlarm(alert.alert_id, selectedReason, notes, {
        contributing_sensors: alert.contributing_sensors,
        confidence_score: alert.confidence_score,
        time_to_critical: alert.time_to_critical_hours,
        retraining_flag: true,
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in duration-200">
        <div className="bg-slate-800/90 border-b border-slate-700 p-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-slate-100 font-bold">
            <BrainCircuit className="w-5 h-5 text-purple-400" />
            <h3 className="text-base font-mono uppercase tracking-wide">
              Layer 4 AI Retraining — False Alarm Label
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <p className="text-xs text-slate-300">
            Categorizing this alert captures the underlying geotechnical noise vector to automatically fine-tune the Layer 4 LSTM/Autoencoder subsidence models.
          </p>

          <div>
            <label className="block text-xs font-mono font-medium text-slate-300 mb-1.5">
              Structured Noise Category:
            </label>
            <div className="space-y-2">
              {FALSE_ALARM_REASONS.map((r) => (
                <label
                  key={r.value}
                  className={`flex items-start gap-2.5 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                    selectedReason === r.value
                      ? "bg-purple-950/40 border-purple-500 text-purple-200"
                      : "bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <input
                    type="radio"
                    name="false_alarm_reason"
                    value={r.value}
                    checked={selectedReason === r.value}
                    onChange={() => setSelectedReason(r.value)}
                    className="mt-0.5 accent-purple-500"
                  />
                  <div>
                    <div className="text-xs font-bold text-slate-200 font-mono">{r.label}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{r.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono font-medium text-slate-300 mb-1">
              Field Verification Notes:
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-purple-500"
              required
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold font-mono uppercase tracking-wide flex items-center gap-1.5 shadow-lg shadow-purple-950 transition-colors"
            >
              <Check className="w-4 h-4" />
              {isSubmitting ? "Submitting Feature Vector..." : "Emit to Retraining Loop"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
