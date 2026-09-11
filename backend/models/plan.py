"""
Modelos de Planos e Assinaturas
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class PlanType(str, Enum):
    FREE = "free"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PlanFeatures(BaseModel):
    max_instances: int = 1
    max_messages_per_day: int = 100
    has_chatbot: bool = True
    has_radar_leads: bool = False
    has_reports: bool = True
    has_campaigns: bool = False
    has_auto_messages: bool = False
    has_pix: bool = False


# Planos padrão do sistema
DEFAULT_PLANS = {
    PlanType.FREE: {
        "id": PlanType.FREE,
        "name": "Colaborador",
        "price": 0.0,
        "interval": "month",
        "features": PlanFeatures(
            max_instances=0,
            max_messages_per_day=0,
            has_chatbot=False,
            has_radar_leads=False,
            has_reports=False,
            has_campaigns=False,
            has_auto_messages=False,
            has_pix=False,
        ),
        "description": "Plano colaborador - acesso a Planos, Downloads e Configuracoes",
    },
    PlanType.MONTHLY: {
        "id": PlanType.MONTHLY,
        "name": "Mensal",
        "price": 14.99,
        "interval": "month",
        "features": PlanFeatures(
            max_instances=0,
            max_messages_per_day=100,
            has_chatbot=True,
            has_radar_leads=False,
            has_reports=True,
            has_campaigns=True,
            has_auto_messages=False,
            has_pix=False,
        ),
        "description": "ChatBot + Commands + Gatilhos + Relatorios + Comunicados",
    },
    PlanType.QUARTERLY: {
        "id": PlanType.QUARTERLY,
        "name": "Trimestral",
        "price": 29.99,
        "interval": "quarter",
        "features": PlanFeatures(
            max_instances=0,
            max_messages_per_day=300,
            has_chatbot=False,
            has_radar_leads=False,
            has_reports=True,
            has_campaigns=True,
            has_auto_messages=False,
            has_pix=True,
        ),
        "description": "Jarvis + Charon + Commands + Gatilhos + PIX",
        "discount_percent": 33,
    },
    PlanType.ANNUAL: {
        "id": PlanType.ANNUAL,
        "name": "Anual",
        "price": 79.99,
        "interval": "year",
        "features": PlanFeatures(
            max_instances=10,
            max_messages_per_day=1000,
            has_chatbot=True,
            has_radar_leads=True,
            has_reports=True,
            has_campaigns=True,
            has_auto_messages=True,
            has_pix=True,
        ),
        "description": "Acesso completo - Tudo liberado",
        "discount_percent": 71,
        "includes_jarvis_lifetime": True,
    },
}


# Hierarquia de planos (para verificação de acesso)
PLAN_HIERARCHY = {
    PlanType.FREE: 0,
    PlanType.MONTHLY: 1,
    PlanType.QUARTERLY: 2,
    PlanType.ANNUAL: 3,
}


class Plan(BaseModel):
    id: PlanType
    name: str
    price: float
    interval: str  # month, quarter, year
    features: PlanFeatures = PlanFeatures()
    description: str = ""
    discount_percent: Optional[int] = None
    includes_jarvis_lifetime: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)


class PlanCreate(BaseModel):
    name: str
    price: float
    interval: str
    features: PlanFeatures = PlanFeatures()
    description: str = ""


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    features: Optional[PlanFeatures] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
