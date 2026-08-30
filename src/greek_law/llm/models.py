from pydantic import BaseModel, ConfigDict
from pyparsing import Literal

Role = Literal["system", "user", "assistant"]
FinishReason = Literal["stop", "length", "other"]


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    content: str
