import enum
from typing import Dict, Any

class TaskComplexity(str, enum.Enum):
    FAST_EXTRACTION = "FAST_EXTRACTION"
    ROUTINE_PLANNING = "ROUTINE_PLANNING"
    COMPLEX_ORCHESTRATION = "COMPLEX_ORCHESTRATION"
    CRITICAL_SAFETY = "CRITICAL_SAFETY"
    CLINICAL_REASONING = "CLINICAL_REASONING"
    TEXT_SIMPLIFICATION = "TEXT_SIMPLIFICATION"

class StrategicModelRouter:
    def __init__(self):
        from careroute.config import settings
        self.fast_model = settings.flash_model_name
        self.smart_model = settings.pro_model_name

    def select_model_for_task(self, complexity: TaskComplexity) -> str:
        if complexity in (TaskComplexity.COMPLEX_ORCHESTRATION, TaskComplexity.CRITICAL_SAFETY, TaskComplexity.CLINICAL_REASONING):
            return self.smart_model
        return self.fast_model

router = StrategicModelRouter()
