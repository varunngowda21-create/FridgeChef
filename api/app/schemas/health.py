from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = "healthy"


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    database: str
    groq: str
