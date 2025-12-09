# Special Offers API Pagination

## Overview
The Special Offers API now supports pagination for better performance and user experience when dealing with large numbers of products or offers.

## Supported Endpoints

### 1. Main Special Offers List
```
GET /shop/api/special-offers/
```

### 2. Individual Special Offer with Products
```
GET /shop/api/special-offers/{offer_id}/
```

## Pagination Parameters

| Parameter | Type | Default | Description | Limits |
|-----------|------|---------|-------------|---------|
| `page` | Integer | 1 | Page number to retrieve | Must be ≥ 1 |
| `per_page` | Integer | 20 | Number of items per page | 1-100 |

## Usage Examples

### Basic Pagination
```bash
# Get first page with 10 items per page
GET /shop/api/special-offers/?page=1&per_page=10

# Get second page with 20 items per page
GET /shop/api/special-offers/?page=2&per_page=20
```

### Pagination with Filters
```bash
# Get first page of men's products in special offer 14
GET /shop/api/special-offers/14/?gender=men&page=1&per_page=5

# Get second page of specific category products
GET /shop/api/special-offers/14/?category_id=5&page=2&per_page=10
```

### Combined Parameters
```bash
# Get first page of women's products from category 3, 15 items per page
GET /shop/api/special-offers/14/?category_id=3&gender=women&page=1&per_page=15
```

## Response Format

### Pagination Object
```json
{
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total_pages": 3,
    "total_products": 45,
    "has_next": true,
    "has_previous": false,
    "next_page": 2,
    "previous_page": null
  }
}
```

### Pagination Fields
- `current_page`: Current page number
- `per_page`: Items per page
- `total_pages`: Total number of pages
- `total_products`: Total number of products/offers
- `has_next`: Boolean indicating if next page exists
- `has_previous`: Boolean indicating if previous page exists
- `next_page`: Next page number (null if no next page)
- `previous_page`: Previous page number (null if no previous page)

## Error Handling

### Invalid Parameters
- Invalid `page` values (< 1) default to 1
- Invalid `per_page` values (< 1 or > 100) default to 20
- Non-numeric values default to defaults

### Response Status
- `200 OK`: Successful pagination
- `400 Bad Request`: Invalid filter parameters
- `404 Not Found`: Special offer not found

## Best Practices

1. **Start with page 1** for initial data load
2. **Use reasonable per_page values** (10-50 recommended)
3. **Check has_next/has_previous** before navigating
4. **Handle edge cases** when no more pages exist
5. **Cache pagination info** to avoid unnecessary API calls

## Implementation Notes

- Pagination works with all existing filters (category_id, gender)
- Products are ordered by `display_order` field
- Pagination is applied after filtering, so page counts reflect filtered results
- Maximum `per_page` is 100 to prevent performance issues
- Pagination metadata is included in all responses

