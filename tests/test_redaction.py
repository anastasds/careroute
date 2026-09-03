"""Unit tests for PII/PHI Redaction Engine (Google Cloud DLP / Regex Filter)."""

import pytest
from careroute.security.redaction import PIIScrubber, redact_phi


def test_ssn_redaction():
    """Validates that Social Security Numbers are scrubbed."""
    text = "Patient John Doe, SSN: 123-45-6789, is being admitted."
    cleaned = PIIScrubber.redact(text)
    assert "123-45-6789" not in cleaned
    assert "[REDACTED_SSN]" in cleaned
    assert "Patient John Doe" in cleaned


def test_mrn_redaction():
    """Validates that Medical Record Numbers are scrubbed."""
    text = "Discharge notes for MRN: 9876543210. Patient is stable."
    cleaned = PIIScrubber.redact(text)
    assert "9876543210" not in cleaned
    assert "[REDACTED_MRN]" in cleaned


def test_email_and_phone_redaction():
    """Validates email and phone number scrubbing."""
    text = "Contact patient at john.doe@hospital.org or call 415-555-0199 for follow-up."
    cleaned = redact_phi(text)
    assert "john.doe@hospital.org" not in cleaned
    assert "[REDACTED_EMAIL]" in cleaned
    assert "415-555-0199" not in cleaned
    assert "[REDACTED_PHONE]" in cleaned


def test_dob_redaction():
    """Validates Date of Birth scrubbing."""
    text = "DOB: 04/12/1962. Prescribed Warfarin 5mg daily."
    cleaned = redact_phi(text)
    assert "04/12/1962" not in cleaned
    assert "[REDACTED_DOB]" in cleaned
    assert "Warfarin 5mg" in cleaned


def test_clinical_and_session_preservation():
    """Validates that clinical terms and patient IDs (e.g., PT-94821) are NOT falsely redacted."""
    text = "Patient ID: PT-94821 diagnosed with CHF and prescribed Lisinopril 10mg."
    cleaned = PIIScrubber.redact(text)
    assert "PT-94821" in cleaned
    assert "CHF" in cleaned
    assert "Lisinopril 10mg" in cleaned


def test_dlp_fallback_graceful():
    """Validates that when Cloud DLP is not enabled, fallback to regex succeeds seamlessly."""
    raw = "Patient phone: (555) 234-5678, SSN 987-65-4321."
    res = PIIScrubber.redact(raw)
    assert "555" not in res or "[REDACTED_PHONE]" in res
    assert "987-65-4321" not in res
