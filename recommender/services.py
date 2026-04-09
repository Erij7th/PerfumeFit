from __future__ import annotations

from .shopify import STORE_URL, StoreProduct, get_shopify_catalog, tokenize

KEYWORD_HINTS = {
    "beach": {"marine", "sea salt", "citrus", "fresh", "vacation"},
    "bold": {"oud", "amber", "leather", "spice", "night"},
    "clean": {"fresh", "musk", "citrus", "airy", "bright"},
    "cozy": {"amber", "vanilla", "cashmere", "warm", "tonka"},
    "date": {"romantic", "rose", "jasmine", "sensual", "amber"},
    "daily": {"clean", "fresh", "easy", "refined", "subtle"},
    "elegant": {"rose", "jasmine", "musk", "refined"},
    "fall": {"amber", "woods", "spice", "vanilla"},
    "feminine": {"women", "rose", "jasmine", "floral"},
    "fresh": {"citrus", "marine", "mint", "bergamot", "clean"},
    "luxury": {"oud", "saffron", "leather", "amber"},
    "masculine": {"men", "woods", "spice", "vetiver"},
    "men": {"men", "masculine", "woods", "spice"},
    "minimal": {"clean", "fresh", "musk", "citrus"},
    "night": {"amber", "oud", "leather", "sensual"},
    "office": {"clean", "fresh", "refined", "subtle", "daily"},
    "playful": {"pear", "citrus", "lychee", "bright"},
    "romantic": {"rose", "jasmine", "musk", "vanilla"},
    "spring": {"floral", "fresh", "bergamot", "pear"},
    "summer": {"citrus", "marine", "mint", "fresh"},
    "unisex": {"unisex", "clean", "woods", "musk"},
    "warm": {"amber", "vanilla", "woods", "spice"},
    "winter": {"amber", "oud", "vanilla", "saffron"},
    "women": {"women", "feminine", "rose", "floral"},
    "woody": {"woods", "cedar", "vetiver", "sandalwood"},
}


def recommend_perfumes(payload: dict, *, catalog: tuple[StoreProduct, ...] | list[StoreProduct] | None = None) -> dict:
    preferred_notes = normalize_list(
        payload.get("notes") or payload.get("preferred_notes") or payload.get("preferredNotes")
    )
    avoided_notes = normalize_list(
        payload.get("avoid_notes") or payload.get("disliked_notes") or payload.get("avoidNotes")
    )
    mood = normalize_list(payload.get("mood") or payload.get("vibe"))
    occasion = normalize_list(payload.get("occasion"))
    season = normalize_list(payload.get("season"))
    prompt = str(payload.get("prompt", "")).strip()

    desired_keywords = expand_keywords(preferred_notes + mood + occasion + season, prompt)
    disliked_keywords = expand_keywords(avoided_notes, " ".join(avoided_notes))

    if catalog is None:
        live_catalog, catalog_source = get_shopify_catalog()
    else:
        live_catalog = tuple(catalog)
        catalog_source = "provided_catalog"

    profile = {
        "prompt": prompt,
        "preferred_notes": preferred_notes,
        "avoid_notes": avoided_notes,
        "mood": mood,
        "occasion": occasion,
        "season": season,
        "interpreted_keywords": sorted(desired_keywords),
        "catalog_source": catalog_source,
        "catalog_size": len(live_catalog),
        "store_url": STORE_URL,
    }

    if not live_catalog:
        return {
            "profile": profile,
            "recommendations": [],
            "message": "The live Perfume Fit catalog is temporarily unavailable. Try again shortly.",
            "errors": ["catalog_unavailable"],
            "status": 503,
        }

    recommendations = [
        score_product(
            product=product,
            desired_keywords=desired_keywords,
            disliked_keywords=disliked_keywords,
        )
        for product in live_catalog
    ]
    recommendations.sort(
        key=lambda item: (item["match_score"], item["available"], item["match_confidence"]),
        reverse=True,
    )

    return {
        "profile": profile,
        "recommendations": recommendations[:3],
        "message": "Here are your best matches from the live Perfume Fit catalog.",
        "errors": [],
        "status": 200,
    }


