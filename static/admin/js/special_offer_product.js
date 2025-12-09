/**
 * Dynamic discount calculation for Special Offer Products
 * Updates discounted price field as user types in discount percentage
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Special Offer Product admin script loaded');
    
    // Find the relevant form fields
    const discountPercentageField = document.querySelector('#id_discount_percentage');
    const originalPriceField = document.querySelector('#id_original_price');
    const discountedPriceField = document.querySelector('#id_discounted_price');
    
    if (!discountPercentageField || !originalPriceField || !discountedPriceField) {
        console.log('Required fields not found');
        return;
    }
    
    // Make discounted price field truly readonly and styled
    discountedPriceField.readOnly = true;
    discountedPriceField.style.backgroundColor = '#f8f9fa';
    discountedPriceField.style.border = '1px solid #dee2e6';
    discountedPriceField.style.color = '#495057';
    discountedPriceField.style.fontWeight = 'bold';
    
    // Add Persian label for better clarity
    const discountedPriceLabel = document.querySelector('label[for="id_discounted_price"]');
    if (discountedPriceLabel) {
        discountedPriceLabel.innerHTML = 'قیمت با تخفیف (تومان) - محاسبه خودکار';
        discountedPriceLabel.style.color = '#28a745';
    }
    
    function calculateDiscountedPrice() {
        const originalPrice = parseFloat(originalPriceField.value) || 0;
        const discountPercentage = parseFloat(discountPercentageField.value) || 0;
        
        if (originalPrice > 0) {
            const discountedPrice = originalPrice * (1 - discountPercentage / 100);
            discountedPriceField.value = discountedPrice.toFixed(2);
            
            // Visual feedback
            if (discountPercentage > 0) {
                discountedPriceField.style.backgroundColor = '#d4edda';
                discountedPriceField.style.borderColor = '#28a745';
            } else {
                discountedPriceField.style.backgroundColor = '#f8f9fa';
                discountedPriceField.style.borderColor = '#dee2e6';
            }
        } else {
            discountedPriceField.value = '';
        }
    }
    
    // Add event listeners for real-time calculation
    discountPercentageField.addEventListener('input', calculateDiscountedPrice);
    discountPercentageField.addEventListener('change', calculateDiscountedPrice);
    originalPriceField.addEventListener('input', calculateDiscountedPrice);
    originalPriceField.addEventListener('change', calculateDiscountedPrice);
    
    // Calculate on page load
    calculateDiscountedPrice();
    
    // Add validation for discount percentage
    discountPercentageField.addEventListener('input', function() {
        const value = parseFloat(this.value);
        if (value < 0) {
            this.value = 0;
        } else if (value > 100) {
            this.value = 100;
        }
        calculateDiscountedPrice();
    });
    
    console.log('Dynamic discount calculation initialized');
});

