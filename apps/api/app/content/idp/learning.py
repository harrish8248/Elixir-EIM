"""
Continuous Learning Service for Elixir EIM IDP.
Learns from human review corrections:
- Stores per-vendor geometric field templates (spatial priors)
- Learns where recurring vendors position key fields (invoice #, date, total)
- Boosts extraction accuracy on subsequent invoices from the same vendor
"""

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel

from apps.api.app.content.idp.models import BoundingBox, OcrPageResult, OcrWord
from apps.api.app.platform.logging import logger

LEARNING_DATA_PATH = Path("docs/ocr-benchmark/vendor_templates.json")


class LearnedFieldPrior(BaseModel):
    vendor_name: str
    field_name: str
    rel_x: float  # x / page_width (0.0 - 1.0)
    rel_y: float  # y / page_height (0.0 - 1.0)
    rel_w: float  # width / page_width
    rel_h: float  # height / page_height
    sample_count: int = 1


class VendorTemplateStore:
    """Stores and retrieves learned geometric priors for vendor templates."""

    def __init__(self, storage_path: Path = LEARNING_DATA_PATH):
        self.storage_path = storage_path
        self.templates: dict[str, dict[str, LearnedFieldPrior]] = {}
        self.load()

    def load(self):
        """Load stored templates from disk if available."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    raw = json.load(f)
                    for vendor, fields in raw.items():
                        self.templates[vendor] = {}
                        for fname, data in fields.items():
                            self.templates[vendor][fname] = LearnedFieldPrior(**data)
            except Exception as e:
                logger.warning(f"Could not load vendor templates: {e}")

    def save(self):
        """Persist learned templates to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            serializable = {
                vendor: {fname: prior.model_dump() for fname, prior in fields.items()}
                for vendor, fields in self.templates.items()
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist vendor templates: {e}")

    def record_correction(
        self,
        vendor_name: str,
        field_name: str,
        bbox: BoundingBox,
        page_width: int = 850,
        page_height: int = 1100,
    ):
        """Update learned relative spatial coordinates from a validated field."""
        if not vendor_name or not bbox or page_width <= 0 or page_height <= 0:
            return

        v_key = vendor_name.strip()
        if v_key not in self.templates:
            self.templates[v_key] = {}

        rel_x = bbox.x / page_width
        rel_y = bbox.y / page_height
        rel_w = bbox.width / page_width
        rel_h = bbox.height / page_height

        if field_name in self.templates[v_key]:
            existing = self.templates[v_key][field_name]
            n = existing.sample_count
            # Incremental moving average
            existing.rel_x = round((existing.rel_x * n + rel_x) / (n + 1), 4)
            existing.rel_y = round((existing.rel_y * n + rel_y) / (n + 1), 4)
            existing.rel_w = round((existing.rel_w * n + rel_w) / (n + 1), 4)
            existing.rel_h = round((existing.rel_h * n + rel_h) / (n + 1), 4)
            existing.sample_count += 1
        else:
            self.templates[v_key][field_name] = LearnedFieldPrior(
                vendor_name=v_key,
                field_name=field_name,
                rel_x=round(rel_x, 4),
                rel_y=round(rel_y, 4),
                rel_w=round(rel_w, 4),
                rel_h=round(rel_h, 4),
                sample_count=1,
            )
        self.save()

    def get_candidate_words(
        self,
        vendor_name: str,
        field_name: str,
        page: OcrPageResult,
        tolerance_rel: float = 0.08,
    ) -> list[OcrWord]:
        """Find OCR words sitting within the learned template region for this vendor."""
        v_key = vendor_name.strip()
        if v_key not in self.templates or field_name not in self.templates[v_key]:
            return []

        prior = self.templates[v_key][field_name]
        pw = page.width or 850
        ph = page.height or 1100

        target_min_x = (prior.rel_x - tolerance_rel) * pw
        target_max_x = (prior.rel_x + prior.rel_w + tolerance_rel) * pw
        target_min_y = (prior.rel_y - tolerance_rel) * ph
        target_max_y = (prior.rel_y + prior.rel_h + tolerance_rel) * ph

        matches = []
        for w in page.words:
            wx, wy = w.bbox.x, w.bbox.y
            if target_min_x <= wx <= target_max_x and target_min_y <= wy <= target_max_y:
                matches.append(w)

        matches.sort(key=lambda w: (w.bbox.y, w.bbox.x))
        return matches
