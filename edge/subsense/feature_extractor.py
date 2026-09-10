"""SubSense Feature Extraction Pipeline (Reference Python & C/C++ Specification).

Deterministic sliding-window feature extractor for multi-sensor mine subsidence monitoring.
Computes exactly:
1. Tilt/inclination:
   - current_value: x_tilt[-1]
   - rate_of_change: (x_tilt[-1] - x_tilt[0]) / window_size
   - short_window_variance: (1/W) * sum((x - mean)^2)
2. Vibration:
   - rms_amplitude: sqrt((1/W) * sum(x^2))
   - peak_count: sum(abs(x) > vib_baseline_threshold)
3. Displacement/stretch:
   - delta_from_rolling_baseline: x_disp[-1] - rolling_baseline
4. Crack sensor:
   - activation_state: x_crack[-1]
   - recent_activation_count: sum(x_crack > crack_threshold)

Excludes: battery_voltage, rssi (reserved for health-check subsystem).

Preserves strict chronological order for train/val/test splitting with zero boundary leakage.
"""

import math
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Optional


FEATURE_NAMES = [
    "tilt_current",
    "tilt_rate_of_change",
    "tilt_variance",
    "vibration_rms",
    "vibration_peak_count",
    "displacement_delta_baseline",
    "crack_state",
    "crack_recent_activation_count",
]


