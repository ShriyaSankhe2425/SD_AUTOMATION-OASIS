"""Gemini vision extraction: prompt, API call, retry, and JSON parsing.

Uses the ``google-genai`` SDK with **native structured outputs**: the schema
is enforced server-side via ``response_schema`` (a Pydantic model whose
field descriptions steer the model), so the prompt itself focuses on *how
to read the document* — a multilingual label glossary for POs with no fixed
template — instead of duplicating the JSON shape (which Google's docs warn
degrades quality).

Ambiguity is captured instead of forced: uncertain party names and
manufacturer readings go into ``*_candidates`` lists, and customer/account
codes printed near a party block go into ``customer_number`` (never into
the company name). Temperature is pinned to 0; invalid JSON triggers one
clarifying retry; transient HTTP errors (429/500/503) are retried with
exponential backoff.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import errors, types
from PIL import Image
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Gemini token counts for one or more `generate_content` calls."""

    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            self.prompt_tokens + other.prompt_tokens,
            self.output_tokens + other.output_tokens,
            self.total_tokens + other.total_tokens,
        )


def _usage_from_response(response) -> TokenUsage:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return TokenUsage()
    return TokenUsage(
        prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
        output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
        total_tokens=getattr(meta, "total_token_count", 0) or 0,
    )


# --- Response schema (enforced by the API via response_schema) -------------

class ExtractedParty(BaseModel):
    """One party block (sold-to or ship-to) as printed on the document."""

    company_name: Optional[str] = Field(
        None,
        description=(
            "The organization's name ONLY, exactly as printed (original "
            "language, do not translate). Never a street address, city, "
            "postal code, phone number, person's name, or numeric code."
        ),
    )
    name_candidates: list[str] = Field(
        default_factory=list,
        description=(
            "Other plausible company names for this party if the document is "
            "ambiguous (e.g. a parent company, a name in another language or "
            "script for the same party, or a second unlabeled candidate). "
            "Empty if the main company_name is unambiguous."
        ),
    )
    customer_number: Optional[str] = Field(
        None,
        description=(
            "Customer/account/partner code printed near this party block "
            "(labels like Customer No., Account, 取引先コード, 得意先コード, "
            "客先コード). Digits/code exactly as printed. Never place this "
            "in company_name."
        ),
    )
    label_text: Optional[str] = Field(
        None,
        description=(
            "The literal label on the document that identifies this party, "
            "exactly as printed (e.g. 納入先, Ship To, 発注元, Bill To)."
        ),
    )
    address: Optional[str] = Field(
        None, description="Street/building address lines as printed, excluding city/postal code if separable."
    )
    city: Optional[str] = Field(None, description="City as printed.")
    country: Optional[str] = Field(None, description="Country as printed, if shown.")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code as printed.")


class ExtractedLineItem(BaseModel):
    material_description: Optional[str] = Field(
        None, description="Product/material description exactly as printed (original language)."
    )
    material_code: Optional[str] = Field(
        None, description="Item/material/part number as printed, if shown."
    )
    quantity: Optional[str] = Field(None, description="Quantity as printed, including unit if shown.")
    unit_price: Optional[str] = Field(None, description="Unit price as printed, original format.")
    total: Optional[str] = Field(None, description="Line amount as printed, original format.")


class ExtractedPO(BaseModel):
    po_number: Optional[str] = Field(None, description="The purchase order number as printed.")
    issue_date: Optional[str] = Field(
        None, description="Issue/order date exactly as printed. Do not reformat."
    )
    sold_to: Optional[ExtractedParty] = Field(
        None,
        description=(
            "The buyer: the party PLACING the order and paying. Often the "
            "document issuer (letterhead of the order form)."
        ),
    )
    ship_to: Optional[ExtractedParty] = Field(
        None, description="The delivery destination party, if stated."
    )
    manufacturer_name: Optional[str] = Field(
        None,
        description=(
            "Always translate to English and return Translated value of manufacturer/supplier name. "
            "The supplier/manufacturer: the party RECEIVING the order and "
            "supplying the goods. Often the addressee (e.g. a company name "
            "followed by 御中), or named in a supplier/vendor block, "
            "letterhead, or logo."
        ),
    )
    manufacturer_candidates: list[str] = Field(
        default_factory=list,
        description=(
            "Other plausible manufacturer/supplier names if uncertain "
            "(e.g. both a logo name and an addressed name exist). Empty if "
            "manufacturer_name is unambiguous."
        ),
    )
    shipping_details: Optional[str] = Field(
        None, description="Shipping/delivery terms or instructions as printed."
    )
    line_items: list[ExtractedLineItem] = Field(default_factory=list)


# --- Prompts ----------------------------------------------------------------

