"""Normalized data models for scraped plan data."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class NbnPlan(BaseModel):
    provider: str
    plan_name: str
    price_monthly: float = Field(gt=0)
    promo_price: float | None = Field(default=None, gt=0)
    promo_period_months: int | None = Field(default=None, gt=0)
    contract_length: str  # e.g. "No lock-in contract", "24 months"
    speed_tier: str  # e.g. "NBN 100/20", "NBN 25"
    typical_evening_speed_mbps: float | None = None
    source_url: str
    scraped_at: str

    @field_validator("scraped_at")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v


class MobilePlan(BaseModel):
    provider: str
    plan_name: str
    price_monthly: float = Field(gt=0)
    promo_price: float | None = Field(default=None, gt=0)
    promo_period_months: int | None = Field(default=None, gt=0)
    contract_length: str
    data_allowance_gb: float | None = None  # None means unlimited
    is_unlimited_data: bool = False
    network: str | None = None  # e.g. "Telstra", "Optus"
    source_url: str
    scraped_at: str

    @field_validator("scraped_at")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
