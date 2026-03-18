"""
Payment Infrastructure — FX Rate Provider Adapter

Architectural Intent:
- Implements FXRatePort protocol for fetching live FX rates
- Supports multiple FX providers (e.g., ECB, XE, Planet DCC)
- Each adapter instance represents one provider
- Rates include expiry timestamps for staleness detection
- In production: uses httpx for async HTTP calls to rate APIs

Production Note:
- Replace stub with actual API integration per provider
- ECB rates update daily; commercial providers update in real-time
- Rate caching should be handled at the infrastructure/caching layer
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from prism.shared.domain.value_objects import Currency

from prism.payment.domain.value_objects.fx import FXRate

logger = logging.getLogger(__name__)

# Stub reference rates (EUR base) for development
_STUB_RATES: dict[tuple[str, str], float] = {
    ("EUR", "USD"): 1.0850,
    ("EUR", "GBP"): 0.8575,
    ("EUR", "CHF"): 0.9425,
    ("EUR", "JPY"): 162.50,
    ("EUR", "CNY"): 7.8200,
    ("EUR", "AED"): 3.9850,
    ("EUR", "SAR"): 4.0700,
    ("EUR", "HKD"): 8.4800,
    ("EUR", "SGD"): 1.4600,
    ("EUR", "AUD"): 1.6650,
    ("EUR", "KRW"): 1425.00,
    ("USD", "EUR"): 0.9217,
    ("USD", "GBP"): 0.7903,
    ("USD", "CHF"): 0.8688,
    ("USD", "JPY"): 149.77,
    ("GBP", "EUR"): 1.1662,
    ("GBP", "USD"): 1.2654,
}


class FXRateProviderAdapter:
    """
    FX rate provider adapter implementing the FXRatePort protocol.

    Each instance is configured for a specific provider. Multiple instances
    can run concurrently for rate shopping (parallelism-first).
    """

    def __init__(
        self,
        provider_name: str,
        api_key: str = "",
        api_base_url: str = "",
        rate_ttl_seconds: int = 300,
        spread_bps: int = 0,
    ) -> None:
        """
        Initialise the FX rate provider.

        Args:
            provider_name: Identifier for this provider (e.g., "ecb", "xe", "planet_dcc")
            api_key: API key for the provider
            api_base_url: Base URL for the provider's API
            rate_ttl_seconds: How long a quoted rate remains valid
            spread_bps: Provider's spread in basis points (added to mid-market rate)
        """
        self._provider_name = provider_name
        self._api_key = api_key
        self._api_base_url = api_base_url
        self._rate_ttl_seconds = rate_ttl_seconds
        self._spread_bps = spread_bps

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def get_rate(
        self,
        source: Currency,
        target: Currency,
    ) -> FXRate:
        """
        Fetch the current FX rate for a currency pair.

        In production, this calls the provider's API. The development stub
        uses reference rates with configurable spread.
        """
        logger.info(
            "FX rate request: %s->%s via %s",
            source.value,
            target.value,
            self._provider_name,
        )

        # Look up stub rate
        pair_key = (source.value, target.value)
        base_rate = _STUB_RATES.get(pair_key)

        if base_rate is None:
            # Try inverse
            inverse_key = (target.value, source.value)
            inverse_rate = _STUB_RATES.get(inverse_key)
            if inverse_rate is None:
                raise ValueError(
                    f"No rate available for {source.value}->{target.value} "
                    f"from provider {self._provider_name}"
                )
            base_rate = 1.0 / inverse_rate

        # Apply provider spread
        spread_multiplier = 1 - (self._spread_bps / 10_000)
        adjusted_rate = round(base_rate * spread_multiplier, 6)

        now = datetime.now(UTC)
        return FXRate(
            source_currency=source,
            target_currency=target,
            rate=adjusted_rate,
            provider=self._provider_name,
            quoted_at=now,
            expires_at=now + timedelta(seconds=self._rate_ttl_seconds),
        )
