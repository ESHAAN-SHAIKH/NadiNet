"""
OCR Service — Google Cloud Vision primary, pytesseract fallback.
"""
import io
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)


async def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Primary: Google Cloud Vision API
    Fallback: pytesseract
    Returns extracted text string.
    """
    # Try Google Cloud Vision first
    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)
        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")
        texts = response.text_annotations
        if texts:
            return texts[0].description.strip()
        return ""
    except ImportError:
        logger.warning("google-cloud-vision not available, using pytesseract")
    except Exception as e:
        logger.warning(f"Google Vision API failed: {e}, falling back to pytesseract")

    # Fallback: pytesseract
    try:
        import pytesseract
        from PIL import Image
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang="eng+hin")
        return text.strip()
    except Exception as e:
        logger.error(f"pytesseract fallback also failed: {e}")
        return ""
