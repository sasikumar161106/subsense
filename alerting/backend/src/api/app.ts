import express from 'express';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import { alertsRouter } from './routes/alerts';
import { communityRouter } from './routes/community';
import { webhooksRouter } from './routes/webhooks';
import { authRouter } from './routes/auth';
import { auditRouter } from './routes/audit';

export const app = express();

app.use(cors());
app.use(express.json({ limit: '2mb' }));

// Rate limiter on public inbound webhook endpoints to prevent abuse / DDoS
const webhookLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute window
  max: 120, // limit each IP to 120 requests per window
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many webhook requests from this IP, please try again later.' }
});

// Mount API routes
app.use('/api/v1/auth', authRouter);
app.use('/api/v1/alerts', alertsRouter);
app.use('/api/v1/community', communityRouter);
app.use('/api/v1/audit', auditRouter);
app.use('/api/v1/webhooks', webhookLimiter, webhooksRouter);
app.use('/webhooks', webhookLimiter, webhooksRouter);

// Health check endpoint
app.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'SubSense Alerting & Decision Support System (Phase 3)',
    timestamp: new Date()
  });
});
