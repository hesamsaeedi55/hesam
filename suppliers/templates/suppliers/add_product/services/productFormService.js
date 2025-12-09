// Product Form Services - Main JavaScript functionality
// This file contains all the JavaScript functions for the product form

// Global form submission handler
function handleSaveClick(button) {
    console.log('🔘 Save button clicked:', button.value);
    
    // Get the form
    const form = document.getElementById('product_form');
    if (form) {
        // Ensure CSRF hidden input exists and matches cookie
        try {
            ensureCsrfHiddenInput(form);
        } catch (e) {
            console.log('⚠️ CSRF ensure error:', e);
        }
        // Clear any previous error messages
        clearErrorMessages();
        
        // Try to add variant data if function exists
        if (typeof addVariantDataToForm === 'function') {
            console.log('🔄 Adding variant data to form');
            try {
                addVariantDataToForm();
            } catch (e) {
                console.log('⚠️ Error adding variant data:', e);
            }
        }
        
        console.log('📤 Submitting form...');
        // Just submit the form normally
        return true; // Allow normal form submission
    } else {
        console.log('❌ Form not found!');
        return false;
    }
}

// Function to clear error messages
function clearErrorMessages() {
    // Remove any existing error alerts
    const existingAlerts = document.querySelectorAll('.alert-danger');
    existingAlerts.forEach(alert => alert.remove());
    
    // Clear field-level errors
    const errorMessages = document.querySelectorAll('.error-message');
    errorMessages.forEach(error => error.remove());
}

// Function to display error message
function displayErrorMessage(message) {
    // Create error alert
    const errorAlert = document.createElement('div');
    errorAlert.className = 'alert alert-danger';
    errorAlert.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #f8d7da; color: #721c24; padding: 20px 30px; border-radius: 8px; box-shadow: 0 6px 20px rgba(0,0,0,0.3); z-index: 5000; font-size: 16px; font-weight: bold; border: 2px solid #f5c6cb; max-width: 400px;';
    
    errorAlert.innerHTML = `
        <h4 style="color: #721c24; margin: 0 0 0.5rem 0;">❌ خطا در ذخیره محصول</h4>
        <p style="color: #721c24; margin: 0; font-size: 0.9rem;">${message}</p>
        <button onclick="this.parentElement.remove()" style="position: absolute; top: 5px; right: 10px; background: none; border: none; font-size: 18px; cursor: pointer; color: #721c24;">&times;</button>
    `;
    
    document.body.appendChild(errorAlert);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (errorAlert.parentElement) {
            errorAlert.remove();
        }
    }, 10000);
}

// Make functions global
window.handleSaveClick = handleSaveClick;
window.clearErrorMessages = clearErrorMessages;
window.displayErrorMessage = displayErrorMessage;

// Helpers for CSRF
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function ensureCsrfHiddenInput(form) {
    const cookieToken = getCookie('csrftoken');
    if (!cookieToken) {
        console.log('⚠️ csrftoken cookie not found');
        return;
    }
    let input = form.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!input) {
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrfmiddlewaretoken';
        form.appendChild(input);
        console.log('✅ Injected missing csrfmiddlewaretoken hidden input');
    }
    if (input.value !== cookieToken) {
        input.value = cookieToken;
        console.log('✅ Synced csrfmiddlewaretoken value from cookie');
    }
}

// Force add variants for testing
window.forceAddVariants = function() {
    console.log('🧪 Force adding variants for testing...');
    
    const form = document.getElementById('product_form');
    if (!form) {
        console.log('❌ Form not found!');
        return;
    }
    
    // Remove existing variant inputs
    const existingInputs = form.querySelectorAll('input[name="variants_data"], input[name="variant_attributes"]');
    existingInputs.forEach(input => input.remove());
    
    // Add test variant data directly
    const testVariants = [
        {
            id: 'test-1',
            sku: 'TEST-VARIANT-001',
            attributes: { color: 'قرمز', size: 'M' },
            priceToman: '150000',
            stock: 10,
            isActive: true
        },
        {
            id: 'test-2', 
            sku: 'TEST-VARIANT-002',
            attributes: { color: 'آبی', size: 'L' },
            priceToman: '160000', 
            stock: 15,
            isActive: true
        }
    ];
    
    const variantDataInput = document.createElement('input');
    variantDataInput.type = 'hidden';
    variantDataInput.name = 'variants_data';
    variantDataInput.value = JSON.stringify(testVariants);
    form.appendChild(variantDataInput);
    
    console.log('✅ Forced variant data added:', variantDataInput.value);
    
    // Verify it's there
    const checkInput = form.querySelector('input[name="variants_data"]');
    if (checkInput) {
        console.log('✅ Verification: variants_data found with value:', checkInput.value);
    } else {
        console.log('❌ Verification: variants_data NOT found!');
    }
};

// Global variant functions that need to be accessible from onclick handlers
function toggleAttributeSelection(element, attrName) {
    const checkbox = element.querySelector('input[type="checkbox"]');
    checkbox.checked = !checkbox.checked;
    
    if (checkbox.checked) {
        element.classList.add('selected');
    } else {
        element.classList.remove('selected');
    }
    
    // Show/hide variant management section based on selection
    const variantsManagement = document.getElementById('variantsManagement');
    const selectedCount = document.querySelectorAll('.variant-attribute-item.selected').length;
    
    console.log('🔍 toggleAttributeSelection called for:', attrName);
    console.log('🔍 Checkbox checked:', checkbox.checked);
    console.log('🔍 Selected count:', selectedCount);
    console.log('🔍 variantsManagement found:', !!variantsManagement);
    
    if (variantsManagement) {
        if (selectedCount > 0) {
            variantsManagement.style.display = 'block';
            console.log('✅ Showing variants management section');
        } else {
            variantsManagement.style.display = 'none';
            console.log('❌ Hiding variants management section');
        }
    } else {
        console.log('❌ variantsManagement element not found!');
    }
}