def normalize_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        pieces = value
    else:
        pieces = str(value).split(",")
    return [item.strip().lower() for item in pieces if item and item.strip()]


def expand_keywords(values: list[str], prompt: str) -> set[str]:
    keywords = set(values)
    expanded_keywords = set()
    lowered_prompt = prompt.lower()
    keywords.update(tokenize(lowered_prompt))

    for token in list(keywords):
        expanded_keywords.add(token.lower())
        expanded_keywords.update(tokenize(token))
        for hint in KEYWORD_HINTS.get(token, set()):
            expanded_keywords.add(hint.lower())
            expanded_keywords.update(tokenize(hint))

    if "date night" in lowered_prompt:
        expanded_keywords.update({"date night", "romantic", "sensual", "amber", "rose"})
    if "night out" in lowered_prompt:
        expanded_keywords.update({"night out", "bold", "amber", "oud", "spice"})
    if "every day" in lowered_prompt or "everyday" in lowered_prompt:
        expanded_keywords.update({"daily", "clean", "fresh"})

    final_keywords = set()
    for keyword in expanded_keywords:
        final_keywords.add(keyword.lower())
        final_keywords.update(tokenize(keyword))
    return {keyword.lower() for keyword in final_keywords if keyword}


def score_product(*, product: StoreProduct, desired_keywords: set[str], disliked_keywords: set[str]) -> dict:
    title_matches = overlap(desired_keywords, product.title_terms)
    note_matches = overlap(desired_keywords, product.note_terms)
    tag_matches = overlap(desired_keywords, product.tag_terms)
    description_matches = overlap(desired_keywords, product.description_terms)
    vendor_matches = overlap(desired_keywords, product.vendor_terms)
    disliked_matches = overlap(
        disliked_keywords,
        product.title_terms | product.note_terms | product.tag_terms | product.description_terms,
    )

    match_score = (
        len(note_matches) * 5
        + len(title_matches) * 4
        + len(tag_matches) * 3
        + len(description_matches) * 2
        + len(vendor_matches)
        + (2 if product.available else 0)
    ) - (len(disliked_matches) * 6)

    if match_score <= 0:
        match_score = 1

    confidence = min(0.52 + (match_score * 0.04), 0.98)

    return {
        "product_id": product.product_id,
        "name": product.title,
        "brand": product.vendor or product.product_type,
        "description": product.description,
        "notes": list(product.notes),
        "tags": list(product.tags),
        "price": product.price,
        "available": product.available,
        "image_url": product.image_url,
        "product_url": product.product_url,
        "match_score": match_score,
        "match_confidence": round(confidence, 2),
        "why_it_matches": build_reason(
            product=product,
            note_matches=note_matches,
            title_matches=title_matches,
            tag_matches=tag_matches,
            description_matches=description_matches,
        ),
        "shop_url": STORE_URL,
    }


def overlap(keywords: set[str], options: frozenset[str] | set[str]) -> list[str]:
    return sorted(set(options).intersection(keywords))


def build_reason(
    *,
    product: StoreProduct,
    note_matches: list[str],
    title_matches: list[str],
    tag_matches: list[str],
    description_matches: list[str],
) -> str:
    reasons = []
    if note_matches:
        reasons.append(f"it surfaces notes like {', '.join(note_matches[:3])}")
    if title_matches:
        reasons.append(f"its title lines up with {', '.join(title_matches[:3])}")
    if tag_matches:
        reasons.append(f"its store tags reinforce {', '.join(tag_matches[:2])}")
    if description_matches:
        reasons.append(f"its description reflects {', '.join(description_matches[:2])}")

    if not reasons:
        return f"{product.title} is a strong general match from the live Perfume Fit catalog."

    return f"{product.title} matches because {', '.join(reasons)}."
