# Perfume Fit AI Recommender

A simple Django app that recommends real products from the public Shopify catalog at `https://perfume.fit` and returns JSON responses that always include the Perfume Fit storefront link.

## Quick start

1. Create a virtual environment and install dependencies:
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
   - `pip install -r requirements.txt`
2. Run migrations:
   - `python manage.py migrate`
3. Start the server:
   - `python manage.py runserver`

## Endpoints

- `GET /` renders a simple demo UI.
- `GET /api/recommend/` accepts query string filters.
- `POST /api/recommend/` accepts JSON like:

```json
{
  "prompt": "I want something clean for the office",
  "notes": "bergamot, musk",
  "avoid_notes": "oud",
  "mood": "fresh",
  "occasion": "office",
  "season": "spring"
}
```

Example response fields:

- `store_url`: `https://perfume.fit`
- `profile`: interpreted shopper preferences plus catalog source and catalog size
- `recommendations`: top three matches with score, confidence, explanation, `product_url`, and `shop_url`

## Notes

- The recommender fetches live public Shopify products from `https://perfume.fit/products.json`.
- Product data is cached in memory for 30 minutes to keep the API responsive.
- Non-perfume items like deodorants and body care are filtered out before ranking.
