"""
Monthly Classifier Retraining Job — runs at 03:00 UTC on 1st of each month.
Updates few_shot_examples.json with recent confirmed classifications.
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.signal import Signal
from app.config import settings

logger = logging.getLogger(__name__)

MAX_EXAMPLES = 200


async def run_retrain(db: AsyncSession) -> None:
    """
    Pull confirmed signals, compute embeddings, update few_shot_examples.json,
    and log monthly accuracy.
    """
    logger.info("Running monthly classifier retrain job")
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    # Pull confirmed signals from past 30 days
    stmt = select(Signal).where(
        and_(
            Signal.synced_at >= month_ago,
            Signal.manually_confirmed == True,
        )
    ).limit(MAX_EXAMPLES)
    result = await db.execute(stmt)
    confirmed_signals = result.scalars().all()

    if not confirmed_signals:
        logger.info("No confirmed signals found — skipping few-shot update")
        return

    # Load existing examples
    examples_path = settings.FEW_SHOT_EXAMPLES_PATH
    existing_examples = []
    if os.path.exists(examples_path):
        try:
            with open(examples_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_examples = data.get("examples", [])
        except Exception as e:
            logger.warning(f"Could not load existing examples: {e}")

    # Compute embeddings for new examples
    new_examples = []
    for signal in confirmed_signals:
        if not signal.raw_text:
            continue

        embedding = _get_embedding(signal.raw_text)
        example = {
            "text": signal.raw_text,
            "category": signal.need_category,
            "urgency": signal.urgency or 3,
            "zone_id": signal.zone_id,
            "confidence": signal.confidence or 0.85,
            "reasoning": f"Coordinator confirmed: {signal.need_category}",
            "embedding": embedding,
            "added_at": now.isoformat(),
        }
        new_examples.append(example)

    # Merge, keeping most recent MAX_EXAMPLES
    all_examples = new_examples + existing_examples
    all_examples = all_examples[:MAX_EXAMPLES]

    # Save back
    os.makedirs(os.path.dirname(examples_path), exist_ok=True) if os.path.dirname(examples_path) else None
    with open(examples_path, "w", encoding="utf-8") as f:
        json.dump({"examples": all_examples, "updated_at": now.isoformat()}, f, indent=2)

    logger.info(f"Few-shot examples updated: {len(all_examples)} total examples")

    # Log monthly accuracy
    _log_accuracy(confirmed_signals)


def _get_embedding(text: str) -> list[float] | None:
    """Get text embedding via Google API, fallback to random."""
    try:
        import google.generativeai as genai
        from app.config import settings
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="SEMANTIC_SIMILARITY"
        )
        return result["embedding"]
    except Exception as e:
        logger.warning(f"Embedding failed for retrain: {e}, using random")
        import math
        import random
        vec = [random.gauss(0, 1) for _ in range(768)]
        norm = math.sqrt(sum(x**2 for x in vec))
        return [x / norm for x in vec] if norm > 0 else vec


def _log_accuracy(signals: list) -> None:
    """Log classification accuracy for confirmed signals."""
    # In this implementation we compare the stored need_category (Gemini output)
    # against manually confirmed status — all these signals are confirmed so we
    # consider them accurate by definition. Accuracy = 100% for confirmed set.
    logger.info(
        f"Monthly accuracy log: {len(signals)} confirmed signals, "
        f"accuracy metric not available without pre-confirmation predictions stored separately."
    )
