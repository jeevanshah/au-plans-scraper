"""Normalized data models for scraped plan data."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class NbnPlan(BaseModel):
    provider: str
    plan_name: str
    price_monthly: float = Field(gt=0)
    promo_price: float | None = Field(default=None, gt=0)
    promo_period_months: int | None = Field(default=None, gt=0)
    promo_end_date: str | None = None  # ISO date, only set when the page shows a fixed calendar end-date
    contract_length: str  # e.g. "No lock-in contract", "24 months"
    speed_tier: str  # e.g. "NBN 100/20", "NBN 25"
    typical_evening_speed_mbps: float | None = None
    tech_type: str | None = None  # e.g. "Fibre", "Fibre and FTTN" -- only set when the page states it
    deal_channel: str | None = None  # e.g. "partner_exclusive", "bank_perk", "promo_code", "direct"
    deal_channel_label: str | None = None  # e.g. "WhistleOut Exclusive LP", "CommBank 30% Off", "Promo Code: SLC-6M"
    direct_public_promo_price: float | None = None  # Baseline direct price when a partner LP is cheaper
    how_to_get: str | None = None  # 1-sentence actionable instruction
    source_url: str
    scraped_at: str

    @field_validator("scraped_at")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v

    @field_validator("promo_end_date")
    @classmethod
    def _validate_end_date(cls, v: str | None) -> str | None:
        if v is not None:
            datetime.fromisoformat(v)
        return v


class MobilePlan(BaseModel):
    provider: str
    plan_name: str
    price_monthly: float = Field(gt=0)
    promo_price: float | None = Field(default=None, gt=0)
    promo_period_months: int | None = Field(default=None, gt=0)
    promo_end_date: str | None = None  # ISO date, only set when the page shows a fixed calendar end-date
    contract_length: str
    # Real billing/renewal cadence in days. Defaults to 30 (standard monthly
    # billing) -- explicitly overridden by providers selling prepaid SIMs on
    # a different cadence (amaysim's 7/28/184/365-day plans, Boost's
    # 3/7/14/28/186/365-day plans, ALDImobile's 365-day "Long Life" plan,
    # Kogan's 365-day plans). Without this, `price_monthly` for those plans
    # is a total-for-the-whole-cycle figure, not an actual monthly price --
    # treating it as monthly (as this project did before this field existed)
    # produces a wildly wrong annual/monthly cost for ~1 in 4 mobile plans
    # (e.g. a $270/365-day plan showing as $270/MONTH, a 12x overstatement).
    # Consumers (site JS, app's offer.dart) must normalize price_monthly and
    # promo_price to a true monthly-equivalent using this field before doing
    # any monthly/annual cost math -- see NOTES.md for the incident that
    # prompted this.
    billing_cycle_days: int = Field(default=30, gt=0)
    data_allowance_gb: float | None = None  # None means unlimited
    is_unlimited_data: bool = False
    network: str | None = None  # e.g. "Telstra", "Optus"
    network_tech: str | None = None  # e.g. "4G", "5G" -- only set when the page states it
    deal_channel: str | None = None
    deal_channel_label: str | None = None
    direct_public_promo_price: float | None = None
    how_to_get: str | None = None
    source_url: str
    scraped_at: str

    @field_validator("scraped_at")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v

    @field_validator("promo_end_date")
    @classmethod
    def _validate_end_date(cls, v: str | None) -> str | None:
        if v is not None:
            datetime.fromisoformat(v)
        return v


class SatellitePlan(BaseModel):
    provider: str
    plan_name: str
    price_monthly: float = Field(gt=0)
    promo_price: float | None = Field(default=None, gt=0)
    promo_period_months: int | None = Field(default=None, gt=0)
    # One-time capital cost (e.g. a Starlink dish/kit or a Sky Muster install fee),
    # distinct from the recurring price_monthly/promo_price above. None when the
    # provider doesn't charge (or doesn't disclose) an upfront hardware cost.
    upfront_hardware_cost: float | None = None
    data_allowance_gb: float | None = None  # None means unlimited
    is_unlimited_data: bool = False
    network: str  # e.g. "Starlink", "Sky Muster"
    contract_length: str
    deal_channel: str | None = None
    deal_channel_label: str | None = None
    direct_public_promo_price: float | None = None
    how_to_get: str | None = None
    source_url: str
    scraped_at: str

    @field_validator("scraped_at")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v


class OpticommPlan(BaseModel):
    provider: str
    plan_name: str
    price_monthly: float = Field(gt=0)
    promo_price: float | None = Field(default=None, gt=0)
    promo_period_months: int | None = Field(default=None, gt=0)
    promo_end_date: str | None = None  # ISO date, only set when the page shows a fixed calendar end-date
    contract_length: str  # e.g. "No lock-in contract"
    speed_tier: str  # e.g. "OptiComm 100/20", "OptiComm 50/20"
    typical_evening_speed_mbps: float | None = None
    tech_type: str | None = "Fibre"  # OptiComm is private fibre
    deal_channel: str | None = None
    deal_channel_label: str | None = None
    direct_public_promo_price: float | None = None
    how_to_get: str | None = None
    source_url: str
    scraped_at: str

    @field_validator("scraped_at")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v

    @field_validator("promo_end_date")
    @classmethod
    def _validate_end_date(cls, v: str | None) -> str | None:
        if v is not None:
            datetime.fromisoformat(v)
        return v


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
