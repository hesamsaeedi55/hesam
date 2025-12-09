/**
 * Image Editor Integration for Product Form
 * Handles cropping and rotating of images during product upload
 */

class ProductImageEditor {
    constructor(options = {}) {
        // Default options
        this.options = {
            dropZoneId: 'dropZone',
            imageInputId: 'imageInput',
            imagePreviewsId: 'imagePreviews',
            cropperModalId: 'imageCropperModal',
            cropperImageId: 'cropperImage',
            applyCropButtonId: 'applyCropBtn',
            cancelCropButtonId: 'cancelCropBtn',
            rotateLeftButtonId: 'rotateLeftBtn',
            rotateRightButtonId: 'rotateRightBtn',
            ...options
        };

        // Elements
        this.dropZone = document.getElementById(this.options.dropZoneId);
        this.imageInput = document.getElementById(this.options.imageInputId);
        this.imagePreviews = document.getElementById(this.options.imagePreviewsId);
        this.cropperModal = document.getElementById(this.options.cropperModalId);
        this.cropperImage = document.getElementById(this.options.cropperImageId);
        this.applyCropButton = document.getElementById(this.options.applyCropButtonId);
        this.cancelCropButton = document.getElementById(this.options.cancelCropButtonId);
        this.rotateLeftButton = document.getElementById(this.options.rotateLeftButtonId);
        this.rotateRightButton = document.getElementById(this.options.rotateRightButtonId);
        
        // State
        this.cropper = null;
        this.currentImageId = null;
        this.currentPreviewItem = null;
        this.editedImages = new Map(); // Maps file name to edited image ID
        this.files = [];
        this.deletedImages = null;
        
        // Initialize
        this.init();
    }
    
    init() {
        // Initialize drag and drop
        if (this.dropZone) {
            this.dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                this.dropZone.style.borderColor = 'var(--primary-color)';
                this.dropZone.style.transform = 'translateY(-2px)';
            });

            this.dropZone.addEventListener('dragleave', () => {
                this.dropZone.style.borderColor = 'var(--border-color)';
                this.dropZone.style.transform = 'translateY(0)';
            });

