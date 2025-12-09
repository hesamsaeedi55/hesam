// Image editor functionality for product uploads
document.addEventListener('DOMContentLoaded', function() {
    // Variables
    let currentEditingImage = null;
    let cropper = null;
    let isCropActive = false;
    
    // DOM Elements
    const modal = document.getElementById('imageEditorModal');
    const editImage = document.getElementById('editImage');
    const closeBtn = document.querySelector('#imageEditorModal .close');
    const rotateLeftBtn = document.getElementById('rotateLeft');
    const rotateRightBtn = document.getElementById('rotateRight');
    const cropBtn = document.getElementById('crop');
    const resetBtn = document.getElementById('resetImage');
    const saveBtn = document.getElementById('saveImage');
    
    // Event Listeners
    if (closeBtn) {
        closeBtn.addEventListener('click', closeEditor);
    }
    
    if (modal) {
        window.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeEditor();
            }
        });
    }
    
    if (rotateLeftBtn) {
        rotateLeftBtn.addEventListener('click', function() {
            if (cropper) {
                cropper.rotate(-90);
            }
        });
    }
    
    if (rotateRightBtn) {
        rotateRightBtn.addEventListener('click', function() {
            if (cropper) {
                cropper.rotate(90);
            }
        });
    }
    
    if (cropBtn) {
        cropBtn.addEventListener('click', function() {
            if (!cropper) return;
            
            if (!isCropActive) {
                // Enable crop mode
                cropper.enable();
                cropBtn.textContent = 'لغو برش';
                cropBtn.classList.add('active');
                isCropActive = true;
            } else {
                // Disable crop mode
                cropper.disable();
                cropBtn.textContent = 'برش تصویر';
                cropBtn.classList.remove('active');
                isCropActive = false;
            }
        });
    }
    
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (cropper) {
                cropper.reset();
                
                // Disable crop mode if it was enabled
                if (isCropActive) {
                    cropper.disable();
                    cropBtn.textContent = 'برش تصویر';
                    cropBtn.classList.remove('active');
                    isCropActive = false;
                }
            }
        });
    }
    
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            if (!cropper || !currentEditingImage) return;
            
            // Get cropped canvas
            const canvas = cropper.getCroppedCanvas({
                maxWidth: 1200,
                maxHeight: 1200,
                fillColor: '#fff'
            });
            
            if (!canvas) {
                alert('خطا در ایجاد تصویر جدید.');
                return;
            }
            
            // Convert canvas to blob
            canvas.toBlob(function(blob) {
                // Handle based on whether this is an existing or new image
                if (currentEditingImage.id) {
                    // Existing image
                    handleExistingImage(blob);
                } else {
                    // New image
                    handleNewImage(blob);
                }
                
                // Close the editor
                closeEditor();
            }, 'image/jpeg', 0.95);
        });
    }
    
    // Add edit buttons to image previews
    function addEditButtonsToImages() {
        // For new uploads
        document.querySelectorAll('.preview-item').forEach(function(item) {
            if (!item.querySelector('.edit')) {
                const editBtn = document.createElement('div');
                editBtn.className = 'edit';
                editBtn.innerHTML = '✎';
                editBtn.addEventListener('click', function() {
                    // Find the file and index
                    const img = item.querySelector('img');
                    const dataUrl = img.src;
                    
                    // Find corresponding file
                    let fileIndex = Array.from(document.querySelectorAll('.preview-item')).indexOf(item);
                    let file = window.files ? window.files[fileIndex] : null;
                    
                    // Open editor
                    openEditor({
                        dataUrl: dataUrl,
                        file: file,
                        index: fileIndex,
                        id: item.dataset.imageId || null
                    });
                });
                
                item.appendChild(editBtn);
            }
        });
    }
    
    // Functions
    function openEditor(imageData) {
        if (!modal || !editImage) {
            console.error('Editor elements not found!');
            return;
        }
        
        console.log('Opening editor for image:', imageData);
        currentEditingImage = imageData;
        
        // Set image source
        editImage.src = imageData.dataUrl;
        
        // Show modal
        modal.style.display = 'block';
        
        // Initialize cropper when image loads
        editImage.onload = function() {
            console.log('Image loaded, initializing cropper');
            // Destroy previous cropper if exists
            if (cropper) {
                cropper.destroy();
            }
            
            try {
                // Initialize cropper
                cropper = new Cropper(editImage, {
                    viewMode: 1,
                    dragMode: 'move',
                    autoCropArea: 0.8,
                    restore: false,
                    guides: true,
                    center: true,
                    highlight: false,
                    cropBoxMovable: true,
                    cropBoxResizable: true,
                    toggleDragModeOnDblclick: false,
                    ready: function() {
                        console.log('Cropper initialized');
                        // Initially disable crop mode
                        cropper.disable();
                        isCropActive = false;
                    }
                });
            } catch (e) {
                console.error('Error initializing cropper:', e);
                alert('خطا در بارگذاری ابزار ویرایش تصویر.');
            }
        };
    }
    
    function closeEditor() {
        if (!modal) return;
        
        // Hide modal
        modal.style.display = 'none';
        
        // Destroy cropper
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        
        // Reset state
        currentEditingImage = null;
        isCropActive = false;
        
        // Reset crop button
        if (cropBtn) {
            cropBtn.textContent = 'برش تصویر';
            cropBtn.classList.remove('active');
        }
    }
    
    function handleExistingImage(blob) {
        const form = document.getElementById('product_form');
        if (!form) return;
        
        // Create a hidden input for the edited image
        const editInput = document.createElement('input');
        editInput.type = 'hidden';
        editInput.name = 'edit_image_' + currentEditingImage.id;
        editInput.value = 'true';
        form.appendChild(editInput);
        
        // Store the blob for form submission
        if (!window.editedImages) window.editedImages = {};
        window.editedImages[currentEditingImage.id] = blob;
        
        // Update the preview image
        const previewItem = document.querySelector(`.preview-item[data-image-id="${currentEditingImage.id}"]`);
        if (previewItem) {
            const previewImage = previewItem.querySelector('img');
            if (previewImage) {
                previewImage.src = URL.createObjectURL(blob);
            }
        }
    }
    
    function handleNewImage(blob) {
        if (!currentEditingImage.file) {
            console.error('No file found in current image data');
            return;
        }
        
        // Create a new File object
        const fileName = currentEditingImage.file.name;
        const editedFile = new File([blob], fileName, {
            type: 'image/jpeg',
            lastModified: new Date().getTime()
        });
        
        // Replace file in files array
        if (window.files && currentEditingImage.index !== undefined) {
            const index = currentEditingImage.index;
            
            // Update the file
            window.files[index] = editedFile;
            
            // Update form input
            const imageInput = document.getElementById('imageInput');
            if (imageInput) {
                const dataTransfer = new DataTransfer();
                window.files.forEach(file => {
                    dataTransfer.items.add(file);
                });
                imageInput.files = dataTransfer.files;
            }
            
            // Update preview
            const previewItems = document.querySelectorAll('.preview-item');
            if (previewItems[index]) {
                const previewImage = previewItems[index].querySelector('img');
                if (previewImage) {
                    previewImage.src = URL.createObjectURL(blob);
                }
            }
        }
    }
    
    // Initialize edit buttons
    setTimeout(addEditButtonsToImages, 1000);
    
    // Make functions accessible globally
    window.imageEditor = {
        openEditor: openEditor,
        closeEditor: closeEditor,
        addEditButtons: addEditButtonsToImages
    };
}); 