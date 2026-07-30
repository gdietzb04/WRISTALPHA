"""Conservative exact-first entity resolution."""

from __future__ import annotations

from dataclasses import dataclass

from wristalpha.analytics.cleaning import CleanListing, normalize_reference


@dataclass(frozen=True)
class CanonicalReference:
    reference_id: str
    brand: str
    canonical_reference: str
    family: str


@dataclass(frozen=True)
class Resolution:
    reference_id: str | None
    confidence: float
    reason: str


def resolve_reference(
    listing: CleanListing,
    catalog: list[CanonicalReference],
) -> Resolution:
    if listing.brand is None or listing.reference_hint is None:
        return Resolution(None, 0.0, "missing_brand_or_reference")
    brand = listing.brand.casefold()
    reference = normalize_reference(listing.reference_hint)
    matches = [
        candidate
        for candidate in catalog
        if candidate.brand.casefold() == brand
        and normalize_reference(candidate.canonical_reference) == reference
    ]
    if len(matches) == 1:
        return Resolution(matches[0].reference_id, 1.0, "exact_brand_reference")
    if len(matches) > 1:
        return Resolution(None, 0.0, "ambiguous_catalog")
    return Resolution(None, 0.0, "no_exact_match")
