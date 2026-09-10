import { randomUUID } from 'crypto';
import {
  AlertDeliveryRecord,
  AlertFeedbackRecord,
  AlertRecord,
  AlertSeverity,
  AlertStatus,
  AlertSource,
  AuditLogRecord,
  AuditTransition,
  CommunityRegistrantRecord,
  DeliveryChannel,
  DeliveryStatus,
  FeedbackVerdict,
  RiskZoneMetadata,
  TenantRecord
} from '../models/types';
import { getPrismaClient } from './client';
import { encrypt_phone_number, decrypt_phone_number } from '../security/encryption';

export const SEEDED_TENANTS: TenantRecord[] = [
  {
    tenant_id: 'tenant-jharia-01',
    tenant_name: 'Jharia Coalfield Block II',
    coalfield_region: 'Dhanbad, Jharkhand (BCCL)',
    zones: [
      {
        zone_id: 'zone-jharia-alpha',
        tenant_id: 'tenant-jharia-01',
        zone_name: 'Seam IV East Roadway',
        latitude: 23.7483,
        longitude: 86.4175,
        strata_profile: 'Interbedded Sandstone & Carbonaceous Shale',
        seam_depth_m: 240
      },
      {
        zone_id: 'zone-jharia-beta',
        tenant_id: 'tenant-jharia-01',
        zone_name: 'Pit Head 3 Overburden Dump',
        latitude: 23.755,
        longitude: 86.425,
        strata_profile: 'Loose Clay & Broken Sandstone Waste Dump',
        seam_depth_m: 45
      }
    ]
  },
  {
    tenant_id: 'tenant-raniganj-02',
    tenant_name: 'Raniganj Deep Mining Complex',
    coalfield_region: 'Asansol, West Bengal (ECL)',
    zones: [
      {
        zone_id: 'zone-raniganj-gamma',
        tenant_id: 'tenant-raniganj-02',
        zone_name: 'North Longwall Panel 7',
        latitude: 23.62,
        longitude: 87.125,
        strata_profile: 'Massive Sandstone Roof with High Horizontal Stress',
        seam_depth_m: 410
      },
      {
        zone_id: 'zone-raniganj-delta',
        tenant_id: 'tenant-raniganj-02',
        zone_name: 'South Incline Subsidence Zone',
        latitude: 23.61,
        longitude: 87.135,
        strata_profile: 'Fractured Sandstone with Abandoned Upper Goaf',
        seam_depth_m: 180
      }
    ]
  }
];

class DataRepository {
  private inMemoryAlerts: Map<string, AlertRecord> = new Map();
  private inMemoryDeliveries: AlertDeliveryRecord[] = [];
  private inMemoryFeedbacks: AlertFeedbackRecord[] = [];
  private inMemoryRegistrants: CommunityRegistrantRecord[] = [];
  private inMemoryAuditLogs: AuditLogRecord[] = [];
  private useInMemory: boolean = false;
  private dbChecked: boolean = false;

  public resetMemoryStore(): void {
    this.inMemoryAlerts.clear();
    this.inMemoryDeliveries = [];
    this.inMemoryFeedbacks = [];
    this.inMemoryRegistrants = [];
    this.inMemoryAuditLogs = [];
  }

  public setForceInMemory(force: boolean): void {
    this.useInMemory = force;
    this.dbChecked = true;
  }

  private async isDbAvailable(): Promise<boolean> {
    if (this.useInMemory) return false;
    if (this.dbChecked) return !this.useInMemory;

    try {
      const prisma = getPrismaClient();
      await prisma.$queryRaw`SELECT 1`;
      this.useInMemory = false;
      this.dbChecked = true;
      return true;
    } catch {
      this.useInMemory = true;
      this.dbChecked = true;
      console.warn(
        '[DATABASE] PostgreSQL is not reachable on localhost:5432. Falling back to in-memory state store for Phase 1.'
      );
      return false;
    }
  }

  // --- Alert Methods ---

