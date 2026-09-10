export interface HardwareActuationLog {
  zone_id: string;
  timestamp: Date;
  action: 'TRIGGER_SIRENS_AND_STROBES';
  status: 'EXECUTED';
}

export const actuationHistory: HardwareActuationLog[] = [];

/**
 * Hardware actuator stub for Phase 1.
 * Fires local sirens and strobes on-ground when a Critical-tier Edge event occurs.
 */
export const hardware_actuator = {
  trigger_local_sirens_and_strobes: (zone_id: string): HardwareActuationLog => {
    const log: HardwareActuationLog = {
      zone_id,
      timestamp: new Date(),
      action: 'TRIGGER_SIRENS_AND_STROBES',
      status: 'EXECUTED'
    };
    actuationHistory.push(log);
    console.log(
      `[HARDWARE ACTUATOR] >>> ON-GROUND SIRENS & STROBES TRIGGERED IMMEDIATELY for zone ${zone_id} <<<`
    );
    return log;
  }
};
