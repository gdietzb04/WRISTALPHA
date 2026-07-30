"""Versioned, source-aware application configuration."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourcedMoney(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    source: str | None = None
    source_needed: str | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> SourcedMoney:
        if self.value is not None and (self.currency is None or self.source is None):
            raise ValueError("a configured monetary value requires currency and source")
        if self.value is None and self.source_needed is None:
            raise ValueError("an unknown monetary value requires source_needed")
        return self


class SourcedCost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: Decimal | None = Field(default=None, ge=0)
    unit: Literal["fraction", "currency"]
    source: str | None = None
    source_needed: str | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> SourcedCost:
        if self.value is not None and self.source is None:
            raise ValueError("a configured cost requires a source")
        if self.value is None and self.source_needed is None:
            raise ValueError("an unknown cost requires source_needed")
        if self.unit == "fraction" and self.value is not None and self.value > 1:
            raise ValueError("fractional costs must be between zero and one")
        return self


class UniverseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    brands: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    maximum_listing_price: SourcedMoney


class HoldingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: str
    reference: str
    year: int | None = Field(default=None, ge=1800, le=2200)
    purchase_price: Decimal = Field(gt=0)
    purchase_currency: str = Field(min_length=3, max_length=3)
    purchase_date: str
    condition: str | None = None
    box: bool | None = None
    papers: bool | None = None


class PortfolioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    next_purchase_budget: SourcedMoney
    holding_horizon: Literal["short", "mid", "long"] | None = None
    holdings: tuple[HoldingInput, ...] = ()


class AlertConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    channel: Literal["email", "telegram", "webhook"] | None = None
    destination_env_var: str | None = None

    @model_validator(mode="after")
    def require_destination_for_channel(self) -> AlertConfig:
        if (self.channel is None) != (self.destination_env_var is None):
            raise ValueError("alert channel and destination_env_var must be set together")
        return self


class CostConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    marketplace_commission: SourcedCost
    payment_or_escrow: SourcedCost
    shipping: SourcedCost
    insurance: SourcedCost
    import_duty_or_vat: SourcedCost
    authentication: SourcedCost
    servicing: SourcedCost
    dealer_bid_ask_spread: SourcedCost


class HtmlSelectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    item: str
    external_id_attribute: str
    title: str
    price: str
    currency: str
    url: str
    brand: str | None = None
    reference: str | None = None


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    adapter: Literal["licensed_api", "html", "csv", "auction"]
    enabled: bool
    source_name: str | None = None
    path: str | None = None
    search_url: str | None = None
    user_agent: str | None = None
    selectors: HtmlSelectorConfig | None = None
    source: str | None = None
    source_needed: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> SourceConfig:
        if self.enabled and self.adapter in {"csv", "auction"} and self.path is None:
            raise ValueError("enabled CSV or auction source requires a path")
        if (
            self.enabled
            and self.adapter == "html"
            and (self.search_url is None or self.user_agent is None or self.selectors is None)
        ):
            raise ValueError("enabled HTML source requires URL, user agent, and verified selectors")
        if self.source is None and self.source_needed is None:
            raise ValueError("source provenance or source_needed is required")
        return self


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    config_version: Literal[1]
    universe: UniverseConfig
    portfolio: PortfolioConfig
    alerts: AlertConfig
    costs: CostConfig
    sources: dict[str, SourceConfig]


class RuntimeSettings(BaseSettings):
    """Environment-only settings; secrets are never stored in source-controlled YAML."""

    model_config = SettingsConfigDict(
        env_prefix="WRISTALPHA_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )
    database_url: str = "postgresql+psycopg://wristalpha@localhost:5432/wristalpha"
    config_path: Path = Path("config/default.yaml")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    schedule_interval_hours: int = Field(default=6, ge=1, le=168)


def load_app_config(path: Path) -> AppConfig:
    with path.open(encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file)
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    return AppConfig.model_validate(raw)
