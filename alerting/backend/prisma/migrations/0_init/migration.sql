-- CreateEnum
CREATE TYPE "AlertSeverity" AS ENUM ('Advisory', 'Warning', 'Critical');

-- CreateEnum
CREATE TYPE "AlertStatus" AS ENUM ('Active', 'Escalated', 'De-escalated', 'Resolved', 'Retracted');

-- CreateEnum
CREATE TYPE "AlertSource" AS ENUM ('Edge', 'Cloud');

-- CreateEnum
CREATE TYPE "DeliveryChannel" AS ENUM ('Siren', 'SMS', 'Email', 'PushNotification', 'DashboardBanner', 'VoiceIVR', 'CommunitySMS');

-- CreateEnum
CREATE TYPE "DeliveryStatus" AS ENUM ('Queued', 'Sent', 'Delivered', 'Failed', 'Retrying');

-- CreateEnum
CREATE TYPE "FeedbackVerdict" AS ENUM ('Confirmed', 'FalsePositive', 'Unclear', 'HardwareDefect');

-- CreateTable Alert
CREATE TABLE "alerts" (
    "alert_id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "risk_zone_id" UUID NOT NULL,
    "severity" "AlertSeverity" NOT NULL,
    "status" "AlertStatus" NOT NULL,
    "confidence_score" DOUBLE PRECISION NOT NULL,
    "time_to_critical_hours" DOUBLE PRECISION,
    "explanation" TEXT NOT NULL,
    "contributing_nodes" UUID[] NOT NULL,
    "contributing_sensors" TEXT[] NOT NULL,
    "source" "AlertSource" NOT NULL,
    "idempotency_key" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "alerts_pkey" PRIMARY KEY ("alert_id")
);

-- CreateTable AlertDelivery
CREATE TABLE "alert_deliveries" (
    "delivery_id" UUID NOT NULL,
    "alert_id" UUID NOT NULL,
    "channel" "DeliveryChannel" NOT NULL,
    "recipient_ref" TEXT NOT NULL,
    "delivery_status" "DeliveryStatus" NOT NULL,
    "attempted_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "delivered_at" TIMESTAMPTZ,

    CONSTRAINT "alert_deliveries_pkey" PRIMARY KEY ("delivery_id")
);

-- CreateTable AlertFeedback
CREATE TABLE "alert_feedbacks" (
    "feedback_id" UUID NOT NULL,
    "alert_id" UUID NOT NULL,
    "operator_id" UUID NOT NULL,
    "verdict" "FeedbackVerdict" NOT NULL,
    "notes" TEXT,
    "submitted_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "alert_feedbacks_pkey" PRIMARY KEY ("feedback_id")
);

-- CreateTable CommunityRegistrant
CREATE TABLE "community_registrants" (
    "registrant_id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "risk_zone_id" UUID NOT NULL,
    "phone_number" TEXT NOT NULL,
    "preferred_language" VARCHAR(10) NOT NULL,
    "opted_in" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "community_registrants_pkey" PRIMARY KEY ("registrant_id")
);

-- CreateTable AuditLog
CREATE TABLE "audit_log" (
    "log_id" UUID NOT NULL,
    "alert_id" UUID NOT NULL,
    "transition" VARCHAR(50) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "snapshot" JSONB NOT NULL,
    "metadata" JSONB,

    CONSTRAINT "audit_log_pkey" PRIMARY KEY ("log_id")
);

-- UniqueIndex on idempotency_key
CREATE UNIQUE INDEX "alerts_idempotency_key_key" ON "alerts"("idempotency_key");

-- Indexes on alerts
CREATE INDEX "alerts_risk_zone_id_status_idx" ON "alerts"("risk_zone_id", "status");
CREATE INDEX "alerts_created_at_idx" ON "alerts"("created_at");

-- Indexes on alert_deliveries
CREATE INDEX "alert_deliveries_alert_id_idx" ON "alert_deliveries"("alert_id");

-- Indexes on alert_feedbacks
CREATE INDEX "alert_feedbacks_alert_id_idx" ON "alert_feedbacks"("alert_id");

-- Indexes on community_registrants
CREATE INDEX "community_registrants_tenant_id_risk_zone_id_idx" ON "community_registrants"("tenant_id", "risk_zone_id");

-- Indexes on audit_log
CREATE INDEX "audit_log_alert_id_idx" ON "audit_log"("alert_id");
CREATE INDEX "audit_log_timestamp_idx" ON "audit_log"("timestamp");

-- Foreign Keys
ALTER TABLE "alert_deliveries" ADD CONSTRAINT "alert_deliveries_alert_id_fkey" FOREIGN KEY ("alert_id") REFERENCES "alerts"("alert_id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "alert_feedbacks" ADD CONSTRAINT "alert_feedbacks_alert_id_fkey" FOREIGN KEY ("alert_id") REFERENCES "alerts"("alert_id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "audit_log" ADD CONSTRAINT "audit_log_alert_id_fkey" FOREIGN KEY ("alert_id") REFERENCES "alerts"("alert_id") ON DELETE CASCADE ON UPDATE CASCADE;
