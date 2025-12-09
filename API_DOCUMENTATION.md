# Project API Documentation

## Category and Product APIs

### 1. Unified Product Loading
- **Endpoint**: `/shop/api/products/unified/`
- **Method**: GET
- **Description**: Comprehensive product loading endpoint supporting various filters
- **Parameters**:
  - `category_id`: Main category ID (required)
  - `subcategory_id`: Optional specific subcategory ID
  - `gender`: Optional gender filter
  - `search`: Optional search query
  - `page`: Page number (default: 1)
  - `limit`: Items per page (default: 20)
- **Response**:
  ```json
  {
    "products": [
      {
        "id": 123,
        "name": "محصول نمونه",
        "description": "توضیحات محصول",
        "price_toman": 100000,
        "price_usd": 2.5,
        "images": [
          {
            "url": "https://example.com/image.jpg",
            "is_primary": true
          }
        ],
        "attributes": [
          {
            "key": "برند",
            "value": "رولکس"
          }
        ]
      }
    ],
    "pagination": {
      "current_page": 1,
      "total_pages": 5,
      "total_items": 100
    }
  }
  ```

### 2. Category Products
- **Endpoint**: `/shop/api/category/{category_id}/products/`
- **Method**: GET
- **Description**: Load products for a specific category
- **Parameters**:
  - `page`: Page number (default: 1)
  - `limit`: Items per page (default: 20)
  - `include_subcategories`: Include products from subcategories (default: true)

### 3. Group Products
- **Endpoint**: `/shop/api/groups/{group_id}/products/`
- **Method**: GET
- **Description**: Load products for a specific category group
- **Parameters**:
  - `gender`: Filter by gender ('مردانه', 'زنانه', 'یونیسکس')
  - `subgroup`: Filter by subgroup ID
  - `page`: Page number (default: 1)
  - `limit`: Items per page (default: 20)

### 4. Simple Product List
- **Endpoint**: `/shop/api/products/`
- **Method**: GET
- **Description**: Basic product listing with pagination
- **Parameters**:
  - `page`: Page number (default: 1)
  - `per_page`: Items per page (default: 10)
- **Response Includes**:
  - Product details
  - Images
  - Attributes (from both new and legacy systems)

## Product Loading Strategies
- Supports multiple filtering methods
- Pagination for all product loading endpoints
- Flexible attribute handling
- Supports gender and category-based filtering

## Notes
- All product APIs support pagination
- Product attributes are returned from multiple sources
- Image URLs are absolute and can be directly used
- Timestamps are returned in Unix epoch format

## Wishlist APIs

### 5. Wishlist List and Create
- **Endpoint**: `/shop/api/v1/wishlist/`
- **Methods**: 
  - GET: List wishlists
  - POST: Create new wishlist

### 6. Wishlist Delete
- **Endpoint**: `/shop/api/v1/wishlist/{pk}/`
- **Method**: DELETE
- **Description**: Delete a specific wishlist item

### 7. Wishlist Toggle
- **Endpoint**: `/shop/api/v1/wishlist/toggle/`
- **Method**: POST
- **Description**: Toggle product in wishlist

### 8. Wishlist Status
- **Endpoint**: `/shop/api/v1/wishlist/status/`
- **Method**: GET
- **Description**: Check wishlist status for a product

## Gender-based Category APIs

### 9. Genders List
- **Endpoint**: `/shop/api/genders/`
- **Method**: GET
- **Description**: Retrieve list of genders

### 10. Categories by Gender
- **Endpoint**: `/shop/api/categories/by-gender/`
- **Method**: GET
- **Description**: Get categories filtered by gender

### 11. Parent Categories by Gender
- **Endpoint**: `/shop/api/categories/parents/by-gender/`
- **Method**: GET

### 12. Child Categories by Gender
- **Endpoint**: `/shop/api/categories/children/by-gender/`
- **Method**: GET

### 13. Child Categories by Parent and Gender
- **Endpoint**: `/shop/api/categories/parent/{parent_id}/children/by-gender/`
- **Method**: GET

### 14. Products by Gender Table
- **Endpoint**: `/shop/api/products/by-gender-table/`
- **Method**: GET

### 15. Gender Category Tree
- **Endpoint**: `/shop/api/gender-category-tree/`
- **Method**: GET

### 16. Gender Statistics
- **Endpoint**: `/shop/api/gender-statistics/`
- **Method**: GET

## Search and Advanced APIs

### 17. Simple Product Search
- **Endpoint**: `/shop/api/products/search/`
- **Method**: GET
- **Parameters**:
  - `q`: Search query

### 18. Advanced Product Search
- **Endpoint**: `/shop/api/products/advanced-search/`
- **Method**: GET
- **Description**: More comprehensive product search with multiple filters

## Additional Utility APIs

### 19. Category Attributes
- **Endpoint**: `/shop/api/category/{category_id}/attributes/`
- **Method**: GET
- **Description**: Retrieve attributes for a specific category

### 20. Categorization Key Management
- **Endpoint**: `/shop/api/category/{category_id}/categorization-key/`
- **Methods**: 
  - GET: Retrieve current categorization key
  - POST: Set categorization key

## Notes
- All APIs support pagination
- Most APIs return JSON responses
- Authentication may be required for some endpoints
- Error responses include descriptive messages

## Authentication
- Check individual endpoint requirements
- Some endpoints may require user authentication
- Token-based authentication is likely implemented
