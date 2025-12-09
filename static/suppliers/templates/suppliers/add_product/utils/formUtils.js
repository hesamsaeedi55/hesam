// Product Form Utilities - Helper functions
// This file contains utility functions for the product form

// Format number with commas for display
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

// Generate SKU automatically
function generateSKU(productName, variantAttributes = {}) {
    const prefix = productName ? productName.substring(0, 4).toUpperCase() : 'PROD';
    const random = Math.floor(Math.random() * 1000);
    return `${prefix}-${random}`;
}

// Validate form fields
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('error');
            isValid = false;
        } else {
            field.classList.remove('error');
        }
    });
    
    return isValid;
}

// Show error message
function showError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (field) {
        field.classList.add('error');
        
        // Remove existing error message
        const existingError = field.parentNode.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        // Add new error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        field.parentNode.appendChild(errorDiv);
    }
}

// Clear error message
function clearError(fieldId) {
    const field = document.getElementById(fieldId);
    if (field) {
        field.classList.remove('error');
        
        const errorMessage = field.parentNode.querySelector('.error-message');
        if (errorMessage) {
            errorMessage.remove();
        }
    }
}

// Debounce function for performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle function for performance
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Get form data as object
function getFormData(form) {
    const formData = new FormData(form);
    const data = {};
    
    for (let [key, value] of formData.entries()) {
        if (data[key]) {
            // Handle multiple values (like checkboxes)
            if (Array.isArray(data[key])) {
                data[key].push(value);
            } else {
                data[key] = [data[key], value];
            }
        } else {
            data[key] = value;
        }
    }
    
    return data;
}

// Set form data from object
function setFormData(form, data) {
    Object.keys(data).forEach(key => {
        const field = form.querySelector(`[name="${key}"]`);
        if (field) {
            if (field.type === 'checkbox') {
                field.checked = data[key];
            } else {
                field.value = data[key];
            }
        }
    });
}

// Copy object deeply
function deepCopy(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof Array) return obj.map(item => deepCopy(item));
    if (typeof obj === 'object') {
        const copy = {};
        Object.keys(obj).forEach(key => {
            copy[key] = deepCopy(obj[key]);
        });
        return copy;
    }
}

// Check if object is empty
function isEmpty(obj) {
    return Object.keys(obj).length === 0;
}

// Sanitize string for display
function sanitizeString(str) {
    if (typeof str !== 'string') return '';
    return str.replace(/[<>]/g, '').trim();
}

// Convert Persian numbers to English
function persianToEnglish(str) {
    const persianNumbers = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    const englishNumbers = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
    
    let result = str;
    persianNumbers.forEach((persian, index) => {
        result = result.replace(new RegExp(persian, 'g'), englishNumbers[index]);
    });
    
    return result;
}

// Convert English numbers to Persian
function englishToPersian(str) {
    const englishNumbers = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
    const persianNumbers = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    
    let result = str;
    englishNumbers.forEach((english, index) => {
        result = result.replace(new RegExp(english, 'g'), persianNumbers[index]);
    });
    
    return result;
}

// Export functions for use in other files
window.ProductFormUtils = {
    formatNumberWithCommas,
    generateSKU,
    validateForm,
    showError,
    clearError,
    debounce,
    throttle,
    getFormData,
    setFormData,
    deepCopy,
    isEmpty,
    sanitizeString,
    persianToEnglish,
    englishToPersian
};
