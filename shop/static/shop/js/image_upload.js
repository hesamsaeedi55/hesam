document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('id_images');
    const previewContainer = document.getElementById('image-preview-container');
    const existingImagesContainer = document.getElementById('existing-images-container');
    const imageLimitWarning = document.getElementById('image-limit-warning');
    const selectAllBtn = document.getElementById('select-all-images');
    const bulkDeleteBtn = document.getElementById('bulk-delete-images');
    const MAX_IMAGES = 10;

    function updateImageCounters() {
        const existingCount = existingImagesContainer ? existingImagesContainer.children.length : 0;
        const newCount = previewContainer ? previewContainer.children.length : 0;
        const totalCount = existingCount + newCount;

        // Update counters for existing images
        if (existingImagesContainer) {
            Array.from(existingImagesContainer.children).forEach((image, index) => {
                const counter = image.querySelector('.image-counter');
                if (counter) {
                    counter.textContent = `${index + 1}/${MAX_IMAGES}`;
                }
            });
        }

        // Update counters for new images
        if (previewContainer) {
            Array.from(previewContainer.children).forEach((image, index) => {
                const counter = image.querySelector('.image-counter');
                if (counter) {
                    counter.textContent = `${existingCount + index + 1}/${MAX_IMAGES}`;
                }
            });
        }

        // Show/hide warning
        if (imageLimitWarning) {
            imageLimitWarning.style.display = totalCount >= MAX_IMAGES ? 'block' : 'none';
        }
    }

    function createImagePreview(file) {
        const reader = new FileReader();
        const imagePreview = document.createElement('div');
        imagePreview.className = 'image-preview';
        
        reader.onload = function(e) {
            imagePreview.innerHTML = `
                <img src="${e.target.result}" alt="Preview">
                <button type="button" class="remove-image">×</button>
                <div class="image-counter">0/${MAX_IMAGES}</div>
            `;
            
            // Add remove button functionality
            const removeButton = imagePreview.querySelector('.remove-image');
            removeButton.addEventListener('click', function() {
                imagePreview.remove();
                updateImageCounters();
            });
        };
        
        reader.readAsDataURL(file);
        return imagePreview;
    }

    // Handle file input change
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const files = Array.from(this.files);
            const currentCount = previewContainer ? previewContainer.children.length : 0;
            
            if (currentCount + files.length > MAX_IMAGES) {
                imageLimitWarning.style.display = 'block';
                return;
            }
            
            files.forEach(file => {
                if (file.type.startsWith('image/')) {
                    const imagePreview = createImagePreview(file);
                    previewContainer.appendChild(imagePreview);
                }
            });
            
            updateImageCounters();
        });
    }

    // Initialize Sortable for new images
    if (previewContainer) {
        new Sortable(previewContainer, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            onEnd: function() {
                updateImageCounters();
            }
        });
    }

    // Initialize Sortable for existing images
    if (existingImagesContainer) {
        new Sortable(existingImagesContainer, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            handle: '.image-preview',
            onEnd: function() {
                updateImageCounters();
            }
        });
    }

    // Handle bulk actions
    if (selectAllBtn && bulkDeleteBtn) {
        selectAllBtn.addEventListener('click', function() {
            const checkboxes = document.querySelectorAll('.image-checkbox');
            const allChecked = Array.from(checkboxes).every(checkbox => checkbox.checked);
            
            checkboxes.forEach(checkbox => {
                checkbox.checked = !allChecked;
                checkbox.closest('.image-preview').classList.toggle('selected', !allChecked);
            });
        });

        bulkDeleteBtn.addEventListener('click', function() {
            const selectedImages = document.querySelectorAll('.image-checkbox:checked');
            selectedImages.forEach(checkbox => {
                const imagePreview = checkbox.closest('.image-preview');
                imagePreview.remove();
            });
            updateImageCounters();
        });
    }
}); 