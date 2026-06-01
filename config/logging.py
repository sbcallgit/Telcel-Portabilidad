import logging
import re
import sys

from pythonjsonlogger import jsonlogger


def mask_phone(phone: str) -> str:
    """Enmascara el centro de un número telefónico para logs. 52181****5678"""
    cleaned = re.sub(r"\D", "", phone)
    if len(cleaned) < 8:
        return "****"
    return cleaned[:4] + "*" * (len(cleaned) - 8) + cleaned[-4:]


def setup_logging(service_name: str = "bot_telcel") -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)

    # Add service field to all records
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        record = old_factory(*args, **kwargs)
        record.service = service_name
        return record

    logging.setLogRecordFactory(record_factory)
    logger.addHandler(handler)