SYSTEM_PROMPT = """You are a structured data extraction assistant for purchase order documents.
You extract values exactly as they appear on the document. You never invent,
infer, or hallucinate data. Field labels on the document may be in any
language — translate labels internally to understand the layout, but output
every VALUE verbatim in its original language and formatting. If a field is
genuinely absent, return null for it."""

USER_PROMPT = """Extract the purchase order data from this document image.

How to read the document — layouts vary, so locate fields by their labels
(translating labels internally as needed; the document may be Japanese,
Chinese, English, French, or mixed):

- PO number: PO No., Order No., 注文番号, 発注番号, 注文書No, 注文書番号
- Issue date: Date, 発行日, 注文日, 発注日, 作成日
- Sold-to / buyer (places the order and pays): Bill To, Sold To, Buyer,
  Purchaser, Invoice To, 発注元, 発注者, 注文者, 請求先, 買主 — on many POs this
  is the issuing company shown in the letterhead.
- Ship-to / delivery destination: Ship To, Deliver To, Delivery Address,
  納入先, 納品先, 送り先, お届け先, 届け先, 送付先
- Manufacturer / supplier (receives the order, supplies the goods): Supplier,
  Vendor, Manufacturer, 仕入先, 発注先, メーカー, 製造元 — often the addressee:
  a company name followed by 御中 is the party the PO is addressed TO.
- Line items table: Description/Item/品名/品目/商品名, Part No./品番/型番,
  Qty/数量, Unit Price/単価, Amount/金額

Strict rules:
- company_name fields contain ONLY an organization name — never a street
  address, city, district, postal code, phone number, or code number.
- Customer/account codes near a party block (取引先コード, Customer No., ...)
  belong in customer_number, not in company_name.
- Copy every value exactly as printed: original language, original date and
  number formatting. Never translate values.
- If you are uncertain between multiple readings for a party name or the
  manufacturer, put the most likely value in the main field and the other
  readings in the corresponding candidates list.
- Record the literal label you used to identify each party in label_text.
- If a field is genuinely not on the document, return null."""

CLARIFY_PROMPT = """Your previous response was not valid JSON. Return ONLY a single valid JSON
object matching the requested schema, with no markdown fences and no text
outside the JSON object."""

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class ExtractionError(Exception):
    """Raised when a page cannot be extracted after all retries."""


def get_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def extract_page(client: genai.Client, image: Image.Image, model_id: str) -> tuple[dict, TokenUsage]:
    """Extract PO data from one page image. Raises ExtractionError on failure.

    Returns the parsed JSON plus the total token usage for this page (summed
    across the initial call and, if triggered, the clarifying retry).
    """
    response_text, usage = _generate(client, model_id, [USER_PROMPT, image])
    try:
        return _parse_json(response_text), usage
    except json.JSONDecodeError:
        logger.warning("Model response was not valid JSON; retrying with clarifying prompt")

    retry_text, retry_usage = _generate(client, model_id, [USER_PROMPT, image, CLARIFY_PROMPT])
    usage = usage + retry_usage
    try:
        return _parse_json(retry_text), usage
    except json.JSONDecodeError as exc:
        logger.error("Retry also returned invalid JSON. Raw response: %r", retry_text[:2000])
        raise ExtractionError(f"parse_error: response is not valid JSON ({exc})") from exc


def _generate(client: genai.Client, model_id: str, contents: list) -> tuple[str, TokenUsage]:
    """Call the model with exponential backoff on transient HTTP errors."""
    generation_config = types.GenerateContentConfig(
        temperature=0,
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=ExtractedPO,
        http_options=types.HttpOptions(timeout=config.API_TIMEOUT_SECONDS * 1000),
    )
    last_error: Exception | None = None
    for attempt in range(config.MAX_API_RETRIES):
        try:
            response = client.models.generate_content(
                model=model_id, contents=contents, config=generation_config
            )
            usage = _usage_from_response(response)
            logger.info(
                "Gemini token usage: %d prompt + %d output = %d total (model=%s)",
                usage.prompt_tokens, usage.output_tokens, usage.total_tokens, model_id,
            )
            return response.text or "", usage
        except errors.APIError as exc:
            last_error = exc
            status = getattr(exc, "code", None)
            if status in config.RETRYABLE_STATUS_CODES and attempt < config.MAX_API_RETRIES - 1:
                delay = config.RETRY_BACKOFF_SECONDS[min(attempt, len(config.RETRY_BACKOFF_SECONDS) - 1)]
                logger.warning("Gemini API error %s; retrying in %ds (attempt %d/%d)",
                               status, delay, attempt + 1, config.MAX_API_RETRIES)
                time.sleep(delay)
            else:
                break
    raise ExtractionError(f"Gemini API call failed after retries: {last_error}") from last_error


def _parse_json(text: str) -> dict:
    """Strip markdown fences (defensive; structured output should not emit
    them) and parse the response as a JSON object."""
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("response is not a JSON object", cleaned, 0)
    return parsed