class SubSenseFeatureExtractor:
    """Deterministic, fixed-size sliding-window feature extractor.

    Designed for 1:1 C/C++ porting onto microcontroller ring buffers (ESP32/Cortex-M).

    C/C++ Implementation Equivalent:
    --------------------------------
    ```c
    typedef struct {
        float tilt_ring[WINDOW_SIZE];
        float vib_ring[WINDOW_SIZE];
        float disp_ring[WINDOW_SIZE];
        float crack_ring[WINDOW_SIZE];
        uint16_t head;
        uint16_t count;
        float disp_rolling_baseline;
    } SubSenseWindowBuffer;

    void extract_features(const SubSenseWindowBuffer* buf, float* out_features) {
        // 1. Tilt
        float tilt_cur = buf->tilt_ring[(buf->head + WINDOW_SIZE - 1) % WINDOW_SIZE];
        float tilt_first = buf->tilt_ring[buf->head];
        float tilt_roc = (tilt_cur - tilt_first) / (float)WINDOW_SIZE;
        float tilt_sum = 0.0f;
        for (int i=0; i<WINDOW_SIZE; i++) tilt_sum += buf->tilt_ring[i];
        float tilt_mean = tilt_sum / (float)WINDOW_SIZE;
        float tilt_var = 0.0f;
        for (int i=0; i<WINDOW_SIZE; i++) {
            float d = buf->tilt_ring[i] - tilt_mean;
            tilt_var += d * d;
        }
        tilt_var /= (float)WINDOW_SIZE;

        // 2. Vibration
        float vib_sq_sum = 0.0f;
        float vib_peaks = 0.0f;
        for (int i=0; i<WINDOW_SIZE; i++) {
            float v = buf->vib_ring[i];
            vib_sq_sum += v * v;
            if (fabsf(v) > VIB_PEAK_THRESHOLD) vib_peaks += 1.0f;
        }
        float vib_rms = sqrtf(vib_sq_sum / (float)WINDOW_SIZE);

        // 3. Displacement
        float disp_cur = buf->disp_ring[(buf->head + WINDOW_SIZE - 1) % WINDOW_SIZE];
        float disp_delta = disp_cur - buf->disp_rolling_baseline;

        // 4. Crack
        float crack_cur = buf->crack_ring[(buf->head + WINDOW_SIZE - 1) % WINDOW_SIZE];
        float crack_count = 0.0f;
        for (int i=0; i<WINDOW_SIZE; i++) {
            if (buf->crack_ring[i] >= CRACK_THRESHOLD) crack_count += 1.0f;
        }

        out_features[0] = tilt_cur;
        out_features[1] = tilt_roc;
        out_features[2] = tilt_var;
        out_features[3] = vib_rms;
        out_features[4] = vib_peaks;
        out_features[5] = disp_delta;
        out_features[6] = crack_cur;
        out_features[7] = crack_count;
    }
    ```
    """

    def __init__(
        self,
        window_size: int = 32,
        step_size: int = 1,
        vib_peak_threshold: float = 0.15,
        crack_threshold: float = 0.50,
        baseline_alpha: float = 0.01,
    ):
        self.window_size = int(window_size)
        self.step_size = int(step_size)
        self.vib_peak_threshold = float(vib_peak_threshold)
        self.crack_threshold = float(crack_threshold)
        self.baseline_alpha = float(baseline_alpha)

    def extract_from_window(
        self,
        tilt_win: np.ndarray,
        vib_win: np.ndarray,
        disp_win: np.ndarray,
        crack_win: np.ndarray,
        rolling_baseline: float,
    ) -> np.ndarray:
        """Extract exact 8-dimensional feature vector from raw arrays of length window_size."""
        w = len(tilt_win)
        assert w == self.window_size, f"Window size mismatch: expected {self.window_size}, got {w}"

        # 1. Tilt features
        tilt_current = float(tilt_win[-1])
        tilt_rate_of_change = float((tilt_win[-1] - tilt_win[0]) / w)
        tilt_mean = float(np.mean(tilt_win))
        tilt_variance = float(np.mean((tilt_win - tilt_mean) ** 2))

        # 2. Vibration features
        vib_rms = float(np.sqrt(np.mean(vib_win ** 2)))
        vib_peak_count = float(np.sum(np.abs(vib_win) > self.vib_peak_threshold))

        # 3. Displacement features
        disp_current = float(disp_win[-1])
        disp_delta = float(disp_current - rolling_baseline)

        # 4. Crack sensor features
        crack_state = float(crack_win[-1])
        crack_recent_count = float(np.sum(crack_win >= self.crack_threshold))

        return np.array([
            tilt_current,
            tilt_rate_of_change,
            tilt_variance,
            vib_rms,
            vib_peak_count,
            disp_delta,
            crack_state,
            crack_recent_count,
        ], dtype=np.float32)

    def process_dataframe(
        self,
        df: pd.DataFrame,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract features over the dataframe using a rolling baseline.

        Returns:
            features: (N_windows, 8) float32
            labels: (N_windows,) int32 (1 if window contains an anomaly, else 0)
            window_indices: (N_windows,) int32 (center or end timestamp index)
        """
        # Strictly extract only the 4 telemetry sensors, ignoring battery and rssi
        tilt = df["tilt"].to_numpy(dtype=np.float32)
        vib = df["vibration"].to_numpy(dtype=np.float32)
        disp = df["displacement"].to_numpy(dtype=np.float32)
        crack = df["crack"].to_numpy(dtype=np.float32)
        is_anomaly = df["is_anomaly"].to_numpy(dtype=np.int32)

        n_samples = len(tilt)
        n_windows = (n_samples - self.window_size) // self.step_size + 1

        features = np.zeros((n_windows, len(FEATURE_NAMES)), dtype=np.float32)
        labels = np.zeros(n_windows, dtype=np.int32)
        window_ends = np.zeros(n_windows, dtype=np.int32)

        # Initialize rolling baseline using initial nominal window
        rolling_baseline = float(np.mean(disp[: self.window_size]))

        for i in range(n_windows):
            start = i * self.step_size
            end = start + self.window_size

            # Update rolling baseline slowly on nominal conditions (EMA)
            # Baseline adapts slowly: B_t = (1 - alpha) * B_{t-1} + alpha * disp[end-1]
            # In C firmware, this maintains a steady zero-drift reference
            cur_disp = disp[end - 1]
            rolling_baseline = (1.0 - self.baseline_alpha) * rolling_baseline + self.baseline_alpha * cur_disp

            feat_vec = self.extract_from_window(
                tilt[start:end],
                vib[start:end],
                disp[start:end],
                crack[start:end],
                rolling_baseline,
            )
            features[i] = feat_vec
            # Window is anomalous if >= 30% of its duration has an active anomaly flag
            labels[i] = 1 if np.mean(is_anomaly[start:end]) >= 0.3 else 0
            window_ends[i] = end - 1

        return features, labels, window_ends


def chronological_split_zero_leakage(
    features: np.ndarray,
    labels: np.ndarray,
    window_ends: np.ndarray,
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
    window_size: int = 32,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Splits time series chronologically with a buffer gap to ensure ZERO leakage across splits.

    Guarantees no window in validation or test shares raw telemetry samples with train windows.
    """
    total_len = len(window_ends)
    train_end_idx = int(total_len * train_ratio)
    val_end_idx = int(total_len * (train_ratio + val_ratio))

    # To guarantee absolute zero cross-boundary leakage, we enforce a buffer gap
    # equal to window_size samples so no window boundary overlaps across split partitions.
    buffer_windows = max(1, window_size // 1)

    train_slice = slice(0, train_end_idx)
    val_slice = slice(train_end_idx + buffer_windows, val_end_idx)
    test_slice = slice(val_end_idx + buffer_windows, total_len)

    splits = {
        "train": (features[train_slice], labels[train_slice]),
        "val": (features[val_slice], labels[val_slice]),
        "test": (features[test_slice], labels[test_slice]),
    }

    return splits
