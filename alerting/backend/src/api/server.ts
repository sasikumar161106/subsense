import dotenv from 'dotenv';
dotenv.config();

import { app } from './app';
import { reevaluate_all_active_alerts } from '../rule-engine/reevaluation';
import { wsManager } from '../channels/adapters/dashboard';
import { createServerInstance } from '../security/https';

const PORT = process.env.PORT || 3000;
const protocol = process.env.USE_HTTPS === 'true' ? 'https' : 'http';
const wsProtocol = process.env.USE_HTTPS === 'true' ? 'wss' : 'ws';

const server = createServerInstance(app);

server.listen(PORT, () => {
  console.log(`=======================================================`);
  console.log(`  SubSense Alerting & Decision Support System (Phase 3)`);
  console.log(`  Listening on ${protocol}://localhost:${PORT}`);
  console.log(`  WebSocket live stream: ${wsProtocol}://localhost:${PORT}/ws/alerts`);
  console.log(`=======================================================`);

  // Initialize WebSocket server attached to HTTP/HTTPS server
  wsManager.init(server);

  // Start periodic 60s background sweep for active and escalated alerts
  const sweepInterval = setInterval(async () => {
    try {
      await reevaluate_all_active_alerts();
    } catch (err) {
      console.error('[REEVALUATION SWEEP ERROR]', err);
    }
  }, 60 * 1000);

  sweepInterval.unref();
});

export default server;
