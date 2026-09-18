"""Model-level AI evaluation requests."""
from typing import Literal

from pydantic import BaseModel


class ModelEvaluationRequest(BaseModel):
    """Regenerate the role-specific evaluation instead of using the cache."""

    regenerate: bool = False
    # Management may explicitly prepare the public user evaluation. Ordinary
    # users can only use the current audience (their own role).
    audience: Literal["current", "management", "user"] = "current"
