from pydantic import BaseModel


class GenericResponse(BaseModel):
    status: bool
    comment: str


class HidEvent(BaseModel):
    name: str
    string: str


class HidBufferEntry(GenericResponse):
    buffer: str
    added_on: float
