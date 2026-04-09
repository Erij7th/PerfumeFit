from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from .services import STORE_URL, recommend_perfumes
from .shopify import normalize_shopify_product


def build_product(
    *,
    product_id: int,
    title: str,
    body_html: str,
    tags: list[str] | None = None,
    vendor: str = "Perfume Brand",
    handle: str = "sample-product",
    price: str = "89.00",
):
    return {
        "id": product_id,
        "title": title,
        "handle": handle,
        "body_html": body_html,
        "vendor": vendor,
        "product_type": vendor,
        "tags": tags or [],
        "variants": [
            {
                "id": product_id * 10,
                "product_id": product_id,
                "title": "Default Title",
                "option1": "Default Title",
                "option2": None,
                "option3": None,
                "available": True,
                "price": price,
                "compare_at_price": None,
                "created_at": "2026-01-01T00:00:00-05:00",
                "updated_at": "2026-01-01T00:00:00-05:00",
                "taxable": True,
                "requires_shipping": True,
                "sku": "",
                "grams": 0,
                "position": 1,
                "featured_image": None,
            }
        ],
        "images": [
            {
                "id": product_id * 100,
                "product_id": product_id,
                "position": 1,
                "created_at": "2026-01-01T00:00:00-05:00",
                "updated_at": "2026-01-01T00:00:00-05:00",
                "src": f"https://cdn.perfume.fit/{handle}.jpg",
                "variant_ids": [],
                "width": 1200,
                "height": 1200,
            }
        ],
    }


class PerfumeRecommendationServiceTests(TestCase):
    def test_recommendation_prefers_live_matching_notes(self):
        warm_product = normalize_shopify_product(
            build_product(
                product_id=1,
                title="Velvet Amber Eau De Parfum Spray",
                handle="velvet-amber",
                vendor="Maison Warm",
                body_html="<p>A cozy vanilla amber perfume with tonka and sandalwood.</p>",
                tags=["fragrance for women", "amber"],
            )
        )
        fresh_product = normalize_shopify_product(
            build_product(
                product_id=2,
                title="Sea Citrus Eau De Toilette Spray",
                handle="sea-citrus",
                vendor="Maison Fresh",
                body_html="<p>A bright grapefruit and sea salt scent for sunny weather.</p>",
                tags=["unisex fragrance", "fresh"],
            )
        )

        results = recommend_perfumes(
            {
                "notes": "vanilla, amber",
                "mood": "cozy",
                "season": "winter",
            },
            catalog=[warm_product, fresh_product],
        )

        self.assertEqual(results["recommendations"][0]["name"], "Velvet Amber Eau De Parfum Spray")
        self.assertEqual(results["profile"]["catalog_source"], "provided_catalog")
        self.assertEqual(results["profile"]["store_url"], STORE_URL)

    def test_non_perfume_products_are_filtered_out(self):
        deodorant_product = normalize_shopify_product(
            build_product(
                product_id=3,
                title="Classic Fresh Deodorant Stick",
                handle="classic-fresh-deodorant",
                body_html="<p>Daily deodorant care with fresh citrus.</p>",
                tags=["fragrance for men"],
            )
        )

        self.assertIsNone(deodorant_product)


class PerfumeRecommendationApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_loads(self):
        response = self.client.get(reverse("recommender:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find Your Signature Scent")

    def test_fragrance_discovery_page_loads(self):
        response = self.client.get(reverse("recommender:fragrance_discovery"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find Your Signature Scent")

    def test_api_returns_store_link(self):
        office_product = normalize_shopify_product(
            build_product(
                product_id=4,
                title="Clean Citrus Eau De Parfum Spray",
                handle="clean-citrus",
                vendor="Studio Citrus",
                body_html="<p>A bright bergamot musk fragrance that feels clean and office-ready.</p>",
                tags=["fragrance for women", "fresh"],
            )
        )

        with patch("recommender.services.get_shopify_catalog", return_value=((office_product,), "shopify_live")):
            response = self.client.post(
                reverse("recommender:recommend"),
                data='{"prompt": "I want something clean for the office", "season": "spring"}',
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["store_url"], STORE_URL)
        self.assertTrue(data["recommendations"])
        self.assertEqual(data["recommendations"][0]["shop_url"], STORE_URL)
        self.assertEqual(data["recommendations"][0]["product_url"], f"{STORE_URL}/products/clean-citrus")

    def test_invalid_json_returns_helpful_error(self):
        response = self.client.post(
            reverse("recommender:recommend"),
            data="{not-json}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["store_url"], STORE_URL)

    def test_api_returns_503_when_catalog_is_unavailable(self):
        with patch("recommender.services.get_shopify_catalog", return_value=((), "unavailable")):
            response = self.client.post(
                reverse("recommender:recommend"),
                data='{"prompt": "something warm"}',
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["store_url"], STORE_URL)
