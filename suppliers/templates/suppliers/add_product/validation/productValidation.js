// Product Form Validation Schema
// This file contains validation rules and schemas for the product form

const ProductValidationSchema = {
    // Basic product information validation
    name: {
        required: true,
        minLength: 2,
        maxLength: 200,
        pattern: /^[\u0600-\u06FF\s\w\-\.]+$/,
        message: 'نام محصول باید بین 2 تا 200 کاراکتر باشد و فقط شامل حروف فارسی، انگلیسی، فاصله، خط تیره و نقطه باشد'
    },
    
    description: {
        required: true,
        minLength: 10,
        maxLength: 2000,
        message: 'توضیحات محصول باید بین 10 تا 2000 کاراکتر باشد'
    },
    
    brand: {
        required: false,
        maxLength: 100,
        pattern: /^[\u0600-\u06FF\s\w\-\.]+$/,
        message: 'نام برند باید حداکثر 100 کاراکتر باشد و فقط شامل حروف فارسی، انگلیسی، فاصله، خط تیره و نقطه باشد'
    },
    
    // Pricing validation
    price_toman: {
        required: true,
        pattern: /^\d{1,3}(,\d{3})*$/,
        min: 1000,
        max: 999999999,
        message: 'قیمت تومان باید بین 1,000 تا 999,999,999 تومان باشد'
    },
    
    price_usd: {
        required: false,
        pattern: /^\d+(\.\d{1,2})?$/,
        min: 0.01,
        max: 999999.99,
        message: 'قیمت دلار باید بین 0.01 تا 999,999.99 دلار باشد'
    },
    
    // Inventory validation
    stock_quantity: {
        required: true,
        pattern: /^\d+$/,
        min: 0,
        max: 999999,
        message: 'تعداد موجودی باید عددی بین 0 تا 999,999 باشد'
    },
    
    // Category validation
    category: {
        required: true,
        message: 'لطفا دسته‌بندی محصول را انتخاب کنید'
    },
    
    // Image validation
    images: {
        required: false,
        maxFiles: 10,
        maxFileSize: 10 * 1024 * 1024, // 10MB
        allowedTypes: ['image/jpeg', 'image/png', 'image/webp'],
        message: 'حداکثر 10 تصویر با حجم کمتر از 10 مگابایت مجاز است (فرمت‌های JPG، PNG، WebP)'
    },
    
    brand_image: {
        required: false,
        maxFileSize: 10 * 1024 * 1024, // 10MB
        allowedTypes: ['image/jpeg', 'image/png', 'image/webp'],
        message: 'تصویر برند باید کمتر از 10 مگابایت باشد (فرمت‌های JPG، PNG، WebP)'
    },
    
    // Variant validation
    variants: {
        sku: {
            required: true,
            pattern: /^[A-Z0-9\-_]+$/,
            minLength: 3,
            maxLength: 50,
            message: 'کد محصول (SKU) باید بین 3 تا 50 کاراکتر باشد و فقط شامل حروف بزرگ انگلیسی، اعداد، خط تیره و زیرخط باشد'
        },
        
        price_toman: {
            required: false,
            pattern: /^\d{1,3}(,\d{3})*$/,
            min: 1000,
            max: 999999999,
            message: 'قیمت نوع محصول باید بین 1,000 تا 999,999,999 تومان باشد'
        },
        
        stock: {
            required: true,
            pattern: /^\d+$/,
            min: 0,
            max: 999999,
            message: 'موجودی نوع محصول باید عددی بین 0 تا 999,999 باشد'
        }
    },
    
    // Specifications validation
    specifications: {
        key: {
            required: true,
            minLength: 1,
            maxLength: 100,
            pattern: /^[\u0600-\u06FF\s\w\-\.]+$/,
            message: 'کلید مشخصه باید بین 1 تا 100 کاراکتر باشد'
        },
        
        value: {
            required: true,
            minLength: 1,
            maxLength: 200,
            message: 'مقدار مشخصه باید بین 1 تا 200 کاراکتر باشد'
        }
    }
};

