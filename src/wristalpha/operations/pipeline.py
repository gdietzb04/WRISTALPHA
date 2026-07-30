"""Fail-closed scheduled pipeline entry point."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from wristalpha.config import AppConfig, load_app_config

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineOutcome:
    status: str
    started_at: datetime
    completed_at: datetime
    blocking_reasons: tuple[str, ...]


def _blocking_reasons(config: AppConfig) -> list[str]:
    reasons: list[str] = []
    if not config.universe.brands and not config.universe.references:
        reasons.append("investable universe is empty")
    enabled_sources = [source for source in config.sources.values() if source.enabled]
    if not enabled_sources:
        reasons.append("no acquisition source is enabled")
    if config.portfolio.next_purchase_budget.value is None:
        reasons.append("purchase budget is unknown")
    unknown_costs = [
        name
        for name, value in config.costs.model_dump().items()
        if isinstance(value, dict) and value.get("value") is None
    ]
    if unknown_costs:
        reasons.append("net cost assumptions are incomplete: " + ", ".join(sorted(unknown_costs)))
    return reasons


def run_pipeline(config_path: str) -> PipelineOutcome:
    started = datetime.now(UTC)
    config = load_app_config(Path(config_path))
    reasons = _blocking_reasons(config)
    status = "blocked" if reasons else "ready"
    if reasons:
        LOGGER.warning("pipeline blocked: %s", "; ".join(reasons))
    else:
        LOGGER.info("configuration complete; verified source execution may proceed")
    return PipelineOutcome(status, started, datetime.now(UTC), tuple(reasons))
