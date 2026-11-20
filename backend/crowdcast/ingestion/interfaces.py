"""Public interface of the ingestion module (AD-02). Other modules import only from here."""

from crowdcast.ingestion.validation import (
    MAX_BATCH,
    BatchRejectedError,
    EventFacts,
    ObservationBatch,
    ObservationIn,
    RejectedRow,
    check_batch,
    check_rows,
)

__all__ = [
    "MAX_BATCH",
    "BatchRejectedError",
    "EventFacts",
    "ObservationBatch",
    "ObservationIn",
    "RejectedRow",
    "check_batch",
    "check_rows",
]
