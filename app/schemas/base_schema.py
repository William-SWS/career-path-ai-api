from pydantic import BaseModel


class BaseMessageResponse(BaseModel):
    message: str
