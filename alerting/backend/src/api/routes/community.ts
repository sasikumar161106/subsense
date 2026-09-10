import { Router, Request, Response } from 'express';
import { randomUUID } from 'crypto';
import { repository } from '../../db/repository';
import { CommunityRegistrantRecord, UserRole } from '../../models/types';
import { authenticateToken } from '../../security/auth';

export const communityRouter = Router();
communityRouter.use(authenticateToken);

/**
 * POST /api/v1/community/registrants
 * Register a community member in a subsidence risk zone
 */
communityRouter.post('/registrants', async (req: Request, res: Response): Promise<void> => {
  try {
    const { tenant_id, risk_zone_id, phone_number, preferred_language, opted_in } = req.body;

    if (!tenant_id || !risk_zone_id || !phone_number || !preferred_language) {
      res.status(400).json({
        error: 'tenant_id, risk_zone_id, phone_number, and preferred_language are required'
      });
      return;
    }

    const registrant: CommunityRegistrantRecord = {
      registrant_id: randomUUID(),
      tenant_id,
      risk_zone_id,
      phone_number,
      preferred_language,
      opted_in: Boolean(opted_in)
    };

    const saved = await repository.createRegistrant(registrant);
    res.status(201).json(saved);
  } catch (error: any) {
    console.error('[API ERROR] Failed to register community member:', error);
    res.status(500).json({ error: 'Failed to register community member', details: error.message });
  }
});

/**
 * GET /api/v1/community/registrants
 * Retrieve registrants optionally filtered by risk_zone_id
 */
communityRouter.get('/registrants', async (req: Request, res: Response): Promise<void> => {
  try {
    const { zone_id, risk_zone_id } = req.query;
    const zone = (risk_zone_id || zone_id) as string | undefined;
    let tenantId = (req.query.tenant_id as string) || undefined;

    if (req.user && req.user.role === UserRole.MineSafetyOfficer && req.user.tenant_id) {
      tenantId = req.user.tenant_id;
    }

    const registrants = await repository.getRegistrants(zone, tenantId);
    res.json(registrants);
  } catch (error: any) {
    console.error('[API ERROR] Failed to fetch registrants:', error);
    res.status(500).json({ error: 'Failed to fetch registrants', details: error.message });
  }
});
