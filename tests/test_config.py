from pathlib import Path

import pytest
from pydantic import ValidationError

from wristalpha.config import AppConfig, SourcedCost, SourcedMoney, load_app_config


def test_default_config_is_valid_and_unknown_costs_are_explicit() -> None:
    config_path = Path(__file__).parents[1] / "config" / "default.yaml"

    config = load_app_config(config_path)

    assert config.config_version == 1
    assert config.universe.brands == ()
    for _, assumption in config.costs:
        assert assumption.value is None
        assert assumption.source is None
        assert assumption.source_needed


def test_money_requires_source_when_value_is_known() -> None:
    with pytest.raises(ValidationError, match="requires currency and source"):
        SourcedMoney(value="1000", currency="USD", source_needed=None)


def test_unknown_cost_requires_source_needed() -> None:
    with pytest.raises(ValidationError, match="requires source_needed"):
        SourcedCost(value=None, unit="fraction", source=None, source_needed=None)


def test_config_forbids_unreviewed_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AppConfig.model_validate(
            {
                "config_version": 1,
                "universe": {
                    "brands": [],
                    "references": [],
                    "maximum_listing_price": {
                        "value": None,
                        "currency": None,
                        "source": None,
                        "source_needed": "needed",
                    },
                },
                "portfolio": {
                    "next_purchase_budget": {
                        "value": None,
                        "currency": None,
                        "source": None,
                        "source_needed": "needed",
                    },
                    "holding_horizon": None,
                    "holdings": [],
                },
                "alerts": {"channel": None, "destination_env_var": None},
                "costs": {
                    name: {
                        "value": None,
                        "unit": "fraction",
                        "source": None,
                        "source_needed": "needed",
                    }
                    for name in (
                        "marketplace_commission",
                        "payment_or_escrow",
                        "shipping",
                        "insurance",
                        "import_duty_or_vat",
                        "authentication",
                        "servicing",
                        "dealer_bid_ask_spread",
                    )
                },
                "sources": {},
                "unreviewed": True,
            }
        )
