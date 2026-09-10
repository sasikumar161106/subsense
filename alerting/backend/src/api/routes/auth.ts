import { Router, Request, Response } from 'express';
import {
  findUserByUsername,
  verifyUserPassword,
  generateToken,
  authenticateToken,
  SEEDED_USERS
} from '../../security/auth';
import { repository } from '../../db/repository';
import { UserRole } from '../../models/types';

export const authRouter = Router();

/**
 * POST /api/v1/auth/login
 * Authenticate credentials and return signed JWT + tenant context
 */
authRouter.post('/login', async (req: Request, res: Response): Promise<void> => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      res.status(400).json({ error: 'Username and password are required' });
      return;
    }

    const user = findUserByUsername(username);
    if (!user || !verifyUserPassword(user, password)) {
      res.status(401).json({ error: 'Invalid username or password' });
      return;
    }

    const token = generateToken(user);

    res.json({
      token,
      user: {
        user_id: user.user_id,
        username: user.username,
        role: user.role,
        tenant_id: user.tenant_id,
        tenant_name: user.tenant_name
      }
    });
  } catch (error: any) {
    console.error('[AUTH ERROR] Login failed:', error);
    res.status(500).json({ error: 'Authentication internal failure', details: error.message });
  }
});

/**
 * GET /api/v1/auth/me
 * Return current authenticated user context and tenant details
 */
authRouter.get('/me', authenticateToken, async (req: Request, res: Response): Promise<void> => {
  if (!req.user) {
    res.status(401).json({ error: 'Unauthenticated' });
    return;
  }

  const tenant = req.user.tenant_id ? repository.getTenantById(req.user.tenant_id) : null;

  res.json({
    user: req.user,
    tenant
  });
});

/**
 * GET /api/v1/auth/tenants
 * List tenants entitled to current caller (all for RegulatorDGMS, scoped for MineSafetyOfficer)
 */
authRouter.get('/tenants', authenticateToken, async (req: Request, res: Response): Promise<void> => {
  const user = req.user;

  if (user && user.role === UserRole.MineSafetyOfficer && user.tenant_id) {
    const tenant = repository.getTenantById(user.tenant_id);
    res.json(tenant ? [tenant] : []);
    return;
  }

  // Regulators or unauthenticated demo can see all tenants
  res.json(repository.getTenants());
});

/**
 * GET /api/v1/auth/zones
 * List risk zones entitled to current caller
 */
authRouter.get('/zones', authenticateToken, async (req: Request, res: Response): Promise<void> => {
  const user = req.user;
  const targetTenant = (user && user.role === UserRole.MineSafetyOfficer ? user.tenant_id : req.query.tenant_id) as string | undefined;

  res.json(repository.getZones(targetTenant));
});
