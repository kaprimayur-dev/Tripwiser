from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class Station(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="Station code e.g. GWL, BPL")
    name: str = Field(..., description="Station name e.g. Gwalior Junction")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    city: Optional[str] = None
    state: Optional[str] = None
    zone: Optional[str] = None
