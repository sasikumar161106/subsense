import Fastify, { FastifyInstance } from "fastify";
import cors from "@fastify/cors";
import rateLimit from "@fastify/rate-limit";
import websocket from "@fastify/websocket";
import { authRoutes } from "./routes/auth";
import { provisioningRoutes } from "./routes/provisioning";
import { contractsRoutes } from "./routes/contracts";
import { alertsRoutes } from "./routes/alerts";
import { trendsRoutes } from "./routes/trends";
import { meshRoutes } from "./routes/mesh";
import { tenantsRoutes } from "./routes/tenants";
import { regulatorRoutes } from "./routes/regulator";
import { smsContactsRoutes } from "./routes/sms-contacts";
import { verifyUserToken } from "./auth/service";
import { GatewayWebSocketServer } from "./ws/gateway-ws";
import { seedDatabase } from "./db/seed";

export async function buildApp(): Promise<FastifyInstance> {
  const app = Fastify({
    logger: false,
  });

  // Enable CORS for web dashboard
  await app.register(cors, {
    origin: true,
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    credentials: true,
  });

  // Rate Limiting (1000 requests per minute)
  await app.register(rateLimit, {
    max: 1000,
    timeWindow: "1 minute",
  });

  // WebSocket support
  await app.register(websocket);

  // Authentication & Session Interceptor Hook
  app.addHook("onRequest", async (request, reply) => {
    const authHeader = request.headers.authorization;
    if (authHeader && authHeader.startsWith("Bearer ")) {
      const token = authHeader.substring(7);
      const session = verifyUserToken(token);
      if (session) {
        (request as any).userSession = session;
      }
    } else {
      // Support tenant header or test role header for developer convenience
      const roleHeader = request.headers["x-user-role"] as string;
      const tenantHeader = request.headers["x-tenant-id"] as string;
      const userHeader = request.headers["x-user-id"] as string;

      if (roleHeader) {
        (request as any).userSession = {
          userId: userHeader || "USR-OP-8492",
          email: "operator.ecl@subsense.gov.in",
          name: "Rajesh Kumar",
          role: roleHeader,
          tenantId: tenantHeader || "OPCO-ECL-01",
          jurisdictionId: "JUR-DGMS-EAST",
          mfaVerified: true,
        };
      }
    }
  });

  // Seed database
  await seedDatabase();

  // Register WebSocket server
  GatewayWebSocketServer.register(app);

  // Register REST Routes
  await app.register(authRoutes);
  await app.register(provisioningRoutes);
  await app.register(contractsRoutes);
  await app.register(alertsRoutes);
  await app.register(trendsRoutes);
  await app.register(meshRoutes);
  await app.register(tenantsRoutes);
  await app.register(regulatorRoutes);
  await app.register(smsContactsRoutes);

  // Health check endpoint
  app.get("/health", async () => {
    return {
      status: "healthy",
      service: "SubSense BFF Gateway",
      layer: "Layer 6 - Dashboard & Application Layer",
      architecture: "SUBSENSE-TDD-APP-006 Rev 2.1",
      timestamp: new Date().toISOString(),
    };
  });

  return app;
}
