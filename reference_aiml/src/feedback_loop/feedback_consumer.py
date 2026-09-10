from typing import List, Dict, Optional, Callable
from collections import deque
from datetime import datetime
from src.schemas.feedback_contracts import OperatorFeedbackEvent
from .online_calibrator import OnlineCalibrator

class FeedbackConsumer:
    """
    Operator Feedback Ingestor & Dispatcher (Section 8.2).
    Consumes labelled operator feedback events from the shared internal queue (alert-feedback topic).
    Applies immediate short-term calibration and buffers examples for retraining.
    """

    def __init__(
        self,
        calibrator: OnlineCalibrator,
        retrain_trigger_count: int = 30,
        on_retrain_callback: Optional[Callable[[List[OperatorFeedbackEvent]], None]] = None,
    ):
        self.calibrator = calibrator
        self.retrain_trigger_count = retrain_trigger_count
        self.on_retrain_callback = on_retrain_callback
        self._buffer: deque[OperatorFeedbackEvent] = deque(maxlen=1000)

    def consume_event(self, event: OperatorFeedbackEvent) -> Dict[str, any]:
        """Processes an incoming feedback event."""
        self._buffer.append(event)

        # 1. Immediate Short-term mitigation: per-site rule/threshold nudge
        new_threshold = self.calibrator.record_feedback(
            site_id=event.site_id,
            feedback_type=event.feedback_type,
        )

        triggered_retrain = False
        # 2. Check if accumulated feedback volume crosses retraining threshold
        if len(self._buffer) >= self.retrain_trigger_count:
            if self.on_retrain_callback:
                self.on_retrain_callback(list(self._buffer))
                triggered_retrain = True

        return {
            "status": "processed",
            "site_id": event.site_id,
            "feedback_type": event.feedback_type,
            "updated_effective_threshold": new_threshold,
            "buffer_count": len(self._buffer),
            "triggered_retrain": triggered_retrain,
        }

    def get_buffered_events(self) -> List[OperatorFeedbackEvent]:
        return list(self._buffer)

    def clear_buffer(self) -> None:
        self._buffer.clear()
