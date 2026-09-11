import React, { useState, useEffect } from "react";
import {
  X,
  Phone,
  Send,
  Plus,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Terminal,
  RefreshCw,
  UserCheck,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { fetchApi } from "../services/api";

export interface EmergencyContact {
  id: string;
  name: string;
  role: string;
  phoneNumber: string;
  isActive: boolean;
  createdAt: string;
}

export interface SmsDispatchLog {
  id: string;
  timestamp: string;
  recipientName: string;
  phoneNumber: string;
  message: string;
  command: string;
  success: boolean;
  output: string;
  error?: string;
  durationMs: number;
}

interface SmsContactsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onContactsUpdated?: (count: number) => void;
}

export const SmsContactsModal: React.FC<SmsContactsModalProps> = ({
  isOpen,
  onClose,
  onContactsUpdated,
}) => {
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [logs, setLogs] = useState<SmsDispatchLog[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [broadcasting, setBroadcasting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // New Contact Form State
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>("");
  const [newRole, setNewRole] = useState<string>("Mining Safety Officer");
  const [newPhone, setNewPhone] = useState<string>("+91");

  // Load contacts and logs
  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchApi("/sms/contacts");
      if (res && res.contacts) {
        setContacts(res.contacts);
        if (onContactsUpdated) {
          onContactsUpdated(res.contacts.filter((c: EmergencyContact) => c.isActive).length);
        }
      }
      const logsRes = await fetchApi("/sms/logs");
      if (logsRes && logsRes.logs) {
        setLogs(logsRes.logs);
      }
    } catch (err: any) {
      console.error("Failed to load SMS contacts:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  // Toggle Active State
  const handleToggleActive = async (contact: EmergencyContact) => {
    try {
      const res = await fetchApi(`/sms/contacts/${contact.id}`, {
        method: "PUT",
        body: JSON.stringify({ isActive: !contact.isActive }),
      });
      if (res && res.contact) {
        setContacts((prev) =>
          prev.map((c) => (c.id === contact.id ? { ...c, isActive: !contact.isActive } : c))
        );
      }
    } catch (err: any) {
      alert(`Error toggling contact: ${err.message}`);
    }
  };

  // Add Contact
  const handleAddContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newPhone.trim()) return;

    try {
      const res = await fetchApi("/sms/contacts", {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          role: newRole.trim(),
          phoneNumber: newPhone.trim(),
          isActive: true,
        }),
      });

      if (res && res.contact) {
        setContacts((prev) => [...prev, res.contact]);
        setNewName("");
        setNewPhone("+91");
        setShowAddForm(false);
        setStatusMessage({ type: "success", text: `Contact ${res.contact.name} added successfully!` });
        setTimeout(() => setStatusMessage(null), 4000);
      }
    } catch (err: any) {
      alert(`Error adding contact: ${err.message}`);
    }
  };

  // Delete Contact
  const handleDeleteContact = async (id: string, name: string) => {
    if (!confirm(`Remove ${name} from emergency broadcast list?`)) return;
    try {
      await fetchApi(`/sms/contacts/${id}`, { method: "DELETE" });
      setContacts((prev) => prev.filter((c) => c.id !== id));
    } catch (err: any) {
      alert(`Error deleting contact: ${err.message}`);
    }
  };

  // Send Test SMS to Single Recipient
  const handleSendTestSms = async (contact: EmergencyContact) => {
    setSendingId(contact.id);
    setStatusMessage(null);
    try {
      const res = await fetchApi("/sms/send-test", {
        method: "POST",
        body: JSON.stringify({
          phoneNumber: contact.phoneNumber,
          message: `[SubSense TEST] Emergency SMS Gateway verification to ${contact.name}. Port 8022 active. Time: ${new Date().toLocaleTimeString("en-IN")}`,
        }),
      });

      if (res && res.success) {
        setStatusMessage({
          type: "success",
          text: `✅ SMS successfully sent to ${contact.name} (${contact.phoneNumber}) in ${res.durationMs}ms!`,
        });
      } else {
        setStatusMessage({
          type: "error",
          text: `⚠️ Termux output: ${res.output || "Connection failed. Check Termux SSH & adb forward."}`,
        });
      }
      await loadData();
    } catch (err: any) {
      setStatusMessage({ type: "error", text: `Dispatch error: ${err.message}` });
    } finally {
      setSendingId(null);
    }
  };

  // Broadcast Test SMS to All Active
  const handleBroadcastAll = async () => {
    setBroadcasting(true);
    setStatusMessage(null);
    try {
      const res = await fetchApi("/sms/send-test", {
        method: "POST",
        body: JSON.stringify({
          message: `[SubSense EMERGENCY DRILL] Full personnel SMS broadcast test. Strata early-warning platform verified. Time: ${new Date().toLocaleTimeString("en-IN")}`,
        }),
      });

      if (res && res.success) {
        setStatusMessage({
          type: "success",
          text: `✅ Broadcast completed to ${res.count} contacts in ${res.durationMs}ms!`,
        });
      } else {
        setStatusMessage({
          type: "error",
          text: `⚠️ Partial or failed broadcast: Check Termux console logs.`,
        });
      }
      await loadData();
    } catch (err: any) {
      setStatusMessage({ type: "error", text: `Broadcast error: ${err.message}` });
    } finally {
      setBroadcasting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in font-mono text-xs">
      <div className="bg-[#0B1220] border border-cyan-500/40 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="bg-gradient-to-r from-[#0E1B33] via-[#112347] to-[#0E1B33] border-b border-cyan-500/30 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-400/50 flex items-center justify-center text-cyan-400 shadow-lg shadow-cyan-500/20">
              <Phone className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                  Emergency SMS Alert Broadcast
                </h2>
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-[10px] font-bold">
                  Termux Port 8022
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Dispatches real cellular SMS via connected Android Phone (<code>termux-sms-send</code>)
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Status Toast Banner */}
        {statusMessage && (
          <div
            className={`px-6 py-2.5 flex items-center gap-2 border-b text-xs ${
              statusMessage.type === "success"
                ? "bg-emerald-950/80 border-emerald-600 text-emerald-300"
                : "bg-red-950/80 border-red-600 text-red-300"
            }`}
          >
            {statusMessage.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            )}
            <span className="flex-1">{statusMessage.text}</span>
          </div>
        )}

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1 custom-scrollbar">
          {/* Top Info & Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-[#070D18] p-3.5 rounded-xl border border-slate-800">
            <div className="flex items-center gap-2 text-slate-300">
              <Radio className="w-4 h-4 text-emerald-400" />
              <span>
                Active Recipients:{" "}
                <strong className="text-emerald-400">
                  {contacts.filter((c) => c.isActive).length}
                </strong>{" "}
                / {contacts.length}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowAddForm(!showAddForm)}
                className="px-3 py-1.5 rounded-lg bg-cyan-900/40 hover:bg-cyan-800/60 text-cyan-300 border border-cyan-700/60 font-bold flex items-center gap-1.5 transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{showAddForm ? "Cancel" : "Add Number"}</span>
              </button>

              <button
                onClick={handleBroadcastAll}
                disabled={broadcasting || contacts.filter((c) => c.isActive).length === 0}
                className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 text-white font-bold flex items-center gap-1.5 shadow-md shadow-amber-900/30 transition-all disabled:opacity-50"
              >
                {broadcasting ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Zap className="w-3.5 h-3.5" />
                )}
                <span>{broadcasting ? "Broadcasting..." : "Test All Active"}</span>
              </button>

              <button
                onClick={loadData}
                disabled={loading}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                title="Refresh contacts and logs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>

          {/* Quick Add Form Drawer */}
          {showAddForm && (
            <form
              onSubmit={handleAddContact}
              className="bg-[#0E1729] border border-cyan-500/50 p-4 rounded-xl space-y-3 animate-fade-in"
            >
              <h3 className="font-bold text-white flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-cyan-400" />
                <span>Register Emergency Alert Recipient</span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Personnel Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Sasi Kumar"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="w-full bg-[#070D18] border border-slate-700 rounded-lg px-3 py-1.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Role / Designation</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Mine Safety Officer"
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value)}
                    className="w-full bg-[#070D18] border border-slate-700 rounded-lg px-3 py-1.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Phone Number (E.164)</label>
                  <input
                    type="text"
                    required
                    placeholder="+917358160485"
                    value={newPhone}
                    onChange={(e) => setNewPhone(e.target.value)}
                    className="w-full bg-[#070D18] border border-slate-700 rounded-lg px-3 py-1.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-3 py-1 rounded bg-slate-800 text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-bold flex items-center gap-1.5 shadow-md"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Save Contact</span>
                </button>
              </div>
            </form>
          )}

          {/* Contact List Table */}
          <div className="border border-slate-800 rounded-xl overflow-hidden bg-[#070D18]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#0D1527] border-b border-slate-800 text-[11px] text-slate-400 uppercase tracking-wider">
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Recipient Name</th>
                  <th className="py-2.5 px-4">Role</th>
                  <th className="py-2.5 px-4">Phone Number</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {contacts.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-500">
                      No emergency contacts configured yet. Click "Add Number" above.
                    </td>
                  </tr>
                ) : (
                  contacts.map((contact) => (
                    <tr
                      key={contact.id}
                      className={`hover:bg-slate-800/30 transition-colors ${
                        !contact.isActive ? "opacity-50" : ""
                      }`}
                    >
                      {/* Active Toggle */}
                      <td className="py-3 px-4">
                        <button
                          onClick={() => handleToggleActive(contact)}
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${
                            contact.isActive
                              ? "bg-emerald-950/70 border-emerald-500 text-emerald-400"
                              : "bg-slate-800 border-slate-600 text-slate-400"
                          }`}
                        >
                          {contact.isActive ? "ACTIVE" : "PAUSED"}
                        </button>
                      </td>

                      {/* Name */}
                      <td className="py-3 px-4 font-bold text-white flex items-center gap-2">
                        <span>{contact.name}</span>
                        {contact.phoneNumber === "+917358160485" && (
                          <span className="px-1.5 py-0.2 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[9px]">
                            PRIMARY
                          </span>
                        )}
                      </td>

                      {/* Role */}
                      <td className="py-3 px-4 text-slate-400">{contact.role}</td>

                      {/* Phone */}
                      <td className="py-3 px-4 font-mono text-cyan-300">
                        {contact.phoneNumber}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleSendTestSms(contact)}
                            disabled={sendingId === contact.id}
                            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-800/60 flex items-center gap-1.5 hover:border-cyan-400 transition-all disabled:opacity-50"
                            title="Send individual test SMS"
                          >
                            <Send className={`w-3 h-3 ${sendingId === contact.id ? "animate-pulse" : ""}`} />
                            <span>{sendingId === contact.id ? "Sending..." : "Test SMS"}</span>
                          </button>

                          <button
                            onClick={() => handleDeleteContact(contact.id, contact.name)}
                            className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-950/30 transition-colors"
                            title="Remove contact"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Real-time Termux Execution Log Drawer */}
          <div className="bg-[#050A14] border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <div className="flex items-center gap-2">
                <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                <span className="font-bold text-slate-200">Termux SSH Command Dispatch Stream</span>
              </div>
              <span className="text-slate-500">Auto-logged on each alert drill</span>
            </div>

            <div className="bg-[#02050A] rounded-lg p-3 max-h-36 overflow-y-auto space-y-1.5 text-[11px] font-mono border border-slate-900 custom-scrollbar">
              {logs.length === 0 ? (
                <div className="text-slate-600 italic">
                  No SMS dispatches yet. Click "Test SMS" or trigger [3. COLLAPSE DRILL] to watch live commands.
                </div>
              ) : (
                logs.slice(0, 10).map((log) => (
                  <div key={log.id} className="leading-relaxed">
                    <div className="flex items-center gap-2 text-slate-400">
                      <span className="text-slate-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                      <span className={log.success ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>
                        {log.success ? "✔ DISPATCHED" : "✖ FAILED"}
                      </span>
                      <span className="text-cyan-400">{log.phoneNumber}</span>
                      <span className="text-slate-500">({log.durationMs}ms)</span>
                    </div>
                    <div className="text-slate-500 text-[10px] pl-4 truncate">
                      $ {log.command}
                    </div>
                    {log.error && (
                      <div className="text-red-400 text-[10px] pl-4">Error: {log.error}</div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="bg-[#0A101D] border-t border-slate-800 px-6 py-3 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Alerts automatically trigger SMS to active recipients on this list</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
