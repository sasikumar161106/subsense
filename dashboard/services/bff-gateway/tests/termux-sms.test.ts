import { describe, it, expect, beforeEach } from "vitest";
import { TermuxSmsService } from "../src/notifications/termux-sms";
import { EmergencyContactsStore } from "../src/notifications/contacts-store";
import { NotificationDispatcher } from "../src/notifications/dispatcher";
import { buildApp } from "../src/app";
import { AlertLifecycleEvent } from "@subsense/shared";

describe("Termux SSH SMS Dispatch & Emergency Contacts Store", () => {
  beforeEach(() => {
    EmergencyContactsStore.resetToDefault();
    TermuxSmsService.clearHistory();
  });

  it("sanitizes international phone numbers accurately", () => {
    expect(TermuxSmsService.sanitizePhoneNumber("+91 73581 60485")).toBe("+917358160485");
    expect(TermuxSmsService.sanitizePhoneNumber(" +91-7010-336-893 ")).toBe("+917010336893");
    expect(TermuxSmsService.sanitizePhoneNumber("9876543210")).toBe("9876543210");
  });

  it("escapes shell characters and quotes in messages safely", () => {
    const rawMsg = "Alert: Conveyor 'Cut-off' & immediate danger!\nNext line";
    const escaped = TermuxSmsService.escapeShellMessage(rawMsg);
    expect(escaped).not.toContain("\n");
    expect(escaped).toContain("'\\''Cut-off'\\''");
  });

  it("seeds primary contact +917358160485 by default", () => {
    const contacts = EmergencyContactsStore.getAll();
    expect(contacts.length).toBeGreaterThanOrEqual(2);
    const primary = contacts.find((c) => c.phoneNumber === "+917358160485");
    expect(primary).toBeDefined();
    expect(primary?.isActive).toBe(true);
  });

  it("adds, updates, and deletes emergency contacts", () => {
    const added = EmergencyContactsStore.add({
      name: "Ramesh Overman",
      role: "Mining Sirdar",
      phoneNumber: "+919876543200",
      isActive: true,
    });
    expect(added.id).toBeDefined();
    expect(added.name).toBe("Ramesh Overman");

    // Update
    const updated = EmergencyContactsStore.update(added.id, { isActive: false });
    expect(updated?.isActive).toBe(false);

    // Delete
    const deleted = EmergencyContactsStore.delete(added.id);
    expect(deleted).toBe(true);
    expect(EmergencyContactsStore.getAll().find((c) => c.id === added.id)).toBeUndefined();
  });

  it("dispatches SMS through NotificationDispatcher when critical alert triggers", async () => {
    const criticalAlert: AlertLifecycleEvent = {
      alert_id: "ALT-CRITICAL-TEST-001",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "critical",
      state: "new",
      raised_at: new Date().toISOString(),
      time_to_critical_hours: [1.0, 3.0],
      confidence_score: 0.98,
      contributing_sensors: ["displacement_mm", "tilt_deg"],
      explanation_summary: "Critical roof displacement breach.",
      acknowledged_by: null,
      acknowledged_at: null,
      escalated_at: null,
    };

    const dispatches = await NotificationDispatcher.dispatchAlert(criticalAlert);
    const smsDispatch = dispatches.find((d) => d.channel === "sms_twilio");
    expect(smsDispatch).toBeDefined();
    expect(smsDispatch?.delivered).toBe(true);
    expect(smsDispatch?.details).toContain("+917358160485");
  });

  it("handles GET /api/v1/sms/contacts and POST /api/v1/sms/send-test via Fastify app", async () => {
    const app = await buildApp();

    // GET /api/v1/sms/contacts
    const getRes = await app.inject({
      method: "GET",
      url: "/api/v1/sms/contacts",
    });
    expect(getRes.statusCode).toBe(200);
    const body = JSON.parse(getRes.body);
    expect(body.contacts).toBeDefined();
    expect(body.contacts.some((c: any) => c.phoneNumber === "+917358160485")).toBe(true);

    // POST /api/v1/sms/contacts
    const postRes = await app.inject({
      method: "POST",
      url: "/api/v1/sms/contacts",
      payload: {
        name: "Test Engineer",
        role: "Safety Lead",
        phoneNumber: "+919999988888",
      },
    });
    expect(postRes.statusCode).toBe(201);
    const postBody = JSON.parse(postRes.body);
    expect(postBody.success).toBe(true);
    expect(postBody.contact.name).toBe("Test Engineer");
  });
});
