"""
Tests for the NLP classifier (Gemini-powered).
"""
import pytest
import json
import time
from unittest.mock import patch, MagicMock, AsyncMock
from app.services import nlp_classifier
from app.services.nlp_classifier import (
    classify_report, _classification_cache, CACHE_TTL_SECONDS,
    _cosine_similarity, _get_top_few_shot_examples,
)


class TestGeminiResponseParsing:
    @pytest.mark.asyncio
    async def test_valid_response_parsed_correctly(self):
        """A well-formed Gemini JSON response is parsed into structured output."""
        mock_response_text = json.dumps({
            "zone_id": "Zone 4",
            "need_category": "nutrition",
            "urgency": 4,
            "population_est": 50,
            "confidence": 0.91,
            "reasoning": "Children not eating for days indicates nutrition crisis."
        })

        mock_response = MagicMock()
        mock_response.text = mock_response_text
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                nlp_classifier._classification_cache.clear()
                result = await classify_report("Children in Zone 4 haven't eaten in days")

        assert result["zone_id"] == "Zone 4"
        assert result["need_category"] == "nutrition"
        assert result["urgency"] == 4
        assert result["confidence"] == pytest.approx(0.91)
        assert result["needs_manual_review"] is False

    @pytest.mark.asyncio
    async def test_malformed_json_sets_confidence_zero(self):
        """Malformed Gemini JSON → confidence=0.0, flagged for manual review."""
        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all!"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                nlp_classifier._classification_cache.clear()
                result = await classify_report("Some field report text here")

        assert result["confidence"] == 0.0
        assert result["needs_manual_review"] is True

    @pytest.mark.asyncio
    async def test_api_exception_flags_manual_review(self):
        """Gemini API exception → confidence=0.0, flagged for manual review."""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error")

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                nlp_classifier._classification_cache.clear()
                result = await classify_report("A report that causes an API error")

        assert result["confidence"] == 0.0
        assert result["needs_manual_review"] is True

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_manual_review(self):
        """Confidence < 0.6 sets needs_manual_review=True."""
        mock_response_text = json.dumps({
            "zone_id": None,
            "need_category": "other",
            "urgency": 2,
            "population_est": None,
            "confidence": 0.45,
            "reasoning": "Unclear report."
        })
        mock_response = MagicMock()
        mock_response.text = mock_response_text
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                nlp_classifier._classification_cache.clear()
                result = await classify_report("Unclear message from field")

        assert result["confidence"] == pytest.approx(0.45)
        assert result["needs_manual_review"] is True

    @pytest.mark.asyncio
    async def test_invalid_category_defaults_to_other(self):
        """Unknown need_category from Gemini defaults to 'other'."""
        mock_response_text = json.dumps({
            "zone_id": "Zone 1",
            "need_category": "alien_invasion",  # Not a valid category
            "urgency": 3,
            "population_est": None,
            "confidence": 0.85,
            "reasoning": "Test."
        })
        mock_response = MagicMock()
        mock_response.text = mock_response_text
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                nlp_classifier._classification_cache.clear()
                result = await classify_report("Some text")

        assert result["need_category"] == "other"

    @pytest.mark.asyncio
    async def test_markdown_wrapped_json_parsed_correctly(self):
        """JSON wrapped in markdown code fences is stripped and parsed."""
        mock_response = MagicMock()
        mock_response.text = "```json\n{\"zone_id\": \"Zone 2\", \"need_category\": \"shelter\", \"urgency\": 4, \"population_est\": 30, \"confidence\": 0.88, \"reasoning\": \"Shelter emergency.\"}\n```"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                nlp_classifier._classification_cache.clear()
                result = await classify_report("Families displaced in Zone 2")

        assert result["need_category"] == "shelter"
        assert result["confidence"] == pytest.approx(0.88)


class TestCacheBehavior:
    @pytest.mark.asyncio
    async def test_same_text_returns_cached_without_api_call(self):
        """Same raw_text within TTL returns cached result without calling Gemini."""
        raw_text = "test_cache_text_unique_12345"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(
            text=json.dumps({
                "zone_id": "Zone 1", "need_category": "nutrition",
                "urgency": 3, "population_est": None,
                "confidence": 0.88, "reasoning": "Test."
            })
        )

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                nlp_classifier._classification_cache.clear()
                # First call: hits API
                r1 = await classify_report(raw_text)
                # Second call: should use cache
                r2 = await classify_report(raw_text)

        assert r1 == r2
        assert mock_model.generate_content.call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_expired_cache_calls_api_again(self):
        """Expired cache entry triggers a new API call."""
        raw_text = "expired_cache_unique_text_xyz"
        nlp_classifier._classification_cache.clear()

        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(
            text=json.dumps({
                "zone_id": None, "need_category": "other",
                "urgency": 2, "population_est": None,
                "confidence": 0.75, "reasoning": "Test."
            })
        )

        cache_key = raw_text.strip().lower()
        # Manually insert expired cache entry
        expired_result = {"zone_id": None, "need_category": "other", "urgency": 2,
                          "population_est": None, "confidence": 0.75, "reasoning": "cached",
                          "needs_manual_review": False}
        nlp_classifier._classification_cache[cache_key] = (expired_result, time.time() - 1)  # expired

        with patch("app.services.nlp_classifier._get_gemini_client", return_value=mock_model):
            with patch("app.services.nlp_classifier._get_top_few_shot_examples", return_value=[]):
                result = await classify_report(raw_text)

        # Should have called API again
        assert mock_model.generate_content.call_count == 1


class TestFewShotSimilarity:
    def test_cosine_similarity_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_top_few_shot_retrieves_n_examples(self):
        """get_top_few_shot_examples returns at most n examples."""
        # Mock the load function to return 10 examples
        mock_examples = [{"text": f"text {i}", "category": "nutrition", "embedding": [float(i), 0.0]}
                         for i in range(10)]
        mock_query_emb = [1.0, 0.0]

        with patch("app.services.nlp_classifier._load_few_shot_examples", return_value=mock_examples):
            with patch("app.services.nlp_classifier._get_text_embedding", return_value=mock_query_emb):
                result = _get_top_few_shot_examples("some text", n=5)

        assert len(result) == 5
