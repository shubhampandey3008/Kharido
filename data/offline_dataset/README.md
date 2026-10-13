# Offline Dataset

Fallback product data used when the Apify API token is absent or a scraper run fails.

## Structure

Each file is a JSON array of product objects matching the `Product` Pydantic model in `kharido/models.py`.

```
data/offline_dataset/
├── running_shoes.json   (10 products)
├── earbuds.json         (10 products)
└── backpacks.json       (10 products)
```

## Product Schema

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | string | Unique ID (e.g. `rs-001`) |
| `title` | string | Full product name |
| `brand` | string | Brand name |
| `price_inr` | float | Price in Indian Rupees |
| `rating` | float | Star rating (0–5) |
| `rating_count` | int | Number of reviews |
| `key_specs` | dict | Flat key-value spec sheet |
| `image_url` | string | Product image (empty for offline data) |
| `product_url` | string | Product page URL |
| `source` | string | Always `"offline_dataset"` |
| `raw_reviews` | list[str] | 3–5 review snippets |

## Adding a New Category

1. Create `data/offline_dataset/{category_slug}.json` with the schema above.
2. Add at least 10 products with varied price points, ratings, and specs.
3. Include 3–5 representative review snippets per product (mix of positive and negative).
4. The `ScraperClient._load_offline_dataset(category)` method will pick it up automatically.

## Category naming

Use the same snake_case slug that `query_understanding_node` produces:
- `running_shoes`
- `earbuds`
- `backpacks`
- `smartphones` (future)
- `trekking_poles` (future)
