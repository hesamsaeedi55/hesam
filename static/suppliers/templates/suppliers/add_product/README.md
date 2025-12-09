# Add Product Form - Refactored Structure

This directory contains the refactored add product form, broken down into organized, maintainable components.

## Directory Structure

```
add_product/
├── AddProductPage.html          # Main container file
├── components/                   # Form section components
│   ├── ProductInfoForm.html     # Basic product information
│   ├── CategoryTagsForm.html    # Category and tags selection
│   ├── PricingForm.html         # Price fields
│   ├── InventoryForm.html       # Stock and status
│   ├── VariantsForm.html        # Product variants management
│   ├── MediaUploadForm.html     # Image upload
│   ├── SpecificationsForm.html  # Technical specifications
│   ├── AttributesForm.html      # Category attributes
│   └── common/                  # Reusable form components
│       ├── FormInput.html       # Generic input field
│       ├── FormTextarea.html    # Generic textarea
│       ├── FormSwitch.html      # Generic toggle switch
│       └── FormFileUpload.html   # Generic file upload
├── services/                    # JavaScript services
│   └── productFormService.js    # Main form functionality
├── validation/                  # Validation logic
│   └── productValidation.js     # Form validation schemas
├── utils/                       # Utility functions
│   └── formUtils.js             # Helper functions
└── styles/                      # CSS styles
    ├── main.css                 # Main stylesheet
    ├── ProductInfoForm.css      # Component-specific styles
    ├── CategoryTagsForm.css     # Component-specific styles
    └── VariantsForm.css         # Component-specific styles
```

## Components Overview

### Form Components

1. **ProductInfoForm.html**
   - Product name
   - Brand information
   - Brand image upload
   - Product description

2. **CategoryTagsForm.html**
   - Category selection dropdown
   - Tags multi-select
   - Dynamic tag loading based on category

3. **PricingForm.html**
   - Price in Toman (required)
   - Price in USD (optional)
   - Number formatting

4. **InventoryForm.html**
   - Stock quantity
   - Active/inactive status toggle

5. **VariantsForm.html**
   - Variant attributes selection
   - Variant generation
   - Variant management table
   - Variant modal for editing

6. **MediaUploadForm.html**
   - Multiple image upload
   - Image preview and management
   - Image cropping functionality

7. **SpecificationsForm.html**
   - Dynamic key-value pairs
   - Add/remove specifications

8. **AttributesForm.html**
   - Category-specific attributes
   - Dynamic attribute loading

### Reusable Components

- **FormInput.html**: Generic input field with validation
- **FormTextarea.html**: Generic textarea with validation
- **FormSwitch.html**: Generic toggle switch
- **FormFileUpload.html**: Generic file upload with preview

## JavaScript Services

### productFormService.js
Main JavaScript functionality including:
- Form submission handling
- Variant management
- Attribute selection
- Form initialization

### formUtils.js
Utility functions for:
- Number formatting
- Form validation
- Data manipulation
- String utilities

### productValidation.js
Validation schemas and functions for:
- Field validation
- File upload validation
- Variant validation
- Form validation

## CSS Styles

### main.css
Core styles including:
- CSS variables for theming
- Base form styles
- Layout styles
- Responsive design

### Component-specific CSS
Individual CSS files for complex components:
- ProductInfoForm.css
- CategoryTagsForm.css
- VariantsForm.css

## Usage

### Including Components
```html
{% include 'suppliers/add_product/components/ProductInfoForm.html' %}
```

### Loading JavaScript
```html
<script src="{% static 'suppliers/templates/suppliers/add_product/services/productFormService.js' %}"></script>
```

### Loading Styles
```html
<link rel="stylesheet" href="{% static 'suppliers/templates/suppliers/add_product/styles/main.css' %}">
```

## Benefits of Refactoring

1. **Maintainability**: Each component is focused on a single responsibility
2. **Reusability**: Components can be reused in other forms
3. **Testability**: Individual components can be tested separately
4. **Readability**: Code is organized and easy to understand
5. **Scalability**: Easy to add new components or modify existing ones
6. **Performance**: Better code splitting and loading

## Migration Notes

- The original `add_product.html` file has been replaced with `AddProductPage.html`
- All functionality has been preserved
- External dependencies remain the same
- Django template context variables are still available in components

## Future Enhancements

1. Add TypeScript support for better type safety
2. Implement component testing
3. Add more reusable form components
4. Implement form state management
5. Add accessibility improvements
6. Implement progressive enhancement
