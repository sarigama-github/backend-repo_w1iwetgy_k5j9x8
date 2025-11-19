"""
Database Schemas for Nova Enterprises security platform

Each Pydantic model represents a collection in MongoDB. The collection name
is the lowercase of the class name (e.g., Upload -> "upload").
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class Upload(BaseModel):
    """Metadata for an uploaded file (we store security info, not the file)."""
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    verdict: str = Field("scanned", description="Scan result or status")
    notes: Optional[str] = None
    client_id: Optional[str] = None

class UserProgress(BaseModel):
    """Simple gamification progress for a client."""
    client_id: str
    points: int = 0
    uploads_count: int = 0
    badges: List[str] = []

class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    message: str
    session_id: Optional[str] = None

class Report(BaseModel):
    """Problem/feedback report submitted by a user."""
    client_id: Optional[str] = None
    subject: str
    message: str
    from_email: Optional[EmailStr] = None
    sent_to_owner: bool = False
    created_at: Optional[datetime] = None
