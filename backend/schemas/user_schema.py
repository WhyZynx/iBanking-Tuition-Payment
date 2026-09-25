from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    user_id: int = Field(serialization_alias="userId")
    username: str
    full_name: str = Field(serialization_alias="fullName")
    phone: str
    email: EmailStr