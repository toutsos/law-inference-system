from typing import Literal

from pydantic import BaseModel, ConfigDict

Role = Literal["system", "user", "assistant"]
FinishReason = Literal["stop", "length", "other"]


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    content: str


class ChatResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    finish_reason: FinishReason
    tokens_in: int
    token_out: int
    duration_seconds: float
