import os
from dotenv import load_dotenv
load_dotenv()
import json
import base64
import logging
import anthropic
import subprocess
import tempfile

logger = logging.getLogger(__name__)

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client

SYSTEM_PROMPT = """You are a price tracking assistant for a market explorer in Istanbul, Turkey.
Extract product information from user input (text, image descriptions, or voice transcripts).

Always respond with a valid JSON object with these fields:
{
  "product": "product name (be specific, e.g. 'Nike Air Max 270' not just 'shoes')",
  "price": "numeric price only, no currency symbol (e.g. '850' or '1200.50')",
  "currency": "currency code: TL, USD, EUR, GBP (default: TL)",
  "store": "store or market name",
  "location": "neighborhood or area in Istanbul (e.g. Taksim, Kapalıçarşı, Kadıköy)",
  "category": "one of: Electronics, Clothing, Shoes, Food, Cosmetics, Jewelry, Accessories, Textiles, Furniture, Other",
  "notes": "any other relevant notes (optional)"
}

If you cannot determine a field, use null. Product name is required.
For Turkish Lira, use 'TL'. Prices in Turkey are often written as '850 TL' or '1.200 TL' (dot as thousands separator).
Common Istanbul markets: Kapalıçarşı (Grand Bazaar), Mısır Çarşısı (Spice Bazaar), Mahmutpaşa, Kadıköy.

Respond ONLY with the JSON object, no other text."""


async def parse_product_entry(raw_input: str) -> dict:
    """Parse a product entry from text, image path, or voice path."""
    try:
        messages_content = []

        # Handle image
        if raw_input.startswith("[IMAGE:"):
            end = raw_input.index("]")
            image_path = raw_input[7:end]
            caption = raw_input[end + 1:].strip()

            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            messages_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_data
                }
            })

            user_text = f"Extract product and price information from this price tag image."
            if caption:
                user_text += f" Additional context: {caption}"
            messages_content.append({"type": "text", "text": user_text})

        # Handle voice (transcribe with whisper via ffmpeg + openai, or fallback)
        elif raw_input.startswith("[VOICE:"):
            end = raw_input.index("]")
            voice_path = raw_input[7:end]

            transcript = await _transcribe_voice(voice_path)
            if not transcript:
                return {"product": None, "error": "Could not transcribe voice"}

            messages_content.append({
                "type": "text",
                "text": f"Extract product and price info from this voice message transcript: '{transcript}'"
            })

        # Handle plain text
        else:
            messages_content.append({
                "type": "text",
                "text": f"Extract product and price info from: '{raw_input}'"
            })

        response = _get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": messages_content}]
        )

        text = response.content[0].text.strip()

        # Clean up JSON if wrapped in code block
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return {"product": None, "error": "Parse error"}
    except Exception as e:
        logger.exception(f"AI parsing error: {e}")
        return {"product": None, "error": str(e)}


async def _transcribe_voice(voice_path: str) -> str:
    """
    Transcribe voice using OpenAI Whisper API (if key available),
    or fall back to asking Claude to handle it as audio description.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")

    if openai_key:
        try:
            import httpx

            # Convert OGG to MP3 for Whisper compatibility
            mp3_path = voice_path.replace(".ogg", ".mp3")
            subprocess.run(
                ["ffmpeg", "-i", voice_path, "-q:a", "0", "-map", "a", mp3_path, "-y"],
                capture_output=True, timeout=30
            )

            with open(mp3_path, "rb") as f:
                audio_data = f.read()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    data={"model": "whisper-1", "language": "tr"},
                    files={"file": ("audio.mp3", audio_data, "audio/mpeg")},
                    timeout=30
                )
                result = response.json()
                return result.get("text", "")
        except Exception as e:
            logger.warning(f"Whisper transcription failed: {e}")

    # Fallback: prompt user to type it out
    return None
