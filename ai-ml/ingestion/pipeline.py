"""
Ingestion Pipeline orchestrating validation, QoS telemetry tracking,
persistence to time-series storage, and stream publishing to Apache Kafka.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from .schema import RawSensorRecord
from .validator import PayloadValidator, ValidationResult, RejectionRecord
from .qos_tracker import QoSTracker, NodeQoSMetrics

logger = logging.getLogger("subsense.ingestion.pipeline")


class IngestionPipeline:
    """
    SubSense Ingestion Pipeline Service.
    Acts as the single point of entry for all telemetry from MQTT broker (Eclipse EMQX).
    Guarantees zero silent drops: every payload is either validated & persisted or rejected & logged.
    """

    def __init__(
        self,
        bounds_config_path: Optional[str] = None,
        audit_log_path: Optional[str] = None,
        kafka_publisher: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        timeseries_sink: Optional[Callable[[RawSensorRecord], None]] = None,
    ):
        self.validator = PayloadValidator(bounds_config_path, audit_log_path)
        self.qos_tracker = QoSTracker()
        self.kafka_publisher = kafka_publisher
        self.timeseries_sink = timeseries_sink
        self.persisted_records: List[RawSensorRecord] = []

    def process_raw_message(
        self,
        raw_payload: Any,
        current_time: Optional[datetime] = None,
    ) -> ValidationResult:
        """
        Ingests a single raw message from MQTT topic (subsense/mine/telemetry).
        """
        result = self.validator.validate(raw_payload, current_time=current_time)

        if not result.is_valid or result.record is None:
            # Rejection already recorded by validator
            return result

        record = result.record

        # 1. Update QoS metrics (PDR, timing, Q_mesh)
        self.qos_tracker.record_packet(record)

        # 2. Persist to Time-Series Store (TimescaleDB / local buffer)
        self.persisted_records.append(record)
        if self.timeseries_sink:
            try:
                self.timeseries_sink(record)
            except Exception as e:
                logger.error(f"Failed writing to time-series store for {record.node_id}: {e}")

        # 3. Publish to validated Kafka topic
        if self.kafka_publisher:
            try:
                topic = f"subsense.telemetry.{record.node_id}"
                self.kafka_publisher(topic, record.model_dump(mode="json"))
            except Exception as e:
                logger.error(f"Failed publishing to Kafka for {record.node_id}: {e}")

        return result

    def get_rejected_count(self) -> int:
        return len(self.validator.rejections)

    def get_persisted_count(self) -> int:
        return len(self.persisted_records)

    def get_node_qos(self, node_id: str) -> Optional[NodeQoSMetrics]:
        return self.qos_tracker.get_metrics(node_id)
