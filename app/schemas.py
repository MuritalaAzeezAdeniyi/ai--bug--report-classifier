from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

Category = Literal[
    "Authentication",
    "Authorization",
    "API",
    "UI",
    "Database",
    "Performance",
    "Security",
    "Validation",
    "Other",
]

Severity = Literal["Critical", "High", "Medium", "Low"]
Priority = Literal["P0", "P1", "P2", "P3"]


class BugReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    severity: Severity
    priority: Priority
    environment: str | None = None
    issue: str = Field(..., min_length=1)
    reproduction_available: StrictBool
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_human_review: StrictBool
