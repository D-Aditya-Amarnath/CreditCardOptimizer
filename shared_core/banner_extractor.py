import os
import base64
import httpx
from io import BytesIO
from typing import List, Optional
from openai import OpenAI
from PIL import Image
from shared_core.models import BannerResult


class BannerExtractor:
    def __init__(self):
        self._llm_client = None

    @property
    def llm_client(self):
        if self._llm_client is None:
            base_url = os.getenv("LMSTUDIO_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:1234/v1"))
            api_key = os.getenv("LMSTUDIO_API_KEY", os.getenv("OLLAMA_API_KEY", "lm-studio"))
            self._llm_client = OpenAI(base_url=base_url, api_key=api_key)
        return self._llm_client

    def extract_text(self, content: bytes, content_type: str) -> str:
        if content_type.startswith("image/"):
            return self._extract_from_image(content)
        elif "html" in content_type or "text" in content_type:
            return self._extract_from_html(content)
        return ""

    def _extract_from_html(self, html_bytes: bytes) -> str:
        from bs4 import BeautifulSoup
        try:
            html = html_bytes.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return ""

    def _extract_from_image(self, image_bytes: bytes) -> str:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")

            if max(image.size) > 1024:
                image.thumbnail((1024, 1024), Image.LANCZOS)

            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            response = self.llm_client.chat.completions.create(
                model="moondream",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
                        },
                        {
                            "type": "text",
                            "text": "Extract ALL text visible in this image including: merchant names, cashback percentages, discount amounts, expiry dates, minimum spend requirements, card names, and terms. Return text verbatim."
                        }
                    ]
                }],
                max_tokens=500,
                temperature=0.0,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            return f"[Moondream extraction failed: {e}]"

    def fetch_and_extract(self, url: str) -> BannerResult:
        try:
            response = httpx.get(
                url,
                timeout=15,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; EmailBot/1.0)',
                    'Accept': 'text/html,image/*,*/*',
                },
                follow_redirects=True
            )

            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            content_type = content_type.split(';')[0].strip()

            text = self.extract_text(response.content, content_type)

            if content_type.startswith("image/"):
                method = "moondream"
            else:
                method = "beautifulsoup"

            return BannerResult(
                banner_url=url,
                content_type=content_type,
                extracted_text=text,
                extraction_method=method,
                extraction_status="success" if text else "empty",
            )

        except httpx.TimeoutException:
            return BannerResult(
                banner_url=url,
                extraction_status="failed",
                error_message="Request timed out"
            )
        except Exception as e:
            return BannerResult(
                banner_url=url,
                extraction_status="failed",
                error_message=str(e)
            )
