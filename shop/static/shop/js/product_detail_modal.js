document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('productModal');
    const closeButtons = document.querySelectorAll('.close-modal');
    const modalTitle = document.getElementById('modalProductTitle');
    const modalImage = document.getElementById('modalProductImage');
    const modalCategory = document.getElementById('modalCategory');
    const modalSupplier = document.getElementById('modalSupplier');
    const modalStatus = document.getElementById('modalStatus');
    const modalPrice = document.getElementById('modalPrice');
    const modalDescription = document.getElementById('modalDescription');
    const modalAttributes = document.getElementById('modalAttributes');
    const attributesList = document.getElementById('attributesList');
    const modalEditButton = document.getElementById('modalEditButton');
    const similarProductsList = document.getElementById('similarProductsList');
    const thumbnailGallery = document.getElementById('thumbnailGallery');

    // Remove any existing sidebar
    const sidebar = document.querySelector('.product-detail-sidebar');
    if (sidebar) {
        sidebar.remove();
    }

    // Make table rows clickable
    const rows = document.querySelectorAll('tr[class^="row"]');
    rows.forEach(row => {
        const cells = Array.from(row.cells).slice(0, -1); // Exclude the last cell (actions)
        cells.forEach(cell => {
            cell.style.cursor = 'pointer';
            cell.addEventListener('click', function(e) {
                // Don't trigger if clicking on a link or button
                if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') {
                    return;
                }

                // Get the product ID from the row
                const productId = row.getAttribute('data-product-id');
                if (productId) {
                    showProductDetails(productId);
                }
            });
        });
    });

    // Close modal when clicking close buttons
    closeButtons.forEach(button => {
        button.addEventListener('click', () => {
            modal.classList.remove('active');
            document.body.style.overflow = ''; // Restore scrolling
        });
    });

    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
            document.body.style.overflow = ''; // Restore scrolling
        }
    });

    // Close modal with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            modal.classList.remove('active');
            document.body.style.overflow = ''; // Restore scrolling
        }
    });

    function showProductDetails(productId) {
        // Prevent body scrolling when modal is open
        document.body.style.overflow = 'hidden';

        // Show loading state
        modalTitle.textContent = 'Loading...';
        modalImage.src = '';
        modalCategory.textContent = '';
        modalSupplier.textContent = '';
        modalStatus.textContent = '';
        modalPrice.textContent = '';
        modalDescription.textContent = '';
        attributesList.innerHTML = '';
        similarProductsList.innerHTML = '';
        thumbnailGallery.innerHTML = '';
        modalEditButton.href = `/admin/shop/product/${productId}/change/`;

        // Show modal
        modal.classList.add('active');

        // Fetch product details
        fetch(`/shop/product/${productId}/detail/`)
            .then(response => response.json())
            .then(data => {
                // Update modal content
                modalTitle.textContent = data.name;
                modalCategory.textContent = data.category;
                modalSupplier.textContent = data.supplier || 'N/A';
                modalStatus.textContent = data.is_active ? 'Active' : 'Inactive';
                modalPrice.textContent = data.price;
                modalDescription.textContent = data.description || 'No description available';

                // Update images and thumbnails
                if (data.images && data.images.length > 0) {
                    // Set main image to first image or primary image
                    const primaryImage = data.images.find(img => img.is_primary) || data.images[0];
                    modalImage.src = primaryImage.url;

                    // Create thumbnails
                    thumbnailGallery.innerHTML = '';
                    data.images.forEach((image, index) => {
                        const thumbnail = document.createElement('img');
                        thumbnail.src = image.url;
                        thumbnail.alt = `${data.name} - Image ${index + 1}`;
                        thumbnail.className = 'thumbnail';
                        if (image.url === primaryImage.url) {
                            thumbnail.classList.add('active');
                        }

                        // Add click handler to change main image
                        thumbnail.addEventListener('click', () => {
                            // Update main image
                            modalImage.src = image.url;
                            
                            // Update active thumbnail
                            document.querySelectorAll('.thumbnail').forEach(thumb => {
                                thumb.classList.remove('active');
                            });
                            thumbnail.classList.add('active');
                        });

                        thumbnailGallery.appendChild(thumbnail);
                    });
                } else {
                    modalImage.src = '/static/shop/images/no-image.png';
                }

                // Update attributes
                if (Object.keys(data.attributes).length > 0) {
                    attributesList.innerHTML = '';
                    Object.entries(data.attributes).forEach(([key, value]) => {
                        const attributeItem = document.createElement('p');
                        attributeItem.innerHTML = `<strong>${key}:</strong> ${value}`;
                        attributesList.appendChild(attributeItem);
                    });
                    modalAttributes.style.display = 'block';
                } else {
                    modalAttributes.style.display = 'none';
                }

                // Update tags
                if (data.tags && data.tags.length > 0) {
                    const tagsSection = document.createElement('div');
                    tagsSection.className = 'info-section';
                    tagsSection.innerHTML = '<h3>Tags</h3>';
                    const tagsList = document.createElement('div');
                    tagsList.className = 'tags-list';
                    data.tags.forEach(tag => {
                        const tagElement = document.createElement('span');
                        tagElement.className = 'tag';
                        tagElement.textContent = tag.name;
                        tagsList.appendChild(tagElement);
                    });
                    tagsSection.appendChild(tagsList);
                    modalAttributes.parentNode.insertBefore(tagsSection, modalAttributes.nextSibling);
                }

                // Update similar products
                if (data.similar_products && data.similar_products.length > 0) {
                    similarProductsList.innerHTML = '';
                    data.similar_products.forEach(product => {
                        const productCard = document.createElement('div');
                        productCard.className = 'similar-product-card';
                        productCard.innerHTML = `
                            <img src="${product.image_url || ''}" alt="${product.name}" class="similar-product-image">
                            <div class="similar-product-name">${product.name}</div>
                            <div class="similar-product-price">${product.price}</div>
                        `;
                        
                        // Add click handler to show product details
                        productCard.addEventListener('click', () => {
                            showProductDetails(product.id);
                        });
                        
                        similarProductsList.appendChild(productCard);
                    });
                } else {
                    similarProductsList.innerHTML = '<p>No similar products found.</p>';
                }
            })
            .catch(error => {
                console.error('Error fetching product details:', error);
                modalTitle.textContent = 'Error loading product details';
            });
    }
}); 