  async findActiveAlerts(zone_id?: string, tenant_id?: string): Promise<AlertRecord[]> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const whereClause: any = {
        status: { in: ['Active', 'Escalated'] }
      };
      if (zone_id) {
        whereClause.risk_zone_id = zone_id;
      }
      if (tenant_id) {
        whereClause.tenant_id = tenant_id;
      }
      const rows = await prisma.alert.findMany({
        where: whereClause,
        include: { deliveries: true, feedbacks: true }
      });
      return rows.map(this.mapDbAlertToRecord);
    }

    const alerts = Array.from(this.inMemoryAlerts.values())
      .filter(
        (a) =>
          (a.status === AlertStatus.Active || a.status === AlertStatus.Escalated) &&
          (!zone_id || a.risk_zone_id === zone_id) &&
          (!tenant_id || a.tenant_id === tenant_id)
      )
      .map((a) => ({
        ...a,
        deliveries: this.inMemoryDeliveries.filter((d) => d.alert_id === a.alert_id),
        feedbacks: this.inMemoryFeedbacks.filter((f) => f.alert_id === a.alert_id)
      }));
    return alerts;
  }

  async findAlertById(alert_id: string): Promise<AlertRecord | null> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const row = await prisma.alert.findUnique({
        where: { alert_id },
        include: { deliveries: true, feedbacks: true }
      });
      return row ? this.mapDbAlertToRecord(row) : null;
    }

    const alert = this.inMemoryAlerts.get(alert_id) || null;
    if (!alert) return null;

    return {
      ...alert,
      deliveries: this.inMemoryDeliveries.filter((d) => d.alert_id === alert_id),
      feedbacks: this.inMemoryFeedbacks.filter((f) => f.alert_id === alert_id)
    };
  }

  async findAlerts(filter: {
    risk_zone_id?: string;
    zone_id?: string;
    severity?: string;
    status?: string;
    start_date?: Date;
    end_date?: Date;
    tenant_id?: string;
  }): Promise<AlertRecord[]> {
    const isDb = await this.isDbAvailable();
    const zoneId = filter.risk_zone_id || filter.zone_id;

    if (isDb) {
      const prisma = getPrismaClient();
      const whereClause: any = {};
      if (zoneId) whereClause.risk_zone_id = zoneId;
      if (filter.tenant_id) whereClause.tenant_id = filter.tenant_id;
      if (filter.severity) whereClause.severity = filter.severity as any;
      if (filter.status) whereClause.status = (filter.status === 'De-escalated' ? 'De_escalated' : filter.status) as any;
      if (filter.start_date || filter.end_date) {
        whereClause.created_at = {};
        if (filter.start_date) whereClause.created_at.gte = filter.start_date;
        if (filter.end_date) whereClause.created_at.lte = filter.end_date;
      }

      const rows = await prisma.alert.findMany({
        where: whereClause,
        orderBy: { created_at: 'desc' },
        include: { deliveries: true, feedbacks: true }
      });
      return rows.map(this.mapDbAlertToRecord);
    }

    let results = Array.from(this.inMemoryAlerts.values()).map((a) => ({
      ...a,
      deliveries: this.inMemoryDeliveries.filter((d) => d.alert_id === a.alert_id),
      feedbacks: this.inMemoryFeedbacks.filter((f) => f.alert_id === a.alert_id)
    }));
    if (zoneId) results = results.filter((a) => a.risk_zone_id === zoneId);
    if (filter.tenant_id) results = results.filter((a) => a.tenant_id === filter.tenant_id);
    if (filter.severity) results = results.filter((a) => a.severity === filter.severity);
    if (filter.status) results = results.filter((a) => a.status === filter.status);
    if (filter.start_date) results = results.filter((a) => new Date(a.created_at) >= filter.start_date!);
    if (filter.end_date) results = results.filter((a) => new Date(a.created_at) <= filter.end_date!);

    return results.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }

  async createAlert(
    data: Omit<AlertRecord, 'alert_id' | 'created_at' | 'updated_at'> & { alert_id?: string }
  ): Promise<AlertRecord> {
    const alert_id = data.alert_id || randomUUID();
    const now = new Date();
    const record: AlertRecord = {
      ...data,
      alert_id,
      created_at: now,
      updated_at: now,
      deliveries: [],
      feedbacks: []
    };

    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const dbStatus = data.status === AlertStatus.De_escalated ? 'De_escalated' : (data.status as any);
      const created = await prisma.alert.create({
        data: {
          alert_id,
          tenant_id: data.tenant_id,
          risk_zone_id: data.risk_zone_id,
          severity: data.severity as any,
          status: dbStatus,
          confidence_score: data.confidence_score,
          time_to_critical_hours: data.time_to_critical_hours,
          explanation: data.explanation,
          contributing_nodes: data.contributing_nodes,
          contributing_sensors: data.contributing_sensors,
          source: data.source as any,
          idempotency_key: data.idempotency_key
        }
      });
      return this.mapDbAlertToRecord(created);
    }

    this.inMemoryAlerts.set(alert_id, record);
    return record;
  }

  async updateAlert(alert_id: string, updates: Partial<AlertRecord>): Promise<AlertRecord> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const data: any = { ...updates };
      delete data.alert_id;
      delete data.created_at;
      delete data.deliveries;
      delete data.feedbacks;
      delete data.audit_logs;
      if (data.status === AlertStatus.De_escalated) {
        data.status = 'De_escalated';
      }

      const updated = await prisma.alert.update({
        where: { alert_id },
        data,
        include: { deliveries: true, feedbacks: true }
      });
      return this.mapDbAlertToRecord(updated);
    }

    const existing = this.inMemoryAlerts.get(alert_id);
    if (!existing) {
      throw new Error(`Alert with id ${alert_id} not found`);
    }

    const updated: AlertRecord = {
      ...existing,
      ...updates,
      updated_at: new Date()
    };
    this.inMemoryAlerts.set(alert_id, updated);
    return updated;
  }

  // --- Alert Deliveries ---

  async saveDeliveries(deliveries: AlertDeliveryRecord[]): Promise<void> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      for (const d of deliveries) {
        await prisma.alertDelivery.create({
          data: {
            delivery_id: d.delivery_id,
            alert_id: d.alert_id,
            channel: d.channel as any,
            recipient_ref: d.recipient_ref,
            delivery_status: d.delivery_status as any,
            attempted_at: d.attempted_at,
            delivered_at: d.delivered_at
          }
        });
      }
      return;
    }

    this.inMemoryDeliveries.push(...deliveries);
  }

  async getDeliveriesByAlertId(alert_id: string): Promise<AlertDeliveryRecord[]> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const rows = await prisma.alertDelivery.findMany({
        where: { alert_id }
      });
      return rows.map((r) => ({
        delivery_id: r.delivery_id,
        alert_id: r.alert_id,
        channel: r.channel as DeliveryChannel,
        recipient_ref: r.recipient_ref,
        delivery_status: r.delivery_status as DeliveryStatus,
        attempted_at: r.attempted_at,
        delivered_at: r.delivered_at
      }));
    }

    return this.inMemoryDeliveries.filter((d) => d.alert_id === alert_id);
  }

  async findDeliveryById(delivery_id: string): Promise<AlertDeliveryRecord | null> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const row = await prisma.alertDelivery.findUnique({
        where: { delivery_id }
      });
      if (!row) return null;
      return {
        delivery_id: row.delivery_id,
        alert_id: row.alert_id,
        channel: row.channel as DeliveryChannel,
        recipient_ref: row.recipient_ref,
        delivery_status: row.delivery_status as DeliveryStatus,
        attempted_at: row.attempted_at,
        delivered_at: row.delivered_at
      };
    }

    return this.inMemoryDeliveries.find((d) => d.delivery_id === delivery_id) || null;
  }

  async updateDelivery(
    delivery_id: string,
    updates: Partial<AlertDeliveryRecord>
  ): Promise<AlertDeliveryRecord | null> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const data: any = {};
      if (updates.delivery_status) data.delivery_status = updates.delivery_status as any;
      if (updates.delivered_at !== undefined) data.delivered_at = updates.delivered_at;

      const updated = await prisma.alertDelivery.update({
        where: { delivery_id },
        data
      });
      return {
        delivery_id: updated.delivery_id,
        alert_id: updated.alert_id,
        channel: updated.channel as DeliveryChannel,
        recipient_ref: updated.recipient_ref,
        delivery_status: updated.delivery_status as DeliveryStatus,
        attempted_at: updated.attempted_at,
        delivered_at: updated.delivered_at
      };
    }

    const idx = this.inMemoryDeliveries.findIndex((d) => d.delivery_id === delivery_id);
    if (idx === -1) return null;

    const existing = this.inMemoryDeliveries[idx];
    const updated: AlertDeliveryRecord = {
      ...existing,
      ...updates
    };
    this.inMemoryDeliveries[idx] = updated;
    return updated;
  }

  // --- Alert Feedback ---

  async createFeedback(feedback: AlertFeedbackRecord): Promise<AlertFeedbackRecord> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const created = await prisma.alertFeedback.create({
        data: {
          feedback_id: feedback.feedback_id,
          alert_id: feedback.alert_id,
          operator_id: feedback.operator_id,
          verdict: feedback.verdict as any,
          notes: feedback.notes,
          submitted_at: feedback.submitted_at
        }
      });
      return {
        feedback_id: created.feedback_id,
        alert_id: created.alert_id,
        operator_id: created.operator_id,
        verdict: created.verdict as FeedbackVerdict,
        notes: created.notes,
        submitted_at: created.submitted_at
      };
    }

    const feedback_id = feedback.feedback_id || randomUUID();
    const record: AlertFeedbackRecord = { ...feedback, feedback_id };
    this.inMemoryFeedbacks.push(record);
    return record;
  }

  // --- Community Registrants (with AES-256-GCM Encryption at Rest) ---

  async createRegistrant(registrant: CommunityRegistrantRecord): Promise<CommunityRegistrantRecord> {
    const registrant_id = registrant.registrant_id || randomUUID();
    const rawPlainPhone = decrypt_phone_number(registrant.phone_number);
    const encryptedPhone = encrypt_phone_number(rawPlainPhone);

    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const created = await prisma.communityRegistrant.create({
        data: {
          registrant_id,
          tenant_id: registrant.tenant_id,
          risk_zone_id: registrant.risk_zone_id,
          phone_number: encryptedPhone,
          preferred_language: registrant.preferred_language,
          opted_in: registrant.opted_in
        }
      });
      return {
        ...created,
        phone_number: rawPlainPhone
      };
    }

    const record: CommunityRegistrantRecord = {
      ...registrant,
      registrant_id,
      phone_number: encryptedPhone
    };
    this.inMemoryRegistrants.push(record);
    return {
      ...record,
      phone_number: rawPlainPhone
    };
  }

  async getRegistrants(risk_zone_id?: string, tenant_id?: string): Promise<CommunityRegistrantRecord[]> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const where: any = {};
      if (risk_zone_id) where.risk_zone_id = risk_zone_id;
      if (tenant_id) where.tenant_id = tenant_id;
      const rows = await prisma.communityRegistrant.findMany({ where });
      return rows.map((r) => ({
        ...r,
        phone_number: decrypt_phone_number(r.phone_number)
      }));
    }

    let records = this.inMemoryRegistrants;
    if (risk_zone_id) {
      records = records.filter((r) => r.risk_zone_id === risk_zone_id);
    }
    if (tenant_id) {
      records = records.filter((r) => r.tenant_id === tenant_id);
    }
    return records.map((r) => ({
      ...r,
      phone_number: decrypt_phone_number(r.phone_number)
    }));
  }

  /**
   * Helper to retrieve raw stored ciphertext for verification of encryption at rest
   */
  async getRawRegistrantPhone(registrant_id: string): Promise<string | undefined> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      const row = await prisma.communityRegistrant.findUnique({ where: { registrant_id } });
      return row?.phone_number;
    }
    const rec = this.inMemoryRegistrants.find((r) => r.registrant_id === registrant_id);
    return rec?.phone_number;
  }

  // --- Audit Log ---

  async insertAuditLog(log: AuditLogRecord): Promise<void> {
    const isDb = await this.isDbAvailable();
    if (isDb) {
      const prisma = getPrismaClient();
      await prisma.auditLog.create({
        data: {
          log_id: log.log_id,
          alert_id: log.alert_id,
          transition: log.transition,
          timestamp: log.timestamp,
          snapshot: log.snapshot as any,
          metadata: log.metadata ? (log.metadata as any) : undefined
        }
      });
      return;
    }

    this.inMemoryAuditLogs.push(log);
  }

  async getAuditLogs(
    query?: string | { alert_id?: string; tenant_id?: string; start_date?: Date; end_date?: Date }
  ): Promise<AuditLogRecord[]> {
    const isDb = await this.isDbAvailable();
    const filter = typeof query === 'string' ? { alert_id: query } : (query || {});

    if (isDb) {
      const prisma = getPrismaClient();
      const where: any = {};
      if (filter.alert_id) where.alert_id = filter.alert_id;
      if (filter.start_date || filter.end_date) {
        where.timestamp = {};
        if (filter.start_date) where.timestamp.gte = filter.start_date;
        if (filter.end_date) where.timestamp.lte = filter.end_date;
      }
      const rows = await prisma.auditLog.findMany({
        where,
        orderBy: { timestamp: 'asc' }
      });
      let mapped = rows.map((r) => ({
        log_id: r.log_id,
        alert_id: r.alert_id,
        transition: r.transition as AuditTransition,
        timestamp: r.timestamp,
        snapshot: r.snapshot as any,
        metadata: r.metadata as any
      }));
      if (filter.tenant_id) {
        mapped = mapped.filter((m) => m.snapshot?.tenant_id === filter.tenant_id);
      }
      return mapped;
    }

    let logs = [...this.inMemoryAuditLogs];
    if (filter.alert_id) {
      logs = logs.filter((a) => a.alert_id === filter.alert_id);
    }
    if (filter.tenant_id) {
      logs = logs.filter((a) => a.snapshot?.tenant_id === filter.tenant_id);
    }
    if (filter.start_date) {
      logs = logs.filter((a) => new Date(a.timestamp) >= filter.start_date!);
    }
    if (filter.end_date) {
      logs = logs.filter((a) => new Date(a.timestamp) <= filter.end_date!);
    }
    return logs.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }

  // --- Phase 3 Tenant & Zone Queries ---

  getTenants(): TenantRecord[] {
    return SEEDED_TENANTS;
  }

  getTenantById(tenant_id: string): TenantRecord | undefined {
    return SEEDED_TENANTS.find((t) => t.tenant_id === tenant_id);
  }

  getZones(tenant_id?: string): RiskZoneMetadata[] {
    if (tenant_id) {
      const tenant = this.getTenantById(tenant_id);
      return tenant ? tenant.zones : [];
    }
    return SEEDED_TENANTS.flatMap((t) => t.zones);
  }

  private mapDbAlertToRecord(row: any): AlertRecord {
    return {
      alert_id: row.alert_id,
      tenant_id: row.tenant_id,
      risk_zone_id: row.risk_zone_id,
      severity: row.severity as AlertSeverity,
      status: (row.status === 'De_escalated' ? AlertStatus.De_escalated : row.status) as AlertStatus,
      confidence_score: row.confidence_score,
      time_to_critical_hours: row.time_to_critical_hours,
      explanation: row.explanation,
      contributing_nodes: row.contributing_nodes,
      contributing_sensors: row.contributing_sensors,
      source: row.source as AlertSource,
      idempotency_key: row.idempotency_key,
      created_at: row.created_at,
      updated_at: row.updated_at,
      deliveries: row.deliveries ? row.deliveries.map((d: any) => ({
        delivery_id: d.delivery_id,
        alert_id: d.alert_id,
        channel: d.channel,
        recipient_ref: d.recipient_ref,
        delivery_status: d.delivery_status,
        attempted_at: d.attempted_at,
        delivered_at: d.delivered_at
      })) : undefined,
      feedbacks: row.feedbacks ? row.feedbacks.map((f: any) => ({
        feedback_id: f.feedback_id,
        alert_id: f.alert_id,
        operator_id: f.operator_id,
        verdict: f.verdict,
        notes: f.notes,
        submitted_at: f.submitted_at
      })) : undefined
    };
  }
}

export const repository = new DataRepository();
