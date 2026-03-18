"""
UCP Ingest Adapter

Architectural Intent:
- Transforms raw Unified Commerce Platform (UCP) JSON payloads into domain Product aggregates
- Acts as an anti-corruption layer between the external UCP format and PRISM's domain model
- Handles field mapping, normalisation, and validation of incoming UCP data
- Produces IngestProductCommand objects for the application layer

Design Notes:
- UCP payloads vary by retailer integration — this adapter normalises the common fields
- Missing or malformed fields are handled gracefully with sensible defaults
- Image URLs from UCP are expected as HTTPS URLs and are converted to GCS URIs
  after asset download (handled separately by the asset pipeline)
- Price normalisation handles both "price" (flat) and "pricing" (nested) UCP formats
"""

from __future__ import annotations

from typing import Any

from prism.catalogue.application.commands.ingest_product import IngestProductCommand


class UCPIngestAdapter:
    """
    Adapter that transforms raw UCP JSON data into IngestProductCommand objects.

    The Unified Commerce Platform (UCP) is the external system that feeds product
    data into PRISM. Each retailer's UCP integration may use slightly different
    field names and structures. This adapter normalises them into PRISM's
    canonical command format.

    Usage:
        adapter = UCPIngestAdapter(tenant_id="tenant-123")
        command = adapter.transform(ucp_payload)
        result = await ingest_use_case.execute(command)
    """

    def __init__(self, tenant_id: str) -> None:
        """
        Initialise the adapter for a specific tenant.

        Args:
            tenant_id: The PRISM tenant ID that will own ingested products.
        """
        self._tenant_id = tenant_id

    def transform(self, ucp_data: dict[str, Any]) -> IngestProductCommand:
        """
        Transform a raw UCP JSON payload into an IngestProductCommand.

        Maps UCP fields to PRISM's canonical product schema, normalising
        field names, extracting nested structures, and applying defaults
        for missing data.

        Args:
            ucp_data: Raw UCP JSON payload as a Python dictionary.

        Returns:
            An IngestProductCommand ready for the application layer.

        Raises:
            ValueError: If required fields (sku, name) are missing.
        """
        sku = self._extract_required(ucp_data, "sku", aliases=["product_id", "item_id"])
        name = self._extract_required(ucp_data, "name", aliases=["title", "product_name"])

        brand = self._extract_optional(
            ucp_data, "brand", aliases=["brand_name", "manufacturer"], default=""
        )
        description = self._extract_optional(
            ucp_data, "description", aliases=["long_description", "body_html"], default=""
        )
        category = self._extract_optional(
            ucp_data, "category", aliases=["product_type", "type"], default=""
        )
        subcategory = self._extract_optional(
            ucp_data, "subcategory", aliases=["sub_category", "product_subtype"], default=""
        )

        # Extract attributes from UCP's flat or nested format
        attributes = self._extract_attributes(ucp_data)

        # Extract image URIs
        image_uris = self._extract_images(ucp_data)

        # Extract price
        price_amount, price_currency = self._extract_price(ucp_data)

        # Extract taxonomy codes if present
        taxonomy_codes = self._extract_taxonomy(ucp_data)

        return IngestProductCommand(
            tenant_id=self._tenant_id,
            sku=sku,
            name=name,
            brand=brand,
            description=description,
            category=category,
            subcategory=subcategory,
            attributes=attributes,
            image_uris=image_uris,
            price_amount=price_amount,
            price_currency=price_currency,
            taxonomy_codes=taxonomy_codes,
            source="ucp",
        )

    def transform_batch(
        self, ucp_items: list[dict[str, Any]]
    ) -> list[IngestProductCommand]:
        """
        Transform a batch of UCP payloads into IngestProductCommands.

        Skips items that fail validation (logs would be added in production).

        Args:
            ucp_items: List of raw UCP JSON payloads.

        Returns:
            List of successfully transformed IngestProductCommands.
        """
        commands: list[IngestProductCommand] = []
        for item in ucp_items:
            try:
                commands.append(self.transform(item))
            except ValueError:
                # In production: log the validation error with item context
                continue
        return commands

    # ── Field extraction helpers ──────────────────────────────────────

    @staticmethod
    def _extract_required(
        data: dict[str, Any],
        primary_key: str,
        aliases: list[str] | None = None,
    ) -> str:
        """
        Extract a required field, checking aliases if the primary key is missing.

        Args:
            data: Source dictionary.
            primary_key: Preferred field name.
            aliases: Alternative field names to check.

        Returns:
            The field value as a string.

        Raises:
            ValueError: If the field is not found under any key.
        """
        value = data.get(primary_key)
        if value:
            return str(value).strip()

        for alias in aliases or []:
            value = data.get(alias)
            if value:
                return str(value).strip()

        all_keys = [primary_key] + (aliases or [])
        raise ValueError(
            f"Required field missing. Checked keys: {all_keys}"
        )

    @staticmethod
    def _extract_optional(
        data: dict[str, Any],
        primary_key: str,
        aliases: list[str] | None = None,
        default: str = "",
    ) -> str:
        """Extract an optional field with fallback to aliases and default."""
        value = data.get(primary_key)
        if value:
            return str(value).strip()

        for alias in aliases or []:
            value = data.get(alias)
            if value:
                return str(value).strip()

        return default

    @staticmethod
    def _extract_attributes(data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract product attributes from UCP's various formats.

        Supports:
        - "attributes" dict (direct)
        - "custom_attributes" list of {"key": ..., "value": ...} objects
        - "metadata" dict (fallback)
        """
        # Direct attributes dict
        if "attributes" in data and isinstance(data["attributes"], dict):
            return data["attributes"]

        # Shopify-style custom_attributes
        if "custom_attributes" in data and isinstance(data["custom_attributes"], list):
            return {
                item["key"]: item["value"]
                for item in data["custom_attributes"]
                if isinstance(item, dict) and "key" in item and "value" in item
            }

        # Metadata fallback
        if "metadata" in data and isinstance(data["metadata"], dict):
            return data["metadata"]

        return {}

    @staticmethod
    def _extract_images(data: dict[str, Any]) -> list[str]:
        """
        Extract image URIs from UCP payload.

        Supports:
        - "images" list of strings (URIs)
        - "images" list of {"src": ...} objects
        - "image_url" single string
        """
        images: list[str] = []

        if "images" in data:
            raw_images = data["images"]
            if isinstance(raw_images, list):
                for img in raw_images:
                    if isinstance(img, str):
                        images.append(img)
                    elif isinstance(img, dict) and "src" in img:
                        images.append(str(img["src"]))

        if not images and "image_url" in data:
            images.append(str(data["image_url"]))

        return images

    @staticmethod
    def _extract_price(data: dict[str, Any]) -> tuple[float | None, str]:
        """
        Extract price from UCP's flat or nested format.

        Returns:
            Tuple of (amount or None, currency code).
        """
        # Flat format: "price" and "currency"
        if "price" in data:
            try:
                amount = float(data["price"])
                currency = str(data.get("currency", "USD")).upper()
                return amount, currency
            except (ValueError, TypeError):
                pass

        # Nested format: "pricing": {"amount": ..., "currency": ...}
        if "pricing" in data and isinstance(data["pricing"], dict):
            pricing = data["pricing"]
            try:
                amount = float(pricing.get("amount", pricing.get("price", 0)))
                currency = str(pricing.get("currency", "USD")).upper()
                if amount > 0:
                    return amount, currency
            except (ValueError, TypeError):
                pass

        return None, "USD"

    @staticmethod
    def _extract_taxonomy(data: dict[str, Any]) -> list[str]:
        """Extract taxonomy codes from UCP payload."""
        codes: list[str] = []

        if "taxonomy_codes" in data and isinstance(data["taxonomy_codes"], list):
            codes.extend(str(c) for c in data["taxonomy_codes"])

        if "gs1_code" in data:
            codes.append(str(data["gs1_code"]))

        if "google_product_category" in data:
            codes.append(str(data["google_product_category"]))

        return codes
