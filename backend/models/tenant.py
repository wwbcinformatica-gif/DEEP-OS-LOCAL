"""
Modelo de Tenant (Assinante)
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
import hashlib
import secrets


class Tenant(BaseModel):
    id: str = Field(default_factory=lambda: secrets.token_hex(16))
    name: str
    email: str
    password_hash: str = ""
    plan: str = "free"  # PlanType value
    status: str = "active"  # SubscriptionStatus value
    license_key: str = Field(default_factory=lambda: generate_license_key())
    company: Optional[str] = None
    phone: Optional[str] = None
    pix_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class TenantCreate(BaseModel):
    name: str
    email: str
    password: str
    company: Optional[str] = None
    phone: Optional[str] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    expires_at: Optional[datetime] = None


class TenantLogin(BaseModel):
    email: str
    password: str


class TenantResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    status: str
    license_key: Optional[str] = ""
    company: Optional[str] = None
    pix_key: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant: TenantResponse


def hash_password(password: str) -> str:
    """Gera hash da senha usando SHA-256 com salt."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a senha corresponde ao hash."""
    try:
        salt, hash_value = password_hash.split(":", 1)
        computed_hash = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return computed_hash == hash_value
    except Exception:
        return False


def generate_license_key() -> str:
    """Gera uma chave de licença única."""
    return f"DA-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
