"""
Modelo de Uso/Métricas
"""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


class UsageMetric(BaseModel):
    id: int = Field(default=0)
    tenant_id: str
    date: date
    messages_used: int = 0
    instances_active: int = 0
    tokens_used: int = 0
    api_calls: int = 0
    storage_used_mb: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)


class UsageSummary(BaseModel):
    tenant_id: str
    plan: str
    messages_used_today: int = 0
    messages_limit: int = 100
    messages_remaining: int = 0
    instances_active: int = 0
    instances_limit: int = 1
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class UsageHistory(BaseModel):
    tenant_id: str
    daily_usage: List[UsageMetric] = []
    total_messages: int = 0
    total_tokens: int = 0
    avg_messages_per_day: float = 0.0


class UsageUpdate(BaseModel):
    """Para atualizar uso via API."""
    tenant_id: str
    messages_increment: int = 0
    tokens_increment: int = 0
    instances_active: int = 0


class UsageCheck(BaseModel):
    """Resultado da verificação de uso."""
    allowed: bool
    current_usage: int
    limit: int
    remaining: int
    message: str = ""