            this.dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                this.dropZone.style.borderColor = 'var(--border-color)';
                this.dropZone.style.transform = 'translateY(0)';
                this.handleFiles(e.dataTransfer.files);
            });

            this.dropZone.addEventListener('click', () => {
                this.imageInput.click();
            });
        }

        // File input change handler
        if (this.imageInput) {
            this.imageInput.addEventListener('change', (e) => {
                this.handleFiles(e.target.files);
            });
        }
        
        // Cropper modal buttons
        if (this.applyCropButton) {
            this.applyCropButton.addEventListener('click', () => this.applyCrop());
        }
        
        if (this.cancelCropButton) {
            this.cancelCropButton.addEventListener('click', () => this.cancelCrop());
        }
        
        if (this.rotateLeftButton) {
            this.rotateLeftButton.addEventListener('click', () => this.rotateImage('left'));
        }
        
        if (this.rotateRightButton) {
            this.rotateRightButton.addEventListener('click', () => this.rotateImage('right'));
        }
        
        // Initialize sortable for preview items
        if (this.imagePreviews && typeof Sortable !== 'undefined') {
            new Sortable(this.imagePreviews, {
                animation: 150,
                ghostClass: 'sortable-ghost',
                onEnd: () => this.updatePositions()
            });
        }
    }
    
    handleFiles(newFiles) {
        if (!newFiles || newFiles.length === 0) return;
        
        // Clear previews if needed
        if (this.files.length === 0) {
            this.imagePreviews.innerHTML = '';
        }
        
        // Process each file
        Array.from(newFiles).forEach(file => {
            if (!file.type.startsWith('image/')) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                const dataUrl = e.target.result;
                this.uploadTempImage(file, dataUrl);
            };
            reader.readAsDataURL(file);
        });
    }
    
    async uploadTempImage(file, dataUrl) {
        try {
            // Create a FormData instance
            const formData = new FormData();
            formData.append('image', file);
            
            // Upload the file to the server
            const response = await fetch('/image-editor/temp/upload/', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.addPreviewItem(file, result.image_url, result.image_id);
                this.editedImages.set(file.name, result.image_id);
                this.files.push(file);
                this.updatePositions();
            } else {
                console.error('Error uploading image:', result.error);
                alert('Error uploading image: ' + result.error);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error processing image');
        }
    }
    
    addPreviewItem(file, imageUrl, imageId) {
        const previewItem = document.createElement('div');
        previewItem.className = 'preview-item';
        previewItem.dataset.imageId = imageId;
        previewItem.dataset.filename = file.name;
        
        previewItem.innerHTML = `
            <img src="${imageUrl}" alt="Preview">
            <div class="position-label"></div>
            <div class="preview-actions">
                <button type="button" class="edit-image" title="Edit Image">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button type="button" class="remove-image" title="Remove Image">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        <line x1="10" y1="11" x2="10" y2="17"></line>
                        <line x1="14" y1="11" x2="14" y2="17"></line>
                    </svg>
                </button>
            </div>
        `;
        
        // Edit button click handler
        previewItem.querySelector('.edit-image').addEventListener('click', () => {
            this.openImageEditor(imageId, previewItem);
        });
        
        // Remove button click handler
        previewItem.querySelector('.remove-image').addEventListener('click', () => {
            this.removeImage(previewItem, imageId, file.name);
        });
        
        this.imagePreviews.appendChild(previewItem);
    }
    
    updatePositions() {
        const items = this.imagePreviews.querySelectorAll('.preview-item');
        items.forEach((item, index) => {
            item.querySelector('.position-label').textContent = `${index + 1}/${items.length}`;
            
            // The first image is the primary image
            if (index === 0) {
                item.classList.add('primary-image');
            } else {
                item.classList.remove('primary-image');
            }
        });
    }
    
    openImageEditor(imageId, previewItem) {
        this.currentImageId = imageId;
        this.currentPreviewItem = previewItem;
        
        // Set the image in the cropper modal
        const img = previewItem.querySelector('img');
        this.cropperImage.src = img.src;
        
        // Show the modal
        this.cropperModal.style.display = 'flex';
        
        // Initialize the cropper
        this.initCropper();
    }
    
    initCropper() {
        // If there's an existing cropper, destroy it
        if (this.cropper) {
            this.cropper.destroy();
        }
        
        // Initialize cropper with options
        this.cropper = new Cropper(this.cropperImage, {
            viewMode: 2,
            dragMode: 'crop',
            aspectRatio: 4/5, // 4:5 portrait aspect ratio
            autoCropArea: 0.8,
            restore: false,
            guides: true,
            center: true,
            highlight: true,
            cropBoxMovable: true,
            cropBoxResizable: true,
            background: true,
            modal: true,
            zoomable: false,
            minCropBoxWidth: 50,
            minCropBoxHeight: 62.5, // Maintains 4:5 ratio (50 * 5/4)
            ready: () => {
                // Center the crop box and enforce 4:5 aspect ratio
                const canvasData = this.cropper.getCanvasData();
                const cropBoxWidth = canvasData.width * 0.8;
                const cropBoxHeight = cropBoxWidth * (5/4); // 4:5 ratio
                
                // Make sure the crop box fits within the canvas
                const maxHeight = canvasData.height * 0.9;
                const adjustedHeight = Math.min(cropBoxHeight, maxHeight);
                const adjustedWidth = adjustedHeight * (4/5); // Maintain ratio
                
                const initialCrop = {
                    left: canvasData.left + (canvasData.width - adjustedWidth) / 2,
                    top: canvasData.top + (canvasData.height - adjustedHeight) / 2,
                    width: adjustedWidth,
                    height: adjustedHeight
                };
                this.cropper.setCropBoxData(initialCrop);
            }
        });
    }
    
    async applyCrop() {
        if (!this.cropper || !this.currentImageId) return;
        
        try {
            const cropData = this.cropper.getData();
            
            // Validate crop data
            if (cropData.width < 10 || cropData.height < 10) {
                alert('Crop area too small. Please select a larger area.');
                return;
            }
            
            // Show loading state
            this.applyCropButton.disabled = true;
            this.applyCropButton.textContent = 'Processing...';
            
            // Save original image URL in case we need to revert
            const originalImgSrc = this.currentPreviewItem.querySelector('img').src;
            
            // Send crop data to the server
            const response = await fetch(`/image-editor/temp/${this.currentImageId}/crop/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    x: Math.round(cropData.x),
                    y: Math.round(cropData.y),
                    width: Math.round(cropData.width),
                    height: Math.round(cropData.height)
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Update the preview image
                if (this.currentPreviewItem) {
                    const img = this.currentPreviewItem.querySelector('img');
                    
                    // Create a new image object to ensure proper loading
                    const newImg = new Image();
                    newImg.onload = () => {
                        // Update only after the new image is successfully loaded
                        img.src = result.imageUrl + '?t=' + new Date().getTime();
                        
                        // Update the editedImages map to track this edited image
                        const filename = this.currentPreviewItem.dataset.filename;
                        if (filename) {
                            this.editedImages.set(filename, this.currentImageId);
                        }
                    };
                    newImg.onerror = () => {
                        console.error('Failed to load cropped image');
                        img.src = originalImgSrc; // Revert to original if loading fails
                        alert('Error loading cropped image. The original image will be used.');
                    };
                    // Start loading the new image
                    newImg.src = result.imageUrl + '?t=' + new Date().getTime();
                }
                
                // Close the modal
                this.closeCropperModal();
            } else {
                alert('Error cropping image: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error cropping image');
        } finally {
            // Reset button state
            this.applyCropButton.disabled = false;
            this.applyCropButton.textContent = 'Apply Crop';
        }
    }
    
    async rotateImage(direction) {
        if (!this.currentImageId) return;
        
        try {
            // Show loading state
            this.rotateLeftButton.disabled = true;
            this.rotateRightButton.disabled = true;
            
            // Save the original image URL in case we need to revert
            const originalImgSrc = this.currentPreviewItem ? 
                this.currentPreviewItem.querySelector('img').src : null;
            
            // Send rotation request to the server
            const response = await fetch(`/image-editor/temp/${this.currentImageId}/rotate/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    direction: direction
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Create a new image to ensure it loads properly
                const newImg = new Image();
                const timestampedUrl = result.imageUrl + '?t=' + new Date().getTime();
                
                newImg.onload = () => {
                    // If cropper is active, update it
                    if (this.cropper) {
                        this.cropper.destroy();
                        this.cropperImage.src = timestampedUrl;
                        // Re-initialize the cropper
                        setTimeout(() => this.initCropper(), 100);
                    }
                    
                    // Update the preview image
                    if (this.currentPreviewItem) {
                        const img = this.currentPreviewItem.querySelector('img');
                        img.src = timestampedUrl;
                    }
                };
                
                newImg.onerror = () => {
                    console.error('Failed to load rotated image');
                    // Revert to original if available
                    if (originalImgSrc && this.currentPreviewItem) {
                        this.currentPreviewItem.querySelector('img').src = originalImgSrc;
                    }
                    alert('Error loading rotated image. The original image will be used.');
                };
                
                // Start loading the new image
                newImg.src = timestampedUrl;
            } else {
                alert('Error rotating image: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error rotating image');
        } finally {
            // Reset button state
            this.rotateLeftButton.disabled = false;
            this.rotateRightButton.disabled = false;
        }
    }
    
    cancelCrop() {
        // Just close the modal without making any changes
        this.closeCropperModal();
    }
    
    closeCropperModal() {
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
        }
        
        // Don't reset currentImageId and currentPreviewItem here
        // They will be reset when a new image is opened
        this.cropperModal.style.display = 'none';
    }
    
    removeImage(previewItem, imageId, filename) {
        // Remove from DOM
        previewItem.remove();
        
        // Remove from editedImages map
        this.editedImages.delete(filename);
        
        // Remove from files array
        const fileIndex = this.files.findIndex(file => file.name === filename);
        if (fileIndex !== -1) {
            this.files.splice(fileIndex, 1);
        }
        
        // Add to deleted images list
        if (!this.deletedImages) {
            this.deletedImages = new Set();
        }
        this.deletedImages.add(imageId);
        
        // Update positions
        this.updatePositions();
        
        // Update the input files and hidden inputs
        this.updateFileInput();
        
        // Send delete request to server if this is an existing image
        if (imageId) {
            fetch(`/shop/productimage/${imageId}/delete/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status !== 'success') {
                    console.error('Error deleting image:', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    }
    
    updateFileInput() {
        if (!this.imageInput) return;
        
        // Create a new DataTransfer object
        const dataTransfer = new DataTransfer();
        
        // Add all files
        this.files.forEach(file => {
            dataTransfer.items.add(file);
        });
        
        // Set the files to the input element
        this.imageInput.files = dataTransfer.files;
        
        // Add hidden inputs for deleted and edited images
        this.updateHiddenInputs();
    }
    
    updateHiddenInputs() {
        // Remove existing hidden inputs
        const existingDeletedInputs = document.querySelectorAll('input[name="delete_images"]');
        const existingEditedInputs = document.querySelectorAll('input[name="edited_images"]');
        existingDeletedInputs.forEach(input => input.remove());
        existingEditedInputs.forEach(input => input.remove());
        
        // Add hidden inputs for deleted images
        if (this.deletedImages && this.deletedImages.size > 0) {
            this.deletedImages.forEach(imageId => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'delete_images';
                input.value = imageId;
                this.imageInput.parentNode.appendChild(input);
            });
        }
        
        // Add hidden inputs for edited images
        if (this.editedImages && this.editedImages.size > 0) {
            this.editedImages.forEach((imageId, filename) => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'edited_images';
                input.value = filename;
                this.imageInput.parentNode.appendChild(input);
            });
        }
    }
    
    // Call this method before form submission
    async prepareForSubmission() {
        // No edited images, no need to do anything
        if (this.editedImages.size === 0) return true;
        
        // Get all edited image IDs
        const imageIds = Array.from(this.editedImages.values());
        
        // For each edited image, get the final image and update the files array
        for (const [filename, imageId] of this.editedImages.entries()) {
            try {
                // Get the edited image from the server
                const response = await fetch(`/image-editor/temp/${imageId}/get/`);
                const result = await response.json();
                
                if (result.success) {
                    // Fetch the edited image
                    const imageResponse = await fetch(result.image_url);
                    const blob = await imageResponse.blob();
                    
                    // Create a new File with the same name as the original
                    const newFile = new File([blob], filename, {
                        type: blob.type,
                        lastModified: new Date().getTime()
                    });
                    
                    // Replace the old file in the files array
                    const fileIndex = this.files.findIndex(file => file.name === filename);
                    if (fileIndex !== -1) {
                        this.files[fileIndex] = newFile;
                    } else {
                        // If file not found, add it to the array
                        this.files.push(newFile);
                    }
                    
                    // Update the preview if it exists
                    const previewItem = this.imagePreviews.querySelector(`[data-filename="${filename}"]`);
                    if (previewItem) {
                        const img = previewItem.querySelector('img');
                        if (img) {
                            img.src = URL.createObjectURL(blob);
                        }
                    }
                }
            } catch (error) {
                console.error('Error preparing image for submission:', error);
                // Continue with other images
            }
        }
        
        // Update the file input with the new files
        this.updateFileInput();
        
        return true;
    }

    async saveEditedImage(originalFile, editedImageElement, existingPreview = null) {
        if (!this.cropper) return;

        try {
            // Force 4:5 ratio in the final output
            const baseWidth = 800;
            const baseHeight = Math.round(baseWidth * (5/4)); // 1000 for 4:5 ratio

            // Get the cropped canvas with forced 4:5 ratio
            const canvas = this.cropper.getCroppedCanvas({
                width: baseWidth,
                height: baseHeight,
                fillColor: '#fff',
                imageSmoothingEnabled: true,
                imageSmoothingQuality: 'high'
            });

            if (!canvas) {
                throw new Error('Failed to create canvas');
            }

            // Convert canvas to blob
            const blob = await new Promise(resolve => canvas.toBlob(resolve, originalFile.type, 0.95));

            // Create a new File object with the same name as the original
            const editedFile = new File([blob], originalFile.name, {
                type: originalFile.type,
                lastModified: new Date().getTime()
            });

            // If this is an existing image, update it instead of creating a new one
            if (existingPreview) {
                const imageId = existingPreview.dataset.imageId;
                if (imageId) {
                    // Create form data for the update
                    const formData = new FormData();
                    formData.append('image', editedFile);
                    formData.append('image_id', imageId);

                    // Send the update request
                    const response = await fetch(`/image-editor/update/${imageId}/`, {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        throw new Error('Failed to update image');
                    }

                    // Update the preview
                    const previewImage = existingPreview.querySelector('img');
                    if (previewImage) {
                        previewImage.src = URL.createObjectURL(blob);
                    }
                }
            } else {
                // For new images, store in tempImages
                this.tempImages.set(originalFile.name, editedFile);
                this.updateFileInput();
                this.updatePreview(editedFile);
            }
        } catch (error) {
            console.error('Error saving edited image:', error);
            alert('Error saving edited image. Please try again.');
        }
    }
}

// Export for use in other scripts
window.ProductImageEditor = ProductImageEditor; 