import pytest

from wristalpha.adapters import (
    AdapterConfigurationError,
    LicensedApiAdapter,
    MarketplaceQuery,
)


def test_licensed_api_stub_fails_closed_without_inventing_endpoint() -> None:
    adapter = LicensedApiAdapter("licensed-provider")

    with pytest.raises(AdapterConfigurationError, match="documentation"):
        adapter.fetch_listings(MarketplaceQuery(), since=None)
