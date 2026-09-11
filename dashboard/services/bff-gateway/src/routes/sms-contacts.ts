import { FastifyPluginAsync } from "fastify";
import { EmergencyContactsStore } from "../notifications/contacts-store";
import { TermuxSmsService } from "../notifications/termux-sms";

export const smsContactsRoutes: FastifyPluginAsync = async (fastify) => {
  // 1. List all emergency contacts
  fastify.get("/api/v1/sms/contacts", async () => {
    return {
      contacts: EmergencyContactsStore.getAll(),
      config: TermuxSmsService.getConfig(),
    };
  });

  // 2. Add new emergency contact
  fastify.post<{
    Body: { name: string; role: string; phoneNumber: string; isActive?: boolean };
  }>("/api/v1/sms/contacts", async (request, reply) => {
    const { name, role, phoneNumber, isActive } = request.body || {};

    if (!name || !phoneNumber) {
      return reply.status(400).send({ error: "Missing required fields: 'name' and 'phoneNumber'" });
    }

    const created = EmergencyContactsStore.add({
      name,
      role: role || "Personnel",
      phoneNumber,
      isActive: isActive ?? true,
    });

    return reply.status(201).send({ success: true, contact: created });
  });

  // 3. Update existing contact
  fastify.put<{
    Params: { id: string };
    Body: { name?: string; role?: string; phoneNumber?: string; isActive?: boolean };
  }>("/api/v1/sms/contacts/:id", async (request, reply) => {
    const { id } = request.params;
    const updated = EmergencyContactsStore.update(id, request.body);

    if (!updated) {
      return reply.status(404).send({ error: `Contact not found: ${id}` });
    }

    return { success: true, contact: updated };
  });

  // 4. Delete contact
  fastify.delete<{
    Params: { id: string };
  }>("/api/v1/sms/contacts/:id", async (request, reply) => {
    const { id } = request.params;
    const deleted = EmergencyContactsStore.delete(id);

    if (!deleted) {
      return reply.status(404).send({ error: `Contact not found: ${id}` });
    }

    return { success: true, message: `Contact ${id} deleted` };
  });

  // 5. Send Test SMS via Termux SSH
  fastify.post<{
    Body: { phoneNumber?: string; message?: string };
  }>("/api/v1/sms/send-test", async (request, reply) => {
    const { phoneNumber, message } = request.body || {};

    const testMsg =
      message ||
      `[SubSense TEST] SubSense Smart Mine Early-Warning Platform connected via Termux. Time: ${new Date().toLocaleTimeString("en-IN")}`;

    if (phoneNumber) {
      // Send to single specified number
      const result = await TermuxSmsService.sendSms(phoneNumber, testMsg, "Test Recipient");
      return {
        success: result.success,
        results: [result],
        command: result.command,
        output: result.output,
        durationMs: result.durationMs,
      };
    } else {
      // Broadcast to all active contacts
      const activeContacts = EmergencyContactsStore.getActive();
      if (activeContacts.length === 0) {
        return reply.status(400).send({ error: "No active emergency contacts found to send test SMS." });
      }

      const results = await Promise.all(
        activeContacts.map((c) => TermuxSmsService.sendSms(c.phoneNumber, testMsg, c.name))
      );

      const allSuccess = results.every((r) => r.success);
      return {
        success: allSuccess,
        results,
        count: results.length,
        durationMs: results.reduce((max, r) => Math.max(max, r.durationMs), 0),
      };
    }
  });

  // 6. Get SMS dispatch history logs
  fastify.get("/api/v1/sms/logs", async () => {
    return {
      logs: TermuxSmsService.getHistory(),
      count: TermuxSmsService.getHistory().length,
    };
  });

  // 7. Update SSH gateway configuration
  fastify.post<{
    Body: { host?: string; port?: number; user?: string };
  }>("/api/v1/sms/config", async (request, reply) => {
    const session = (request as any).userSession;
    if (!session || (session.role !== "site_admin" && session.role !== "technical_lead")) {
      return reply.status(403).send({ error: "Forbidden: Only Site Administrator or Technical Lead can update SMS config" });
    }
    TermuxSmsService.setConfig(request.body || {});
    return {
      success: true,
      config: TermuxSmsService.getConfig(),
    };
  });
};
