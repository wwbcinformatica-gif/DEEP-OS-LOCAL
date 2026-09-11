"""
Modelo de Pagamentos
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class PaymentMethod(str, Enum):
    PIX = "pix"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BOLETO = "boleto"
    FREE = "free"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class Payment(BaseModel):
    id: int = Field(default=0)
    tenant_id: str
    amount: float
    currency: str = "BRL"
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.PENDING
    plan_id: Optional[str] = None
    subscription_months: int = 1
    transaction_id: Optional[str] = None
    gateway_response: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class PaymentCreate(BaseModel):
    tenant_id: str
    amount: float
    method: PaymentMethod
    plan_id: str
    subscription_months: int = 1


class PaymentResponse(BaseModel):
    id: int
    tenant_id: str
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    plan_id: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None


class PIXPayment(BaseModel):
    """Resposta de pagamento PIX."""
    qr_code: str  # Base64 da imagem do QR Code
    qr_code_url: str  # URL do QR Code
    pix_key: str  # Chave PIX
    expires_at: datetime
    payment_id: int
