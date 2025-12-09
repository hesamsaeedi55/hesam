function formatStoreName(input) {
    let value = input.value;
    
    // Convert to lowercase
    value = value.toLowerCase();
    
    // Replace spaces and special characters with underscores
    value = value.replace(/[^a-zA-Z0-9_]/g, '_');
    
    // Remove multiple consecutive underscores
    value = value.replace(/_+/g, '_');
    
    // Remove leading and trailing underscores
    value = value.replace(/^_+|_+$/g, '');
    
    // Ensure it starts with letter or number
    if (value && !/^[a-zA-Z0-9]/.test(value)) {
        value = 'store_' + value;
    }
    
    // Limit to 30 characters
    if (value.length > 30) {
        value = value.substring(0, 30);
    }
    
    // Update the input value
    input.value = value;
    
    // Add visual feedback
    if (value !== input.dataset.originalValue) {
        input.style.backgroundColor = '#fff3cd';
        setTimeout(() => {
            input.style.backgroundColor = '';
        }, 1000);
    }
    
    input.dataset.originalValue = value;
}

function preventInvalidChars(e) {
    // Allow: backspace, delete, tab, escape, enter
    if ([8, 9, 27, 13, 46].indexOf(e.keyCode) !== -1 ||
        // Allow: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
        (e.keyCode === 65 && e.ctrlKey === true) ||
        (e.keyCode === 67 && e.ctrlKey === true) ||
        (e.keyCode === 86 && e.ctrlKey === true) ||
        (e.keyCode === 88 && e.ctrlKey === true) ||
        // Allow: home, end, left, right
        (e.keyCode >= 35 && e.keyCode <= 40)) {
        return;
    }
    
    // Allow only letters, numbers, and underscores
    if (!/[a-zA-Z0-9_]/.test(e.key)) {
        e.preventDefault();
        return false;
    }
    
    // Check length limit
    if (e.target.value.length >= 30) {
        e.preventDefault();
        return false;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    const storeNameInput = document.getElementById('id_store_name');
    if (storeNameInput) {
        // Store original value for comparison
        storeNameInput.dataset.originalValue = storeNameInput.value;
        
        // Add event listeners
        storeNameInput.addEventListener('input', function() {
            formatStoreName(this);
        });
        
        storeNameInput.addEventListener('keypress', preventInvalidChars);
        
        // Format on paste
        storeNameInput.addEventListener('paste', function() {
            setTimeout(() => {
                formatStoreName(this);
            }, 10);
        });
        
        // Format existing value on load
        if (storeNameInput.value) {
            formatStoreName(storeNameInput);
        }
    }
});