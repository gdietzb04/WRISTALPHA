"""Official/licensed API adapter boundary without invented provider details."""

from __future__ import annotations

from datetime import datetime

from wristalpha.adapters.base import (
    AdapterConfigurationError,
    MarketplaceAdapter,
    MarketplaceQuery,
    RawListing,
)


class LicensedApiAdapter(MarketplaceAdapter):
    """Disabled stub that is completed only from licensed provider documentation."""

    def __init__(self, provider_name: str | None = None) -> None:
        self._provider_name = provider_name

    def fetch_listings(
        self,
        query: MarketplaceQuery,
        since: datetime | None,
    ) -> list[RawListing]:
        del query, since
        provider = self._provider_name or "unconfigured provider"
        raise AdapterConfigurationError(
            f"{provider}: supply licensed API documentation, credentials, endpoint, "
            "and field mapping before enabling this adapter"
        )
