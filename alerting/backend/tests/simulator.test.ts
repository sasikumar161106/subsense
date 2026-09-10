import { repository } from '../src/db/repository';
import { runSimulator } from '../src/simulator';
import { audit_logger } from '../src/audit/logger';

describe('Simulator Verification Test', () => {
  beforeEach(() => {
    repository.resetMemoryStore();
  });

  test('runSimulator should execute all 5 scenarios and produce clean DGMS audit trail', async () => {
    await expect(runSimulator()).resolves.not.toThrow();

    const auditLogs = await audit_logger.get_all_audit_logs();
    const transitions = auditLogs.map((l) => l.transition);

    expect(transitions).toContain('created');
    expect(transitions).toContain('merged');
    expect(transitions).toContain('escalated');
    expect(transitions).toContain('retracted');
  });
});
