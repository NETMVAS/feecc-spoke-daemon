from pydantic import BaseModel


class BaseEvent(BaseModel):
    name: str
    string: str
