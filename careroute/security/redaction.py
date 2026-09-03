"""PII / PHI Redaction Engine for HIPAA-Aware Clinical Workflows.

Provides dual-mode PII/PHI scrubbing:
1. Google Cloud Sensitive Data Protection (DLP) API when configured/available.
2. High-performance, comprehensive deterministic regex filtering (SSN, MRN, phone, email, dates of birth, zip codes).
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from careroute.observability.logger import logger


class PIIScrubber:
    """HIPAA-aware PII and PHI redaction engine."""

    # Pre-compiled high-performance deterministic regex patterns
    PATTERNS: List[Tuple[str, re.Pattern, str]] = [
        # Social Security Numbers (SSN): 123-45-6789 or 123 45 6789 or explicit SSN: \d{9}
        (
            "SSN",
            re.compile(r"(?:\bSSN[#:\s]+)?\b(?!(?:000|666))\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b", re.I),
            "[REDACTED_SSN]",
        ),
        # Medical Record Numbers (MRN) and Hospital Account Numbers (exclude CareRoute internal PT- IDs)
        (
            "MRN",
            re.compile(r"\b(?:MRN|MEDREC|REC|ACCT)[#:\s]+([A-Z0-9-]{4,15})\b", re.I),
            "MRN: [REDACTED_MRN]",
        ),
        # Email Addresses
        (
            "EMAIL",
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b"),
            "[REDACTED_EMAIL]",
        ),
        # Phone numbers (US/International, various formats)
        (
            "PHONE",
            re.compile(
                r"(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b"
            ),
            "[REDACTED_PHONE]",
        ),
        # Dates of Birth (DOB) e.g., DOB: 01/15/1955, Born: 1980-05-12
        (
            "DOB",
            re.compile(
                r"\b(?:DOB|Date of Birth|Born)[#:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
                re.I,
            ),
            "DOB: [REDACTED_DOB]",
        ),
        # 5-digit or 9-digit US ZIP Codes with explicit label
        (
            "ZIP",
            re.compile(r"\b(?:ZIP|Postal(?:\s*Code)?)[#:\s]+(\d{5}(?:-\d{4})?)\b", re.I),
            "ZIP: [REDACTED_ZIP]",
        ),
    ]

    _dlp_client = None
    _dlp_checked = False

    @classmethod
    def _get_dlp_client(cls):
        """Initializes the Cloud DLP client if installed and enabled."""
        if not cls._dlp_checked:
            cls._dlp_checked = True
            dlp_enabled = os.getenv("CAREROUTE_ENABLE_DLP", "false").lower() in ("true", "1", "yes")
            if dlp_enabled:
                try:
                    from google.cloud import dlp_v2
                    cls._dlp_client = dlp_v2.DlpServiceClient()
                    logger.info("Google Cloud DLP client initialized for PHI redaction.")
                except Exception as exc:
                    logger.warning(
                        f"Google Cloud DLP unavailable or not configured ({exc}). Falling back to local regex scrubber."
                    )
        return cls._dlp_client

    @classmethod
    def redact_with_dlp(cls, text: str, project_id: Optional[str] = None) -> Optional[str]:
        """Invokes Google Cloud Sensitive Data Protection (DLP) API to redact PHI/PII."""
        client = cls._get_dlp_client()
        if not client:
            return None

        project = project_id or os.getenv("GCP_PROJECT_ID")
        if not project:
            return None

        try:
            parent = f"projects/{project}/locations/global"
            # Standard HIPAA / US info types
            info_types = [
                {"name": "US_SOCIAL_SECURITY_NUMBER"},
                {"name": "EMAIL_ADDRESS"},
                {"name": "PHONE_NUMBER"},
                {"name": "DATE_OF_BIRTH"},
                {"name": "US_HEALTHCARE_NPI"},
                {"name": "MEDICAL_RECORD_NUMBER"},
                {"name": "STREET_ADDRESS"},
            ]
            inspect_config = {
                "info_types": info_types,
                "min_likelihood": "LIKELY",
            }
            deidentify_config = {
                "info_type_transformations": {
                    "transformations": [
                        {
                            "primitive_transformation": {
                                "replace_with_info_type_config": {}
                            }
                        }
                    ]
                }
            }
            item = {"value": text}

            response = client.deidentify_content(
                request={
                    "parent": parent,
                    "deidentify_config": deidentify_config,
                    "inspect_config": inspect_config,
                    "item": item,
                }
            )
            return response.item.value
        except Exception as exc:
            logger.warning(f"Cloud DLP de-identification failed: {exc}. Falling back to regex.")
            return None

    @classmethod
    def redact_with_regex(cls, text: str) -> str:
        """Applies comprehensive regex replacements to scrub direct identifiers."""
        redacted = text
        for label, pattern, replacement in cls.PATTERNS:
            if pattern.search(redacted):
                redacted = pattern.sub(replacement, redacted)
        return redacted

    @classmethod
    def redact(cls, text: str, project_id: Optional[str] = None) -> str:
        """Scrubs PII/PHI using Cloud DLP if enabled/available, with regex fallback.
        
        Preserves non-identifying clinical terms and valid patient session tokens
        (e.g., PT-94821) while masking SSNs, MRNs, phone numbers, emails, and DOBs.
        """
        if not text or not isinstance(text, str):
            return text

        # 1. Try Google Cloud DLP if configured
        dlp_result = cls.redact_with_dlp(text, project_id=project_id)
        if dlp_result is not None:
            return dlp_result

        # 2. Local deterministic regex filtering
        return cls.redact_with_regex(text)


# Convenience module-level function
def redact_phi(text: str, project_id: Optional[str] = None) -> str:
    """Convenience helper to redact PHI/PII from any clinical string."""
    return PIIScrubber.redact(text, project_id=project_id)
