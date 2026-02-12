"""Notification-related schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from typing import list


class EmailCreate(BaseModel):
    subject: str
    recipients: list[EmailStr]
    body: str
    html: bool = Field(default=False)
