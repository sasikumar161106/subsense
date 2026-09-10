from typing import Dict, List, Optional
from collections import deque
from src.schemas.sensor_contracts import SensorReading

class SlidingWindowBuffer:
    """
    In-memory ring buffer per sensor node that manages streaming telemetry windowing.
    Automatically maintains fixed maximum history length (e.g. 60 samples).
    """

    def __init__(self, window_size: int = 60, min_samples_for_inference: int = 15):
        self.window_size = window_size
        self.min_samples = min_samples_for_inference
        self._buffers: Dict[str, deque[SensorReading]] = {}

    def append_reading(self, reading: SensorReading) -> None:
        if reading.node_id not in self._buffers:
            self._buffers[reading.node_id] = deque(maxlen=self.window_size)
        self._buffers[reading.node_id].append(reading)

    def append_batch(self, readings: List[SensorReading]) -> None:
        for r in readings:
            self.append_reading(r)

    def get_window(self, node_id: str) -> Optional[List[SensorReading]]:
        buf = self._buffers.get(node_id)
        if buf and len(buf) >= self.min_samples:
            return list(buf)
        return None

    def get_all_windows(self) -> Dict[str, List[SensorReading]]:
        ready_windows: Dict[str, List[SensorReading]] = {}
        for nid, buf in self._buffers.items():
            if len(buf) >= self.min_samples:
                ready_windows[nid] = list(buf)
        return ready_windows

    def clear(self, node_id: Optional[str] = None) -> None:
        if node_id:
            if node_id in self._buffers:
                self._buffers[node_id].clear()
        else:
            self._buffers.clear()
