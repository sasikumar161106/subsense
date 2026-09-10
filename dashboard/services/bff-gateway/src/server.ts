import { buildApp } from "./app";

const PORT = parseInt(process.env.PORT || "3001", 10);
const HOST = process.env.HOST || "0.0.0.0";

async function start() {
  try {
    const app = await buildApp();
    await app.listen({ port: PORT, host: HOST });
    console.log(`[SubSense Layer 6 BFF] Server listening at http://${HOST}:${PORT}`);
    console.log(`[SubSense Layer 6 BFF] WebSocket live stream at ws://${HOST}:${PORT}/ws/live`);
  } catch (err) {
    console.error("Fatal error starting BFF Gateway:", err);
    process.exit(1);
  }
}

start();
