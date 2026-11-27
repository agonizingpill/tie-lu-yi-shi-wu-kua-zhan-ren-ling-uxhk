"""Compatibility namespace for verification-number operations."""

from railway.services.verification_desk import (  # noqa: F401
    RejectedVerification,
    verify_claim,
    verify_number,
)
from railway.services.allocation import (  # noqa: F401
    allocate_verification_numbers,
    call_payload,
)
