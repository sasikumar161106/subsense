"""Synthetic Multi-Sensor Telemetry Generator for SubSense.

Generates realistic time-series data for underground coal mine subsidence monitoring.
Simulates:
- Nominal operational baseline (ambient micro-seismic noise, thermal drift)
- Benign operational machinery transients (coal shearers, haulers - vibration only)
- Progressive subsidence precursors (roof sagging, micro-fracturing, gradual tilt/stretch)
- Sudden-onset collapse/burst signatures (rapid displacement, tilt spike, shockwaves)
- Telemetry health metadata (battery voltage, RSSI) to verify feature extractor exclusion
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any


def generate_mine_telemetry(
    total_samples: int = 12000,
    sampling_rate_hz: float = 1.0,
    random_seed: int = 42,
) -> pd.DataFrame:
    """Generate continuous multi-sensor time-series representing mine lifecycle.

    Timeline allocation:
    - 0% to 60%: Normal operation + heavy machinery passes (Training split)
    - 60% to 80%: Normal operation + early progressive subsidence (Validation split)
    - 80% to 100%: Normal + machinery + progressive + sudden collapse events (Held-out Test split)
    """
    np.random.seed(random_seed)
    time_index = np.arange(total_samples) / sampling_rate_hz

    # 1. Tilt (degrees): nominal flat with slow thermal drift
    tilt = 0.1 * np.sin(2 * np.pi * time_index / 3600.0) + np.random.normal(0, 0.03, total_samples)

    # 2. Vibration (g): baseline ambient micro-seismic noise
    vibration = np.random.normal(0, 0.04, total_samples)

    # 3. Displacement (mm): nominal stable borehole extensometer
    displacement = np.random.normal(0, 0.02, total_samples)

    # 4. Crack sensor (graded 0.0 to 1.0)
    crack = np.zeros(total_samples, dtype=np.float32)

    # 5. Metadata: Battery (V) and RSSI (dBm) - explicitly NOT model features
    battery = 4.15 - (time_index / total_samples) * 0.45 + np.random.normal(0, 0.01, total_samples)
    rssi = -72.0 + np.random.normal(0, 2.5, total_samples)

    # Labels
    is_anomaly = np.zeros(total_samples, dtype=np.int32)
    anomaly_type = np.array(["normal"] * total_samples, dtype=object)

    # Inject Benign Heavy Machinery Transients (Coal shearer / haulage train)
    # These cause sharp vibration spikes, but NO tilt drift, NO displacement, NO crack opening.
    # Essential to test that the model doesn't trigger false alarms on vibration alone!
    machinery_windows = [
        (int(total_samples * 0.15), min(total_samples, int(total_samples * 0.15) + 80)),
        (int(total_samples * 0.38), min(total_samples, int(total_samples * 0.38) + 120)),
        (int(total_samples * 0.65), min(total_samples, int(total_samples * 0.65) + 90)),
        (int(total_samples * 0.83), min(total_samples, int(total_samples * 0.83) + 100)),
    ]
    for start, end in machinery_windows:
        length = end - start
        if length <= 0: continue
        machinery_vib = 0.65 * np.sin(2 * np.pi * np.arange(length) * 8.0 / sampling_rate_hz)
        machinery_vib += np.random.normal(0, 0.20, length)
        vibration[start:end] += machinery_vib
        anomaly_type[start:end] = "machinery_transient"
        # is_anomaly remains 0 (Benign operational activity)

    # Inject Progressive Subsidence in Validation Partition (60% - 80%)
    # Progressive roof sagging & pillar yielding
    val_sub_start = int(total_samples * 0.70)
    val_sub_end = int(total_samples * 0.76)
    val_len = val_sub_end - val_sub_start
    t_norm = np.linspace(0, 1, val_len)

    tilt[val_sub_start:val_sub_end] += 1.8 * (t_norm ** 1.5) + np.random.normal(0, 0.08, val_len)
    vibration[val_sub_start:val_sub_end] += 0.25 * t_norm * np.random.normal(0, 1.0, val_len)
    displacement[val_sub_start:val_sub_end] += 6.5 * (t_norm ** 1.8) + np.random.normal(0, 0.05, val_len)
    crack[val_sub_start:val_sub_end] = np.clip(0.6 * t_norm + np.random.uniform(0, 0.2, val_len), 0.0, 1.0)
    is_anomaly[val_sub_start:val_sub_end] = 1
    anomaly_type[val_sub_start:val_sub_end] = "progressive_subsidence"

    # Inject Anomaly Events in Held-Out Test Partition (80% - 100%)
    # Event A: Progressive Pillar Failure / Strata Sagging (87% to 92%)
    test_prog_start = int(total_samples * 0.86)
    test_prog_end = int(total_samples * 0.91)
    test_prog_len = test_prog_end - test_prog_start
    tp_norm = np.linspace(0, 1, test_prog_len)

    tilt[test_prog_start:test_prog_end] += 2.4 * (tp_norm ** 1.4) + np.random.normal(0, 0.1, test_prog_len)
    vibration[test_prog_start:test_prog_end] += 0.35 * tp_norm * np.random.normal(0, 1.0, test_prog_len)
    displacement[test_prog_start:test_prog_end] += 9.0 * (tp_norm ** 1.6)
    crack[test_prog_start:test_prog_end] = np.clip(0.8 * tp_norm + np.random.uniform(0, 0.15, test_prog_len), 0.0, 1.0)
    is_anomaly[test_prog_start:test_prog_end] = 1
    anomaly_type[test_prog_start:test_prog_end] = "progressive_subsidence"

    # Event B: Sudden-Onset Rockburst / Major Roof Fall (94% to 97%)
    # Immediate catastrophic signature: violent shockwave, instantaneous tilt jump, displacement step, crack latch
    test_sudden_start = int(total_samples * 0.94)
    test_sudden_end = int(total_samples * 0.97)
    test_sudden_len = test_sudden_end - test_sudden_start

    tilt[test_sudden_start:test_sudden_end] += 5.5 + np.random.normal(0, 0.3, test_sudden_len)
    # Violent shockwave with high peak counts
    vibration[test_sudden_start:test_sudden_end] += 1.8 * np.sin(np.arange(test_sudden_len) * 0.9) + np.random.normal(0, 0.5, test_sudden_len)
    displacement[test_sudden_start:test_sudden_end] += 22.0 + np.random.normal(0, 0.2, test_sudden_len)
    crack[test_sudden_start:test_sudden_end] = 1.0
    is_anomaly[test_sudden_start:test_sudden_end] = 1
    anomaly_type[test_sudden_start:test_sudden_end] = "sudden_collapse"

    df = pd.DataFrame({
        "timestamp_sec": time_index,
        "tilt": tilt.astype(np.float32),
        "vibration": vibration.astype(np.float32),
        "displacement": displacement.astype(np.float32),
        "crack": crack.astype(np.float32),
        "battery_voltage": battery.astype(np.float32),
        "rssi": rssi.astype(np.float32),
        "is_anomaly": is_anomaly,
        "anomaly_type": anomaly_type,
    })

    return df