function generateTestVariants() {
    const selectedAttrs = document.querySelectorAll('.variant-attribute-item.selected');
    let combinations = [];
    
    if (selectedAttrs.length > 0) {
        // Simple test: create 6 variants
        const variants = [
            { sku: 'TSH-001-RED-M', attrs: 'رنگ: قرمز سایز: M', price: '150000', stock: '10' },
            { sku: 'TSH-002-BLUE-L', attrs: 'رنگ: آبی سایز: L', price: '150000', stock: '15' },
            { sku: 'TSH-003-WHITE-S', attrs: 'رنگ: سفید سایز: S', price: '140000', stock: '20' },
            { sku: 'TSH-004-BLACK-XL', attrs: 'رنگ: سیاه سایز: XL', price: '160000', stock: '8' },
            { sku: 'TSH-005-GREEN-M', attrs: 'رنگ: سبز سایز: M', price: '150000', stock: '12' },
            { sku: 'TSH-006-RED-L', attrs: 'رنگ: قرمز سایز: L', price: '150000', stock: '18' }
        ];
        
        const table = document.getElementById('variantsTableBody');
        variants.forEach(variant => {
            const row = table.insertRow();
            row.innerHTML = `<td>${variant.sku}</td><td>${variant.attrs}</td><td>${parseInt(variant.price).toLocaleString()} تومان</td><td>${variant.stock}</td><td>فعال</td><td><button onclick="this.closest('tr').remove()">حذف</button></td>`;
        });
        
        alert('✅ ' + variants.length + ' نوع محصول ایجاد شد!');
        
        // Show management section
        document.getElementById('variantsManagement').style.display = 'block';
    } else {
        alert('⚠️ لطفا حداقل یک ویژگی انتخاب کنید');
    }
}

// Format number with commas
function formatNumberWithCommas(input) {
    if (!input) return;
    
    // Remove any existing commas
    let value = input.value.replace(/,/g, '');
    
    // Only format if it's a valid number
    if (!isNaN(value) && value !== '') {
        // Add commas for thousands separator
        input.value = parseInt(value).toLocaleString();
    }
}

// Initialize form when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 JavaScript is loading...');
    console.log('✅ handleSaveClick function defined:', typeof handleSaveClick);
    
    // Initialize form
    const form = document.getElementById('product_form');
    const variantToggle = document.getElementById('has_variants');
    const variantContent = document.getElementById('variants-content');
    
    // Setup variant toggle
    if (variantToggle && variantContent) {
        variantToggle.addEventListener('change', function() {
            variantContent.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // Initialize variant management
    if (typeof initVariantManagement === 'function') {
        initVariantManagement();
    }
    
    // Handle form submission
    if (form) {
        form.addEventListener('submit', function(e) {
            console.log('📤 Form submission started...');
            console.log('📤 Form action:', form.action);
            console.log('📤 Form method:', form.method);
            console.log('📤 Event target:', e.target);
            console.log('📤 Event submitter:', e.submitter);
            
            // Check if variants are enabled and exclude variant attributes from validation
            const hasVariantsCheckbox = document.getElementById('has_variants');
            const variantsEnabled = hasVariantsCheckbox && hasVariantsCheckbox.checked;
            
            if (variantsEnabled) {
                console.log('🔄 Variants enabled, checking for variant attributes to exclude...');
                
                // Get selected variant attributes directly from DOM to avoid timing issues
                const selectedVariantItems = document.querySelectorAll('.variant-attribute-item.selected');
                const selectedVariantKeys = Array.from(selectedVariantItems).map(item => item.getAttribute('data-attribute'));
                console.log('🔍 Selected variant keys from DOM:', selectedVariantKeys);
                
                // Remove required attribute from variant attribute fields
                selectedVariantKeys.forEach(key => {
                    const attrField = form.querySelector(`[name="attr_${key}"]`);
                    const variantAttrField = form.querySelector(`[name="variant_attr_${key}"]`);
                    
                    if (attrField) {
                        console.log(`🔧 Removing required attribute from attr_${key}`);
                        attrField.removeAttribute('required');
                    }
                    if (variantAttrField) {
                        console.log(`🔧 Removing required attribute from variant_attr_${key}`);
                        variantAttrField.removeAttribute('required');
                    }
                });
            }
            
            // Add variant data to form if variants are enabled
            if (variantToggle && variantToggle.checked && typeof addVariantDataToForm === 'function') {
                console.log('🔄 Adding variant data to form...');
                addVariantDataToForm();
            }
            
            // Log form data before submission
            const formData = new FormData(form);
            console.log('📋 Form data being submitted:');
            for (let [key, value] of formData.entries()) {
                console.log(`  ${key}: ${value}`);
            }
            
            console.log('✅ Form submission proceeding...');
            console.log('✅ About to submit form to:', form.action);
            
            // Add debug logging for the response
            console.log('📤 Form is about to be submitted...');
            
            // Don't prevent default - let the form submit normally
        });
    }
});
