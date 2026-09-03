"""Patient Personalization Memory and Clinician Notes Store.

Manages individualized patient profiles, tracking behavioral adherence traits
(e.g., forgetfulness, erratic work shifts), lifestyle routines, clinician private notes,
and caregiver escalation contacts to ensure highly personalized care delivery.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from careroute.core.models import PatientPersonalizationProfile
from careroute.observability.logger import logger


class PatientPersonalizationMemory:
    """In-memory and persistent manager for per-patient behavioral profiles."""

    def __init__(self) -> None:
        self._profiles: Dict[str, PatientPersonalizationProfile] = {}

    def get_profile(self, patient_id: str) -> PatientPersonalizationProfile:
        """Retrieves an existing patient personalization profile or returns an empty default."""
        if patient_id not in self._profiles:
            self._profiles[patient_id] = PatientPersonalizationProfile(
                patient_id=patient_id,
                behavioral_traits=[],
                daily_routines={},
                reading_level_preference="Standard",
                preferred_reminder_channel="None",
                clinician_notes=[],
                caregiver_name=None,
                caregiver_phone=None
            )
        return self._profiles[patient_id]

    def save_profile(self, profile: PatientPersonalizationProfile) -> None:
        """Saves or updates a patient profile."""
        self._profiles[profile.patient_id] = profile
        logger.info(
            f"Saved personalization profile for patient {profile.patient_id}",
            extra={"patient_id": profile.patient_id, "traits_count": len(profile.behavioral_traits)}
        )

    def add_behavioral_trait(self, patient_id: str, trait: str) -> None:
        """Records a newly observed behavioral pattern for a patient."""
        profile = self.get_profile(patient_id)
        if trait not in profile.behavioral_traits:
            profile.behavioral_traits.append(trait)
            self.save_profile(profile)

    def add_clinician_note(self, patient_id: str, note: str) -> None:
        """Appends a confidential clinician directive to the patient memory."""
        profile = self.get_profile(patient_id)
        profile.clinician_notes.append(note)
        self.save_profile(profile)

    def format_context_for_agent(self, patient_id: str) -> str:
        """Formats the personalization profile into a concise context block for prompt injection."""
        profile = self.get_profile(patient_id)
        lines = [
            f"--- PATIENT PERSONALIZATION PROFILE [{profile.patient_id}] ---",
            f"Reading Level: {profile.reading_level_preference}",
            f"Reminder Preference: {profile.preferred_reminder_channel}",
        ]
        if profile.behavioral_traits:
            lines.append("Behavioral Adherence Traits:")
            for t in profile.behavioral_traits:
                lines.append(f"  • {t}")
        if profile.daily_routines:
            lines.append(f"Daily Routine Anchors: {profile.daily_routines}")
        if profile.clinician_notes:
            lines.append("Clinician Directives & Notes:")
            for n in profile.clinician_notes:
                lines.append(f"  • {n}")
        if profile.caregiver_name:
            lines.append(f"Caregiver Contact: {profile.caregiver_name} ({profile.caregiver_phone})")
        lines.append("-----------------------------------------------------")
        return "\n".join(lines)


# Singleton instance
personalization_memory = PatientPersonalizationMemory()

