class ImageEditor {
    constructor() {
        this.currentImage = null;
        this.rotation = 0;
        this.cropData = null;
        this.tempImages = new Map(); // Store edited images temporarily
        this.cropper = null;
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        const imageInput = document.getElementById('id_images');
        if (imageInput) {
            imageInput.addEventListener('change', (e) => this.handleImageSelect(e));
        }
    }

    handleImageSelect(event) {
        const files = event.target.files;
        for (let file of files) {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.currentImage = e.target.result;
                this.showEditor(file);
            };
            reader.readAsDataURL(file);
        }
    }

    showEditor(file, existingPreview = null) {
        // Create modal for image editing
        const modal = document.createElement('div');
        modal.className = 'image-editor-modal';
        modal.innerHTML = `
            <div class="image-editor-container">
                <div class="image-editor-header">
                    <h3>Edit Image</h3>
                    <button class="close-editor">&times;</button>
                </div>
                <div class="image-editor-content">
                    <div class="image-preview-container">
                        <img src="${this.currentImage}" id="editable-image" alt="Preview">
                    </div>
                    <div class="image-editor-controls">
                        <button class="rotate-left" title="Rotate Left">
                            <i class="fas fa-undo"></i>
                        </button>
                        <button class="rotate-right" title="Rotate Right">
                            <i class="fas fa-redo"></i>
                        </button>
                        <button class="crop-image" title="Crop Image">
                            <i class="fas fa-crop"></i>
                        </button>
                    </div>
                </div>
                <div class="image-editor-footer">
                    <button class="cancel-edit">Cancel</button>
                    <button class="save-edit">Save Changes</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Initialize Cropper.js
        const image = modal.querySelector('#editable-image');
        image.onload = () => {
            this.cropper = new Cropper(image, {
                aspectRatio: 4/5,
                viewMode: 2,
                autoCropArea: 0.8,
                responsive: true,
                restore: false,
                guides: true,
                center: true,
                highlight: false,
                cropBoxMovable: true,
                cropBoxResizable: true,
                toggleDragModeOnDblclick: false,
                cropBoxMovable: false,
                cropBoxResizable: false,
                ready: function() {
                    // Force the crop box to be 4:5
                    const containerData = this.cropper.getContainerData();
                    const width = containerData.width * 0.8;
                    const height = width * (5/4);
                    
                    this.cropper.setCropBoxData({
                        width: width,
                        height: height,
                        left: (containerData.width - width) / 2,
                        top: (containerData.height - height) / 2
                    });

                    // Lock the aspect ratio
                    this.cropper.setAspectRatio(4/5);
                }.bind(this)
            });
        };

        // Setup event listeners for the editor
        this.setupEditorEvents(modal, file, existingPreview);
    }

    setupEditorEvents(modal, file, existingPreview) {
        const editableImage = modal.querySelector('#editable-image');
        const closeBtn = modal.querySelector('.close-editor');
        const cancelBtn = modal.querySelector('.cancel-edit');
        const saveBtn = modal.querySelector('.save-edit');
        const rotateLeftBtn = modal.querySelector('.rotate-left');
        const rotateRightBtn = modal.querySelector('.rotate-right');
        const cropBtn = modal.querySelector('.crop-image');

        // Close modal
        closeBtn.onclick = () => {
            if (this.cropper) {
                this.cropper.destroy();
                this.cropper = null;
            }
            modal.remove();
        };
        cancelBtn.onclick = () => {
            if (this.cropper) {
                this.cropper.destroy();
                this.cropper = null;
            }
            modal.remove();
        };

        // Rotate image
        rotateLeftBtn.onclick = () => {
            if (this.cropper) {
                this.cropper.rotate(-90);
            }
        };
        rotateRightBtn.onclick = () => {
            if (this.cropper) {
                this.cropper.rotate(90);
            }
        };

        // Save edited image
        saveBtn.onclick = () => {
            if (this.cropper) {
                this.saveEditedImage(file, editableImage, existingPreview).then(editedFile => {
                    this.tempImages.set(file.name, editedFile);
                    this.updateFileInput();
                    if (existingPreview) {
                        this.updateExistingPreview(existingPreview, editedFile);
                    } else {
                        this.updatePreview(editedFile);
                    }
                }).catch(error => {
                    console.error('Error saving edited image:', error);
                    alert('Error saving edited image. Please try again.');
                });
                this.cropper.destroy();
                this.cropper = null;
            }
            modal.remove();
        };

        // Toggle crop mode
        cropBtn.onclick = () => {
            if (this.cropper) {
                const isCropMode = cropBtn.classList.toggle('active');
                if (isCropMode) {
                    this.cropper.setDragMode('crop');
                } else {
                    this.cropper.setDragMode('move');
                }
            }
        };
    }

    async saveEditedImage(originalFile, editedImageElement, existingPreview = null) {
        try {
            // Convert edited image to file
            const editedFile = await this.dataURItoFile(
                editedImageElement.src, 
                originalFile.name || 'edited_image.jpg'
            );

            // Preserve original metadata if possible
            if (originalFile.originalUrl) {
                editedFile.originalUrl = originalFile.originalUrl;
            }

            // If there's an existing preview, update its source
            if (existingPreview) {
                existingPreview.src = editedImageElement.src;
                existingPreview.dataset.originalFileName = editedFile.name;
                
                // Preserve original URL if available
                if (originalFile.originalUrl) {
                    existingPreview.dataset.originalUrl = originalFile.originalUrl;
                }
            }

            return editedFile;
        } catch (error) {
            console.error('Error saving edited image:', error);
            throw error;
        }
    }

    async dataURItoFile(dataURI, filename) {
        const response = await fetch(dataURI);
        const blob = await response.blob();
        return new File([blob], filename, { type: blob.type });
    }

    updatePreview(editedFile) {
        const previewContainer = document.getElementById('image-preview-container');
        const reader = new FileReader();
        
        reader.onload = (e) => {
            const preview = document.createElement('div');
            preview.className = 'image-preview';
            preview.innerHTML = `
                <img src="${e.target.result}" alt="Preview">
                <div class="image-preview-controls">
                    <button type="button" class="edit-image" onclick="editImage('${editedFile.name}')">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button type="button" class="remove-image" onclick="removeImage('${editedFile.name}')">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            previewContainer.appendChild(preview);
        };
        
        reader.readAsDataURL(editedFile);
    }

    updateExistingPreview(existingPreview, editedFile) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = existingPreview.querySelector('img');
            img.src = e.target.result;
        };
        reader.readAsDataURL(editedFile);
    }

    updateFileInput() {
        const fileInput = document.getElementById('id_images');
        const dataTransfer = new DataTransfer();
        
        // Add all edited files to the DataTransfer object
        this.tempImages.forEach(file => {
            dataTransfer.items.add(file);
        });
        
        // Update the file input
        fileInput.files = dataTransfer.files;
    }
}

// Initialize the image editor when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const imageEditor = new ImageEditor();
    imageEditor.init();
});

// Make removeImage function available globally
function removeImage(fileName) {
    const imageEditor = new ImageEditor();
    imageEditor.tempImages.delete(fileName);
    imageEditor.updateFileInput();
    
    // Remove the preview
    const previews = document.querySelectorAll('.image-preview');
    previews.forEach(preview => {
        const img = preview.querySelector('img');
        if (img.src.includes(fileName)) {
            preview.remove();
        }
    });
}

// Make editImage function available globally
function editImage(fileName) {
    const imageEditor = new ImageEditor();
    const previews = document.querySelectorAll('.image-preview');
    
    previews.forEach(preview => {
        const img = preview.querySelector('img');
        if (img.src.includes(fileName)) {
            const file = imageEditor.tempImages.get(fileName);
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    imageEditor.currentImage = e.target.result;
                    imageEditor.showEditor(file, preview);
                };
                reader.readAsDataURL(file);
            }
        }
    });
} 