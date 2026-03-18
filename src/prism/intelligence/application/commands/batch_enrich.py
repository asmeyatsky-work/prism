"""
Intelligence Application Command — Batch Enrich Use Case

Architectural Intent:
- Fan-out/fan-in pattern for bulk product enrichment
- Semaphore-based rate limiting prevents infrastructure overload
- Individual product failures do not abort the batch
- Results are aggregated into a summary DTO
- Parallelism-first per skill2026 Principle 6
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from prism.intelligence.application.commands.enrich_product import (
    EnrichProductCommand,
    EnrichProductUseCase,
)
from prism.intelligence.application.dtos.enrichment_dto import (
    BatchEnrichmentResultDTO,
    EnrichmentJobDTO,
)
from prism.shared.application.dtos import CommandResult, TenantContext

# Default concurrency limit to prevent API rate-limit exhaustion
_DEFAULT_MAX_CONCURRENCY = 5


@dataclass(frozen=True)
class BatchEnrichCommand:
    """Command to enrich multiple products in a single batch."""

    product_commands: list[EnrichProductCommand] = field(default_factory=list)
    tenant_context: TenantContext = field(
        default_factory=lambda: TenantContext(tenant_id="default")
    )
    max_concurrency: int = _DEFAULT_MAX_CONCURRENCY


class BatchEnrichUseCase:
    """
    Fan-out/fan-in use case for enriching multiple products concurrently.

    Uses an asyncio.Semaphore to limit the number of concurrent enrichment
    jobs, preventing infrastructure overload (API rate limits, memory).
    Individual failures are captured without aborting the entire batch.
    """

    def __init__(self, enrich_product_use_case: EnrichProductUseCase) -> None:
        self._enrich_product = enrich_product_use_case

    async def execute(
        self,
        command: BatchEnrichCommand,
    ) -> CommandResult[BatchEnrichmentResultDTO]:
        """
        Execute batch enrichment for all products in the command.

        Args:
            command: Batch enrichment command containing per-product configs.

        Returns:
            CommandResult wrapping a BatchEnrichmentResultDTO summary.
        """
        if not command.product_commands:
            return CommandResult.ok(
                BatchEnrichmentResultDTO(
                    total_requested=0,
                    total_succeeded=0,
                    total_failed=0,
                    job_results=[],
                )
            )

        semaphore = asyncio.Semaphore(command.max_concurrency)

        async def _enrich_with_limit(
            product_cmd: EnrichProductCommand,
        ) -> CommandResult[str]:
            async with semaphore:
                return await self._enrich_product.execute(product_cmd)

        # Fan-out: dispatch all enrichments with concurrency limiting
        results = await asyncio.gather(
            *(_enrich_with_limit(cmd) for cmd in command.product_commands),
            return_exceptions=True,
        )

        # Fan-in: aggregate results
        succeeded = 0
        failed = 0
        job_dtos: list[EnrichmentJobDTO] = []
        now = datetime.now(UTC)

        for i, result in enumerate(results):
            product_cmd = command.product_commands[i]
            if isinstance(result, BaseException):
                failed += 1
                job_dtos.append(
                    EnrichmentJobDTO(
                        id="",
                        product_id=product_cmd.product_id,
                        tenant_id=product_cmd.tenant_context.tenant_id,
                        status="FAILED",
                        error_message=str(result),
                        model_version=product_cmd.model_version,
                        created_at=now,
                        updated_at=now,
                    )
                )
            elif isinstance(result, CommandResult) and result.success:
                succeeded += 1
            elif isinstance(result, CommandResult):
                failed += 1
                job_dtos.append(
                    EnrichmentJobDTO(
                        id="",
                        product_id=product_cmd.product_id,
                        tenant_id=product_cmd.tenant_context.tenant_id,
                        status="FAILED",
                        error_message=result.error or "Unknown error",
                        model_version=product_cmd.model_version,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                failed += 1

        return CommandResult.ok(
            BatchEnrichmentResultDTO(
                total_requested=len(command.product_commands),
                total_succeeded=succeeded,
                total_failed=failed,
                job_results=job_dtos,
            )
        )
