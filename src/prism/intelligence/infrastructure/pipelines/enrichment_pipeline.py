"""
Intelligence Infrastructure Pipeline — Dataflow-Style Enrichment Configuration

Architectural Intent:
- Declarative pipeline configuration for enrichment workflows
- Defines stage ordering, parallelism, timeouts, and retry policies
- Pipeline config is passed to DAGOrchestrator for execution
- Separates pipeline topology from execution runtime
- Supports both single-product and batch enrichment patterns

Pipeline Topology:
    ┌─────────────────────┐     ┌──────────────────────┐
    │ extract_attributes  │────>│ generate_description  │──┐
    └─────────────────────┘     └──────────────────────┘  │
    ┌─────────────────────┐                                │  ┌────────────────────┐
    │ assess_image_quality│                                ├─>│ generate_embedding │
    └─────────────────────┘                                │  └────────────────────┘
                                                           │
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RetryPolicy(str, Enum):
    """Retry strategies for pipeline stage failures."""

    NONE = "none"
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"


@dataclass(frozen=True)
class StageConfig:
    """Configuration for a single enrichment pipeline stage."""

    name: str
    depends_on: tuple[str, ...] = ()
    is_critical: bool = True
    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy = RetryPolicy.EXPONENTIAL_BACKOFF
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    @property
    def retry_enabled(self) -> bool:
        """Whether retries are configured for this stage."""
        return self.retry_policy != RetryPolicy.NONE and self.max_retries > 0


@dataclass(frozen=True)
class PipelineConfig:
    """
    Declarative enrichment pipeline configuration.

    Defines the full topology and execution parameters for a product
    enrichment workflow. Used by the application layer to construct
    a DAGOrchestrator with the correct step ordering and timeouts.
    """

    name: str
    stages: tuple[StageConfig, ...] = ()
    max_concurrent_products: int = 5
    global_timeout_seconds: float = 300.0
    enable_quality_assessment: bool = True

    def stage_names(self) -> tuple[str, ...]:
        """Return all stage names in declaration order."""
        return tuple(s.name for s in self.stages)

    def get_stage(self, name: str) -> StageConfig | None:
        """Look up a stage by name."""
        for stage in self.stages:
            if stage.name == name:
                return stage
        return None


# Standard single-product enrichment pipeline
STANDARD_ENRICHMENT_PIPELINE = PipelineConfig(
    name="standard_enrichment",
    stages=(
        StageConfig(
            name="extract_attributes",
            depends_on=(),
            is_critical=True,
            timeout_seconds=60.0,
            retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            max_retries=3,
        ),
        StageConfig(
            name="assess_image_quality",
            depends_on=(),
            is_critical=False,
            timeout_seconds=30.0,
            retry_policy=RetryPolicy.FIXED_DELAY,
            max_retries=2,
        ),
        StageConfig(
            name="generate_description",
            depends_on=("extract_attributes",),
            is_critical=True,
            timeout_seconds=60.0,
            retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            max_retries=3,
        ),
        StageConfig(
            name="generate_embedding",
            depends_on=("generate_description",),
            is_critical=True,
            timeout_seconds=30.0,
            retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            max_retries=3,
        ),
    ),
    max_concurrent_products=5,
    global_timeout_seconds=300.0,
    enable_quality_assessment=True,
)

# High-throughput batch pipeline with relaxed timeouts
BATCH_ENRICHMENT_PIPELINE = PipelineConfig(
    name="batch_enrichment",
    stages=(
        StageConfig(
            name="extract_attributes",
            depends_on=(),
            is_critical=True,
            timeout_seconds=90.0,
            retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            max_retries=5,
        ),
        StageConfig(
            name="assess_image_quality",
            depends_on=(),
            is_critical=False,
            timeout_seconds=45.0,
            retry_policy=RetryPolicy.NONE,
            max_retries=0,
        ),
        StageConfig(
            name="generate_description",
            depends_on=("extract_attributes",),
            is_critical=True,
            timeout_seconds=90.0,
            retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            max_retries=5,
        ),
        StageConfig(
            name="generate_embedding",
            depends_on=("generate_description",),
            is_critical=True,
            timeout_seconds=45.0,
            retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            max_retries=5,
        ),
    ),
    max_concurrent_products=10,
    global_timeout_seconds=600.0,
    enable_quality_assessment=False,
)
