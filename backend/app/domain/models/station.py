from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional

class Station(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(..., min_length=1, description="Station code e.g. GWL, BPL")
    name: str = Field(..., min_length=1, description="Station name e.g. Gwalior Junction")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    city: Optional[str] = None
    state: Optional[str] = None
    zone: Optional[str] = None

    @field_validator("code", "name")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped
