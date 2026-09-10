import React, { useState } from "react";
import { AlertLifecycleEvent } from "@subsense/shared";
import { Volume2, AlertTriangle, ShieldCheck, X } from "lucide-react";

interface AudibleAckModalProps {
  alert: AlertLifecycleEvent | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirmAck: (alertId: string, comment: string) => Promise<void>;
}

export const AudibleAckModal: React.FC<AudibleAckModalProps> = ({
  alert,
  isOpen,
  onClose,
  onConfirmAck,
}) => {
  const [comment, setComment] = useState<string>("Audible evacuation chime heard on console. Operator acknowledging protocol.");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen || !alert) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onConfirmAck(alert.alert_id, comment);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-slate-900 border-2 border-red-500/80 rounded-xl shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in duration-200">
        <div className="bg-red-950/80 border-b border-red-800/80 p-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-red-300 font-bold">
            <Volume2 className="w-5 h-5 text-red-400 animate-bounce" />
            <h3 className="text-base font-mono uppercase tracking-wide">
              Mandatory Safety Acknowledgement
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs font-mono space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400">Alert Identifier:</span>
              <span className="text-amber-400 font-bold">{alert.alert_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Location:</span>
              <span className="text-slate-200">{alert.site_id} • {alert.zone_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Severity Level:</span>
              <span className="text-red-400 font-bold uppercase">{alert.severity}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Time to Critical:</span>
              <span className="text-amber-300 font-bold">
                {alert.time_to_critical_hours[0]}h – {alert.time_to_critical_hours[1]}h
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Contributing Sensors:</span>
              <span className="text-cyan-400 font-semibold">{alert.contributing_sensors.join(", ")}</span>
            </div>
            <div className="pt-2 border-t border-slate-800 text-slate-300">
              {alert.explanation_summary}
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono font-medium text-slate-300 mb-1">
              Operator Log Commentary (Recorded to Cryptographic Ledger):
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-red-500 font-mono"
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
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold font-mono uppercase tracking-wide flex items-center gap-1.5 shadow-lg shadow-emerald-950 transition-colors"
            >
              <ShieldCheck className="w-4 h-4" />
              {isSubmitting ? "Signing Ledger..." : "Confirm & Disarm Countdown"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
