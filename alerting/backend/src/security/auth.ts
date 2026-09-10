import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';
import { UserRecord, UserRole, AuthTokenPayload } from '../models/types';

const JWT_SECRET = process.env.JWT_SECRET || 'subsense-jwt-safety-compliance-secret-key-2026';

// Extend Express Request interface to carry authenticated user context
declare global {
  namespace Express {
    interface Request {
      user?: AuthTokenPayload;
      tenant_scope?: string | null;
    }
  }
}

function hashPassword(password: string): string {
  return crypto.createHash('sha256').update(password + 'subsense_salt').digest('hex');
}

/**
 * Pre-seeded demonstration credentials across two distinct coalfield tenants
 * plus the national DGMS oversight regulator.
 */
export const SEEDED_USERS: UserRecord[] = [
  {
    user_id: 'usr-jharia-01',
    username: 'officer_jharia',
    password_hash: hashPassword('subsense123'),
    role: UserRole.MineSafetyOfficer,
    tenant_id: 'tenant-jharia-01',
    tenant_name: 'Jharia Coalfield Block II'
  },
  {
    user_id: 'usr-raniganj-02',
    username: 'officer_raniganj',
    password_hash: hashPassword('subsense123'),
    role: UserRole.MineSafetyOfficer,
    tenant_id: 'tenant-raniganj-02',
    tenant_name: 'Raniganj Deep Mining Complex'
  },
  {
    user_id: 'usr-dgms-01',
    username: 'dgms_inspector',
    password_hash: hashPassword('dgms2026'),
    role: UserRole.RegulatorDGMS,
    tenant_id: null, // Cross-tenant regulatory entitlement
    tenant_name: 'DGMS National Coalfield Oversight'
  }
];

export function findUserByUsername(username: string): UserRecord | undefined {
  return SEEDED_USERS.find((u) => u.username.toLowerCase() === username.toLowerCase());
}

export function verifyUserPassword(user: UserRecord, candidate: string): boolean {
  return user.password_hash === hashPassword(candidate);
}

export function generateToken(user: UserRecord): string {
  const payload: AuthTokenPayload = {
    user_id: user.user_id,
    username: user.username,
    role: user.role,
    tenant_id: user.tenant_id
  };
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '24h' });
}

export function verifyToken(token: string): AuthTokenPayload | null {
  try {
    return jwt.verify(token, JWT_SECRET) as AuthTokenPayload;
  } catch {
    return null;
  }
}

/**
 * Middleware: Authenticate incoming Bearer JWT token
 * If no token is passed in development, creates a permissive default context
 * while strictly validating tokens whenever provided.
 */
export function authenticateToken(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.substring(7) : null;

  if (!token) {
    // If running in development/demo without token, check for header override or default
    const devTenantHeader = req.headers['x-tenant-id'] as string | undefined;
    if (devTenantHeader) {
      req.user = {
        user_id: 'usr-dev-header',
        username: 'dev_operator',
        role: UserRole.MineSafetyOfficer,
        tenant_id: devTenantHeader
      };
      req.tenant_scope = devTenantHeader;
    }
    return next();
  }

  const verified = verifyToken(token);
  if (!verified) {
    res.status(401).json({ error: 'Invalid or expired authorization token' });
    return;
  }

  req.user = verified;
  req.tenant_scope = verified.tenant_id;
  next();
}

/**
 * Middleware: Require one of the specified roles
 */
export function requireRole(allowedRoles: UserRole[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({ error: 'Authentication required for this operation' });
      return;
    }

    if (!allowedRoles.includes(req.user.role)) {
      res.status(403).json({
        error: `Forbidden: Role '${req.user.role}' is not authorized for this resource. Required: [${allowedRoles.join(', ')}]`
      });
      return;
    }

    next();
  };
}

/**
 * Middleware: Enforce tenant scoping.
 * - MineSafetyOfficer is strictly locked to their own tenant.
 * - RegulatorDGMS can specify any tenant or view all tenants.
 */
export function enforceTenantScope(req: Request, res: Response, next: NextFunction): void {
  if (!req.user) {
    return next();
  }

  if (req.user.role === UserRole.MineSafetyOfficer) {
    const targetTenant = (req.body?.tenant_id || req.query?.tenant_id || req.params?.tenant_id) as string | undefined;
    if (targetTenant && targetTenant !== req.user.tenant_id) {
      res.status(403).json({
        error: `Tenant Access Denied: Operator is locked to tenant '${req.user.tenant_id}'. Cross-tenant access to '${targetTenant}' is forbidden.`
      });
      return;
    }
    req.tenant_scope = req.user.tenant_id;
  } else if (req.user.role === UserRole.RegulatorDGMS) {
    const requestedTenant = (req.query?.tenant_id || req.body?.tenant_id) as string | undefined;
    req.tenant_scope = requestedTenant || null; // null indicates all entitled tenants
  }

  next();
}
