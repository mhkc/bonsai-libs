"Shared data models."

from typing import TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Model(BaseModel):
    """Shared base model."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
