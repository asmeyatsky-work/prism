"""
Try-On Infrastructure — Gemini Vision Body Extractor

Architectural Intent:
- Implements BodyExtractionPort using Google Gemini Vision API
- Receives raw customer image bytes, sends to Gemini for pose extraction
- Returns structured BodyPose value object with keypoints
- Customer image bytes are sent over TLS to Gemini and NOT stored locally

Privacy:
- Image bytes are held in-memory only for the duration of the API call
- No local caching, logging, or persistence of customer images
- Gemini API data processing agreement covers transient processing
"""

from __future__ import annotations

import json
import logging
from typing import Any

from prism.tryon.domain.value_objects.composition import BodyPose

logger = logging.getLogger(__name__)


# Gemini structured output schema for body pose extraction
_POSE_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "keypoints": {
            "type": "object",
            "description": "Body landmark keypoints as {name: [x, y, confidence]}",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
            },
        },
        "orientation": {
            "type": "string",
            "enum": ["front", "side", "back", "three_quarter"],
        },
        "body_type": {
            "type": "string",
            "description": "Inferred body silhouette category",
        },
    },
    "required": ["keypoints", "orientation", "body_type"],
}

_EXTRACTION_PROMPT = (
    "Analyze this image and extract body pose keypoints for virtual garment try-on. "
    "Return structured JSON with: keypoints (mapping of body landmark names to "
    "[x, y, confidence] arrays where coordinates are normalised 0-1), "
    "orientation (front/side/back/three_quarter), and body_type classification. "
    "Focus on landmarks relevant to garment fitting: shoulders, elbows, wrists, "
    "hips, knees, ankles, neck, and torso midpoints."
)


class GeminiVisionBodyExtractor:
    """
    Body pose extractor powered by Google Gemini Vision API.

    Implements the BodyExtractionPort protocol. Accepts raw image bytes,
    sends them to Gemini with a structured output schema, and returns
    a BodyPose value object.

    Args:
        project_id: Google Cloud project ID.
        location: Google Cloud region (default: us-central1).
        model_name: Gemini model identifier (default: gemini-2.0-flash).
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        model_name: str = "gemini-2.0-flash",
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model_name = model_name
        self._client: Any = None  # Lazy initialised

    async def extract_pose(self, image_bytes: bytes) -> BodyPose:
        """
        Extract body pose from customer image bytes.

        The image bytes are sent to Gemini Vision API over TLS and are
        NOT persisted locally. After the API response is received, no
        reference to the original bytes is retained.

        Args:
            image_bytes: Raw customer image (JPEG/PNG).

        Returns:
            BodyPose with extracted keypoints.

        Raises:
            ValueError: If the image is empty or no body is detected.
            RuntimeError: If the Gemini API call fails.
        """
        if not image_bytes:
            raise ValueError("Cannot extract pose from empty image bytes")

        client = await self._get_client()

        try:
            response = await client.aio.models.generate_content(
                model=self._model_name,
                contents=[
                    {
                        "parts": [
                            {"text": _EXTRACTION_PROMPT},
                            {
                                "inline_data": {
                                    "mime_type": _detect_mime_type(image_bytes),
                                    "data": image_bytes,
                                },
                            },
                        ],
                    },
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": _POSE_EXTRACTION_SCHEMA,
                },
            )

            # Parse structured response
            result = json.loads(response.text)

        except Exception as exc:
            logger.error("Gemini pose extraction failed: %s", exc)
            raise RuntimeError(f"Gemini pose extraction failed: {exc}") from exc

        # Validate the response has keypoints
        keypoints_raw = result.get("keypoints", {})
        if not keypoints_raw:
            raise ValueError("No body keypoints detected in the image")

        # Convert list values to tuples for the frozen BodyPose
        keypoints: dict[str, tuple[float, float, float]] = {}
        for name, coords in keypoints_raw.items():
            if len(coords) >= 3:
                keypoints[name] = (float(coords[0]), float(coords[1]), float(coords[2]))

        return BodyPose(
            keypoints=keypoints,
            orientation=result.get("orientation", "front"),
            body_type=result.get("body_type", "standard"),
        )

    async def _get_client(self) -> Any:
        """Lazy-initialise the Gemini client."""
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(
                    project=self._project_id,
                    location=self._location,
                )
            except ImportError as exc:
                raise RuntimeError(
                    "google-genai package is required for Gemini Vision adapter. "
                    "Install with: pip install google-genai"
                ) from exc
        return self._client


def _detect_mime_type(image_bytes: bytes) -> str:
    """Detect image MIME type from magic bytes."""
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    # Default to JPEG for luxury retail images
    return "image/jpeg"
