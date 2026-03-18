"""
Payment Application — Get FX Comparison Query

Architectural Intent:
- Fetches FX rates from multiple providers in PARALLEL (parallelism-first)
- Uses asyncio.gather for concurrent provider calls
- Returns FXComparisonDTO with best rate and savings analysis
- Pure read operation — no state mutation
"""

from __future__ import annotations

import asyncio

from prism.shared.application.dtos import QueryResult
from prism.shared.domain.value_objects import Currency, Money

from prism.payment.application.dtos.payment_dto import FXComparisonDTO, FXRateDTO
from prism.payment.domain.ports.payment_ports import FXRatePort
from prism.payment.domain.services.fx_service import FXService


class GetFXComparisonQuery:
    """
    Fetch and compare FX rates from multiple providers concurrently.

    Per skill2026 Principle 6: FX rate comparison runs concurrently
    across providers using asyncio.gather.
    """

    def __init__(
        self,
        fx_providers: list[FXRatePort],
    ) -> None:
        self._fx_providers = fx_providers
        self._fx_service = FXService()

    async def execute(
        self,
        source_currency: str,
        target_currency: str,
        amount: float,
    ) -> QueryResult[FXComparisonDTO]:
        """
        Fetch rates from all providers in parallel and return comparison.

        Providers that fail or timeout are silently excluded from the
        comparison — the query succeeds as long as at least one provider
        responds.
        """
        try:
            source = Currency(source_currency)
            target = Currency(target_currency)
        except ValueError as exc:
            return QueryResult.fail(f"Invalid currency: {exc}")

        if not self._fx_providers:
            return QueryResult.fail("No FX rate providers configured")

        # Parallel fetch from all providers
        tasks = [
            provider.get_rate(source, target)
            for provider in self._fx_providers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful results
        rates = [r for r in results if not isinstance(r, BaseException)]

        if not rates:
            return QueryResult.fail("All FX rate providers failed")

        # Build comparison using domain service
        money_amount = Money(amount=amount, currency=source)
        comparison = self._fx_service.compare_rates(rates, money_amount)

        # Map to DTOs
        rate_dtos = [
            FXRateDTO(
                source_currency=r.source_currency.value,
                target_currency=r.target_currency.value,
                rate=r.rate,
                provider=r.provider,
                quoted_at=r.quoted_at,
                expires_at=r.expires_at,
            )
            for r in comparison.rates
        ]

        best_dto = FXRateDTO(
            source_currency=comparison.best_rate.source_currency.value,
            target_currency=comparison.best_rate.target_currency.value,
            rate=comparison.best_rate.rate,
            provider=comparison.best_rate.provider,
            quoted_at=comparison.best_rate.quoted_at,
            expires_at=comparison.best_rate.expires_at,
        )

        response = FXComparisonDTO(
            rates=rate_dtos,
            best_rate=best_dto,
            savings_amount=comparison.savings_vs_worst.amount,
            savings_currency=comparison.savings_vs_worst.currency.value,
        )

        return QueryResult.ok(response)
