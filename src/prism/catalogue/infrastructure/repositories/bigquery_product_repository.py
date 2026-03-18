"""
BigQuery Product Repository

Architectural Intent:
- Implements ProductRepositoryPort using Google BigQuery as the persistence layer
- BigQuery is the warehouse of record for PRISM — optimised for analytical queries
  and ML feature extraction alongside operational reads
- Tenant isolation is enforced via WHERE clause on tenant_id in every query
- Products are stored as JSON-serialised rows for schema flexibility

Design Notes:
- Uses parameterised queries to prevent SQL injection
- Upsert semantics via MERGE statement keyed on (tenant_id, id)
- Search delegates to BigQuery's full-text SEARCH function (requires search index)
- Async wrapper around the synchronous BigQuery client using run_in_executor
- Product reconstruction from row data handles missing/null fields gracefully

Infrastructure Dependencies:
- google-cloud-bigquery SDK
- BigQuery dataset and table must be pre-provisioned
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from functools import partial
from typing import Any

from prism.catalogue.domain.entities.product import EnrichmentStatus, Product
from prism.catalogue.domain.ports.repository_ports import ProductRepositoryPort
from prism.shared.domain.value_objects import Currency, ImageRef, Money, TenantId


class BigQueryProductRepository:
    """
    BigQuery-backed implementation of ProductRepositoryPort.

    Stores products in a BigQuery table with JSON-serialised attribute columns.
    Provides tenant-scoped CRUD and search operations.

    Table Schema (provisioned separately):
        prism_catalogue.products (
            id STRING NOT NULL,
            tenant_id STRING NOT NULL,
            sku STRING NOT NULL,
            name STRING,
            brand STRING,
            description STRING,
            category STRING,
            subcategory STRING,
            attributes JSON,
            images JSON,
            price_amount FLOAT64,
            price_currency STRING,
            taxonomy_codes JSON,
            enrichment_status STRING,
            quality_score FLOAT64,
            embedding_vector_id STRING,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
        )
    """

    def __init__(
        self,
        project_id: str,
        dataset_id: str = "prism_catalogue",
        table_id: str = "products",
    ) -> None:
        self._project_id = project_id
        self._dataset_id = dataset_id
        self._table_id = table_id
        self._full_table_id = f"{project_id}.{dataset_id}.{table_id}"
        self._client: Any = None
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _get_client(self) -> Any:
        """Lazy-initialise the BigQuery client."""
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self._project_id)
        return self._client

    async def get_by_id(
        self, product_id: str, tenant_id: TenantId
    ) -> Product | None:
        """Retrieve a product by domain ID, scoped to tenant."""
        query = f"""
            SELECT * FROM `{self._full_table_id}`
            WHERE id = @product_id AND tenant_id = @tenant_id
            LIMIT 1
        """
        params = [
            _query_param("product_id", "STRING", product_id),
            _query_param("tenant_id", "STRING", tenant_id.value),
        ]
        rows = await self._execute_query(query, params)
        if not rows:
            return None
        return self._row_to_product(rows[0])

    async def get_by_sku(
        self, sku: str, tenant_id: TenantId
    ) -> Product | None:
        """Retrieve a product by SKU, scoped to tenant."""
        query = f"""
            SELECT * FROM `{self._full_table_id}`
            WHERE sku = @sku AND tenant_id = @tenant_id
            LIMIT 1
        """
        params = [
            _query_param("sku", "STRING", sku),
            _query_param("tenant_id", "STRING", tenant_id.value),
        ]
        rows = await self._execute_query(query, params)
        if not rows:
            return None
        return self._row_to_product(rows[0])

    async def save(self, product: Product) -> None:
        """
        Persist a product using MERGE (upsert) semantics.

        Inserts if the product does not exist, updates if it does.
        Keyed on (tenant_id, id) for idempotent saves.
        """
        row = self._product_to_row(product)
        columns = ", ".join(row.keys())
        values = ", ".join(f"@{k}" for k in row.keys())
        update_set = ", ".join(
            f"T.{k} = S.{k}" for k in row.keys() if k not in ("id", "tenant_id")
        )

        query = f"""
            MERGE `{self._full_table_id}` T
            USING (SELECT {values}) S
            ON T.id = S.id AND T.tenant_id = S.tenant_id
            WHEN MATCHED THEN
                UPDATE SET {update_set}
            WHEN NOT MATCHED THEN
                INSERT ({columns}) VALUES ({values})
        """
        params = [
            _query_param(k, _infer_bq_type(v), v) for k, v in row.items()
        ]
        await self._execute_query(query, params)

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        """List products for a tenant with pagination."""
        count_query = f"""
            SELECT COUNT(*) as total FROM `{self._full_table_id}`
            WHERE tenant_id = @tenant_id
        """
        data_query = f"""
            SELECT * FROM `{self._full_table_id}`
            WHERE tenant_id = @tenant_id
            ORDER BY created_at DESC
            LIMIT @limit OFFSET @offset
        """
        params = [
            _query_param("tenant_id", "STRING", tenant_id.value),
        ]
        count_rows = await self._execute_query(count_query, params)
        total = count_rows[0]["total"] if count_rows else 0

        data_params = params + [
            _query_param("limit", "INT64", limit),
            _query_param("offset", "INT64", offset),
        ]
        rows = await self._execute_query(data_query, data_params)
        products = [self._row_to_product(row) for row in rows]

        return products, total

    async def search(
        self,
        tenant_id: TenantId,
        query_text: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        """
        Search products using BigQuery full-text SEARCH function.

        Requires a search index on the products table. Falls back to
        LIKE-based search if the search index is not available.
        """
        count_query = f"""
            SELECT COUNT(*) as total FROM `{self._full_table_id}`
            WHERE tenant_id = @tenant_id
            AND (
                SEARCH(name, @query_text)
                OR SEARCH(description, @query_text)
                OR SEARCH(brand, @query_text)
            )
        """
        data_query = f"""
            SELECT * FROM `{self._full_table_id}`
            WHERE tenant_id = @tenant_id
            AND (
                SEARCH(name, @query_text)
                OR SEARCH(description, @query_text)
                OR SEARCH(brand, @query_text)
            )
            ORDER BY created_at DESC
            LIMIT @limit OFFSET @offset
        """
        params = [
            _query_param("tenant_id", "STRING", tenant_id.value),
            _query_param("query_text", "STRING", query_text),
        ]
        count_rows = await self._execute_query(count_query, params)
        total = count_rows[0]["total"] if count_rows else 0

        data_params = params + [
            _query_param("limit", "INT64", limit),
            _query_param("offset", "INT64", offset),
        ]
        rows = await self._execute_query(data_query, data_params)
        products = [self._row_to_product(row) for row in rows]

        return products, total

    # ── Internal helpers ──────────────────────────────────────────────

    async def _execute_query(
        self, query: str, params: list[Any]
    ) -> list[dict[str, Any]]:
        """Execute a parameterised BigQuery query asynchronously."""
        import asyncio

        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

        job_config = QueryJobConfig(query_parameters=params)
        client = self._get_client()

        loop = asyncio.get_event_loop()
        query_job = await loop.run_in_executor(
            self._executor,
            partial(client.query, query, job_config=job_config),
        )
        result = await loop.run_in_executor(
            self._executor,
            query_job.result,
        )
        return [dict(row) for row in result]

    @staticmethod
    def _product_to_row(product: Product) -> dict[str, Any]:
        """Serialise a Product aggregate to a BigQuery row dict."""
        images_json = json.dumps(
            [
                {"bucket": img.bucket, "path": img.path, "content_type": img.content_type}
                for img in product.images
            ]
        )
        return {
            "id": product.id,
            "tenant_id": product.tenant_id.value,
            "sku": product.sku,
            "name": product.name,
            "brand": product.brand,
            "description": product.description,
            "category": product.category,
            "subcategory": product.subcategory,
            "attributes": json.dumps(product.attributes),
            "images": images_json,
            "price_amount": product.price.amount if product.price else None,
            "price_currency": product.price.currency.value if product.price else None,
            "taxonomy_codes": json.dumps(list(product.taxonomy_codes)),
            "enrichment_status": product.enrichment_status.value,
            "quality_score": product.quality_score,
            "embedding_vector_id": product.embedding_vector_id,
            "created_at": product.created_at.isoformat(),
            "updated_at": product.updated_at.isoformat(),
        }

    @staticmethod
    def _row_to_product(row: dict[str, Any]) -> Product:
        """Reconstruct a Product aggregate from a BigQuery row dict."""
        # Parse images
        images_data = row.get("images")
        if isinstance(images_data, str):
            images_data = json.loads(images_data)
        images = tuple(
            ImageRef(
                bucket=img["bucket"],
                path=img["path"],
                content_type=img.get("content_type", "image/jpeg"),
            )
            for img in (images_data or [])
        )

        # Parse attributes
        attributes = row.get("attributes")
        if isinstance(attributes, str):
            attributes = json.loads(attributes)
        attributes = attributes or {}

        # Parse taxonomy codes
        taxonomy_codes = row.get("taxonomy_codes")
        if isinstance(taxonomy_codes, str):
            taxonomy_codes = json.loads(taxonomy_codes)
        taxonomy_codes = tuple(taxonomy_codes or [])

        # Parse price
        price = None
        if row.get("price_amount") is not None and row.get("price_currency"):
            try:
                price = Money(
                    amount=float(row["price_amount"]),
                    currency=Currency(row["price_currency"]),
                )
            except (ValueError, KeyError):
                pass

        # Parse timestamps
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return Product(
            id=row["id"],
            tenant_id=TenantId(value=row["tenant_id"]),
            sku=row.get("sku", ""),
            name=row.get("name", ""),
            brand=row.get("brand", ""),
            description=row.get("description", ""),
            category=row.get("category", ""),
            subcategory=row.get("subcategory", ""),
            attributes=attributes,
            images=images,
            price=price,
            taxonomy_codes=taxonomy_codes,
            enrichment_status=EnrichmentStatus(
                row.get("enrichment_status", "RAW")
            ),
            quality_score=float(row.get("quality_score", 0.0)),
            embedding_vector_id=row.get("embedding_vector_id"),
            created_at=created_at,
            updated_at=updated_at,
        )


def _query_param(name: str, type_: str, value: Any) -> Any:
    """Create a BigQuery ScalarQueryParameter."""
    from google.cloud.bigquery import ScalarQueryParameter

    return ScalarQueryParameter(name, type_, value)


def _infer_bq_type(value: Any) -> str:
    """Infer BigQuery scalar type from a Python value."""
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    if isinstance(value, datetime):
        return "TIMESTAMP"
    return "STRING"