// Validation functions
const ProductValidator = {
    // Validate a single field
    validateField(fieldName, value, schema = ProductValidationSchema) {
        const rules = schema[fieldName];
        if (!rules) return { isValid: true };
        
        const errors = [];
        
        // Required validation
        if (rules.required && (!value || value.toString().trim() === '')) {
            errors.push(rules.message || `${fieldName} الزامی است`);
            return { isValid: false, errors };
        }
        
        // Skip other validations if value is empty and not required
        if (!value || value.toString().trim() === '') {
            return { isValid: true };
        }
        
        // Min length validation
        if (rules.minLength && value.toString().length < rules.minLength) {
            errors.push(rules.message || `${fieldName} باید حداقل ${rules.minLength} کاراکتر باشد`);
        }
        
        // Max length validation
        if (rules.maxLength && value.toString().length > rules.maxLength) {
            errors.push(rules.message || `${fieldName} باید حداکثر ${rules.maxLength} کاراکتر باشد`);
        }
        
        // Pattern validation
        if (rules.pattern && !rules.pattern.test(value.toString())) {
            errors.push(rules.message || `${fieldName} فرمت صحیح ندارد`);
        }
        
        // Min value validation
        if (rules.min !== undefined && parseFloat(value) < rules.min) {
            errors.push(rules.message || `${fieldName} باید حداقل ${rules.min} باشد`);
        }
        
        // Max value validation
        if (rules.max !== undefined && parseFloat(value) > rules.max) {
            errors.push(rules.message || `${fieldName} باید حداکثر ${rules.max} باشد`);
        }
        
        return {
            isValid: errors.length === 0,
            errors: errors
        };
    },
    
    // Validate entire form
    validateForm(formData, schema = ProductValidationSchema) {
        const errors = {};
        let isValid = true;
        
        Object.keys(schema).forEach(fieldName => {
            const value = formData[fieldName];
            const validation = this.validateField(fieldName, value, schema);
            
            if (!validation.isValid) {
                errors[fieldName] = validation.errors;
                isValid = false;
            }
        });
        
        return {
            isValid,
            errors
        };
    },
    
    // Validate file upload
    validateFile(file, rules) {
        const errors = [];
        
        if (!file) {
            if (rules.required) {
                errors.push('فایل الزامی است');
            }
            return { isValid: errors.length === 0, errors };
        }
        
        // File size validation
        if (rules.maxFileSize && file.size > rules.maxFileSize) {
            errors.push(`حجم فایل باید کمتر از ${Math.round(rules.maxFileSize / (1024 * 1024))} مگابایت باشد`);
        }
        
        // File type validation
        if (rules.allowedTypes && !rules.allowedTypes.includes(file.type)) {
            errors.push(`نوع فایل مجاز نیست. انواع مجاز: ${rules.allowedTypes.join(', ')}`);
        }
        
        return {
            isValid: errors.length === 0,
            errors
        };
    },
    
    // Validate multiple files
    validateFiles(files, rules) {
        const errors = [];
        
        if (!files || files.length === 0) {
            if (rules.required) {
                errors.push('حداقل یک فایل الزامی است');
            }
            return { isValid: errors.length === 0, errors };
        }
        
        // Max files validation
        if (rules.maxFiles && files.length > rules.maxFiles) {
            errors.push(`حداکثر ${rules.maxFiles} فایل مجاز است`);
        }
        
        // Validate each file
        Array.from(files).forEach((file, index) => {
            const fileValidation = this.validateFile(file, rules);
            if (!fileValidation.isValid) {
                errors.push(`فایل ${index + 1}: ${fileValidation.errors.join(', ')}`);
            }
        });
        
        return {
            isValid: errors.length === 0,
            errors
        };
    },
    
    // Validate variants
    validateVariants(variants) {
        const errors = [];
        
        if (!variants || variants.length === 0) {
            return { isValid: true, errors: [] };
        }
        
        variants.forEach((variant, index) => {
            const variantErrors = [];
            
            // Validate SKU
            const skuValidation = this.validateField('sku', variant.sku, ProductValidationSchema.variants);
            if (!skuValidation.isValid) {
                variantErrors.push(`SKU: ${skuValidation.errors.join(', ')}`);
            }
            
            // Validate price
            if (variant.price_toman) {
                const priceValidation = this.validateField('price_toman', variant.price_toman, ProductValidationSchema.variants);
                if (!priceValidation.isValid) {
                    variantErrors.push(`قیمت: ${priceValidation.errors.join(', ')}`);
                }
            }
            
            // Validate stock
            const stockValidation = this.validateField('stock', variant.stock, ProductValidationSchema.variants);
            if (!stockValidation.isValid) {
                variantErrors.push(`موجودی: ${stockValidation.errors.join(', ')}`);
            }
            
            if (variantErrors.length > 0) {
                errors.push(`نوع ${index + 1}: ${variantErrors.join(', ')}`);
            }
        });
        
        return {
            isValid: errors.length === 0,
            errors
        };
    }
};

// Export for use in other files
window.ProductValidationSchema = ProductValidationSchema;
window.ProductValidator = ProductValidator;
