from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STORE_URL = "https://perfume.fit"
SHOPIFY_PRODUCTS_URL = f"{STORE_URL}/products.json"
SHOPIFY_PAGE_SIZE = 250
SHOPIFY_MAX_PRODUCTS = 1000
SHOPIFY_CACHE_TTL_SECONDS = 1800
SHOPIFY_TIMEOUT_SECONDS = 15

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MULTISPACE_PATTERN = re.compile(r"\s+")

STOPWORDS = {
    "a", "an", "and", "any", "be", "for", "i", "in", "is", "it", "like",
    "me", "my", "of", "something", "that", "the", "this", "to", "want", "with",
}

NOTE_KEYWORDS = (
    "amber", "apple", "basil", "bergamot", "blood orange", "cardamom", "cashmere",
    "cedar", "cinnamon", "citrus", "coconut", "coffee", "freesia", "grapefruit",
    "green tea", "jasmine", "lavender", "leather", "lemon", "lychee", "marine",
    "mint", "musk", "neroli", "orange blossom", "oud", "patchouli", "peach",
    "pear", "peony", "pepper", "pineapple", "rose", "saffron", "salt",
    "sandalwood", "sea salt", "spice", "tonka", "vanilla", "vetiver", "violet",
    "white musk", "wood", "woods",
)

PREFERRED_PRODUCT_TERMS = (
    "cologne",
    "eau de cologne",
    "eau de parfum",
    "eau de toilette",
    "extract",
    "fragrance spray",
    "parfum",
    "perfume",
    "spray",
)

EXCLUDED_PRODUCT_TERMS = (
    "after shave",
    "aftershave",
    "body lotion",
    "body wash",
    "candle",
    "candles",
    "deodorant",
    "gift set",
    "hair mist",
    "sample vial",
    "shampoo",
    "shower gel",
    "soap",
)

_catalog_cache: dict[str, object] = {"fetched_at": 0.0, "products": ()}
_catalog_cache_lock = threading.Lock()


@dataclass(frozen=True)
class StoreProduct:
    product_id: int
    title: str
    handle: str
    description: str
    vendor: str
    product_type: str
    tags: tuple[str, ...]
    notes: tuple[str, ...]
    available: bool
    price: str | None
    image_url: str | None
    product_url: str
    title_terms: frozenset[str]
    description_terms: frozenset[str]
    tag_terms: frozenset[str]
    vendor_terms: frozenset[str]
    note_terms: frozenset[str]


def get_shopify_catalog() -> tuple[tuple[StoreProduct, ...], str]:
    now = time.monotonic()
    with _catalog_cache_lock:
        cached_products = _catalog_cache["products"]
        fetched_at = _catalog_cache["fetched_at"]
        if cached_products and (now - fetched_at) < SHOPIFY_CACHE_TTL_SECONDS:
            return cached_products, "shopify_cache"

    try:
        products = fetch_shopify_catalog()
    except (HTTPError, URLError, TimeoutError, ValueError):
        with _catalog_cache_lock:
            cached_products = _catalog_cache["products"]
        if cached_products:
            return cached_products, "shopify_stale_cache"
        return (), "unavailable"

    with _catalog_cache_lock:
        _catalog_cache["products"] = products
        _catalog_cache["fetched_at"] = now
    return products, "shopify_live"


def fetch_shopify_catalog() -> tuple[StoreProduct, ...]:
    products: list[StoreProduct] = []
    page = 1

    while len(products) < SHOPIFY_MAX_PRODUCTS:
        raw_products = fetch_shopify_page(page)
        if not raw_products:
            break

        for raw_product in raw_products:
            product = normalize_shopify_product(raw_product)
            if product is None:
                continue
            products.append(product)
            if len(products) >= SHOPIFY_MAX_PRODUCTS:
                break

        if len(raw_products) < SHOPIFY_PAGE_SIZE:
            break
        page += 1

    return tuple(products)


def fetch_shopify_page(page: int) -> list[dict]:
    request = Request(
        url=f"{SHOPIFY_PRODUCTS_URL}?{urlencode({'limit': SHOPIFY_PAGE_SIZE, 'page': page})}",
        headers={"User-Agent": "PerfumeFitRecommender/1.0"},
    )
    with urlopen(request, timeout=SHOPIFY_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    return payload.get("products", [])


def normalize_shopify_product(raw_product: dict) -> StoreProduct | None:
    title = clean_text(raw_product.get("title"))
    description = strip_html(raw_product.get("body_html"))
    vendor = clean_text(raw_product.get("vendor"))
    product_type = clean_text(raw_product.get("product_type"))
    handle = clean_text(raw_product.get("handle"))
    tags = normalize_tags(raw_product.get("tags"))

    if not handle or not is_perfume_product(title, description, tags):
        return None

    variants = raw_product.get("variants") or []
    images = raw_product.get("images") or []
    searchable_text = " ".join(filter(None, [title, description, vendor, product_type, " ".join(tags)]))
    notes = extract_notes(searchable_text)

    return StoreProduct(
        product_id=int(raw_product.get("id") or 0),
        title=title,
        handle=handle,
        description=description,
        vendor=vendor,
        product_type=product_type,
        tags=tags,
        notes=notes,
        available=any(bool(variant.get("available")) for variant in variants),
        price=format_price(variants),
        image_url=normalize_image_url(images[0].get("src")) if images else None,
        product_url=f"{STORE_URL}/products/{handle}",
        title_terms=frozenset(tokenize(title)),
        description_terms=frozenset(tokenize(description)),
        tag_terms=frozenset(tokenize(" ".join(tags))),
        vendor_terms=frozenset(tokenize(f"{vendor} {product_type}")),
        note_terms=frozenset(tokenize(" ".join(notes))),
    )


def normalize_tags(value) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = value
    return tuple(clean_text(part) for part in parts if clean_text(part))


def is_perfume_product(title: str, description: str, tags: tuple[str, ...]) -> bool:
    searchable = " ".join([title.lower(), description.lower(), " ".join(tags).lower()])
    if any(term in searchable for term in EXCLUDED_PRODUCT_TERMS):
        return False
    return any(term in searchable for term in PREFERRED_PRODUCT_TERMS)


def extract_notes(text: str) -> tuple[str, ...]:
    lowered_text = text.lower()
    return tuple(note for note in NOTE_KEYWORDS if note in lowered_text)[:6]


def strip_html(value) -> str:
    if not value:
        return ""
    cleaned = HTML_TAG_PATTERN.sub(" ", str(value))
    return clean_text(unescape(cleaned))


def clean_text(value) -> str:
    return MULTISPACE_PATTERN.sub(" ", str(value or "")).strip()


def tokenize(value: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(value.lower()) if token not in STOPWORDS]


def normalize_image_url(value) -> str | None:
    if not value:
        return None
    image_url = str(value)
    return f"https:{image_url}" if image_url.startswith("//") else image_url


def format_price(variants: list[dict]) -> str | None:
    prices = []
    for variant in variants:
        price = variant.get("price")
        if price in (None, ""):
            continue
        try:
            prices.append(Decimal(str(price)))
        except (InvalidOperation, ValueError):
            continue

    if not prices:
        return None
    return f"${min(prices):.2f}"
