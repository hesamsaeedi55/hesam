document.addEventListener('DOMContentLoaded', function() {
    // Create and append sidebar to the body if it doesn't exist
    let sidebar = document.getElementById('product-detail-sidebar');
    
    if (!sidebar) {
        sidebar = document.createElement('div');
        sidebar.id = 'product-detail-sidebar';
        sidebar.className = 'product-detail-sidebar';
        sidebar.innerHTML = `
            <div class="sidebar-header">
                <h3>Product Details</h3>
                <button class="close-sidebar">&times;</button>
            </div>
            <div class="sidebar-content">
                <div class="sidebar-loader">Loading...</div>
                <div class="product-info" style="display:none;"></div>
            </div>
        `;
        document.body.appendChild(sidebar);
    }

    // Add close button functionality
    sidebar.querySelector('.close-sidebar').addEventListener('click', function() {
        sidebar.classList.remove('active');
    });

    // Allow closing with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar.classList.contains('active')) {
            sidebar.classList.remove('active');
        }
    });

    // Find all rows in the admin list view
    const resultList = document.getElementById('result_list');
    if (!resultList) return;
    
    const rows = resultList.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        // Add row click handler
        makeRowClickable(row);
    });
    
    // Function to make a row clickable
    function makeRowClickable(row) {
        // Find all cells in the row except in the last column (actions)
        const cells = Array.from(row.querySelectorAll('td:not(:last-child), th'));
        
        cells.forEach(cell => {
            // Get the product ID from the row
            const idCell = row.querySelector('th:first-child');
            if (!idCell) return;
            
            // Extract ID from cell content or link
            let productId;
            const idLink = idCell.querySelector('a');
            
            if (idLink) {
                const href = idLink.getAttribute('href');
                const match = href.match(/\/(\d+)\//);
                if (match) {
                    productId = match[1];
                }
            }
            
            if (!productId) return;
            
            // Add click handler to the cell
            cell.addEventListener('click', function(e) {
                // Don't trigger if clicking on a checkbox, button or internal link
                if (e.target.tagName === 'INPUT' || 
                    e.target.tagName === 'BUTTON' || 
                    e.target.tagName === 'A' ||
                    e.target.closest('a, button, input')) {
                    return;
                }
                
                // Stop event propagation
                e.stopPropagation();
                
                // Show sidebar and loading state
                sidebar.classList.add('active');
                sidebar.querySelector('.sidebar-loader').style.display = 'block';
                sidebar.querySelector('.product-info').style.display = 'none';
                
                // Fetch product details from our API endpoint
                fetch(`/shop/product/${productId}/sidebar-detail/?format=json`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Network response was not ok');
                        }
                        return response.json();
                    })
                    .then(data => {
                        const productInfo = sidebar.querySelector('.product-info');
                        
                        // Build HTML content for the sidebar
                        let content = `
                            <h2>${data.name}</h2>
                            <div class="price">${data.price}</div>
                        `;
                        
                        // Image slider
                        if (data.images.length > 0) {
                            content += `
                                <div class="image-slider">
                                    <div class="slider-container">
                            `;
                            
                            data.images.forEach(image => {
                                content += `<div class="slide"><img src="${image.url}" alt="${data.name}"></div>`;
                            });
                            
                            content += `
                                    </div>
                                    <div class="slider-nav">
                                        <button class="prev-slide">&lt;</button>
                                        <button class="next-slide">&gt;</button>
                                    </div>
                                </div>
                            `;
                        } else {
                            content += `<div class="no-image">No images available</div>`;
                        }
                        
                        // Basic info
                        content += `
                            <div class="basic-info">
                                <p><strong>Category:</strong> ${data.category}</p>
                                <p><strong>Supplier:</strong> ${data.supplier || 'N/A'}</p>
                                <p><strong>Status:</strong> ${data.is_active ? 'Active' : 'Inactive'}</p>
                            </div>
                            
                            <div class="description">
                                <h4>Description</h4>
                                <p>${data.description || 'No description available'}</p>
                            </div>
                        `;
                        
                        // Attributes
                        if (data.attributes.length > 0) {
                            content += `
                                <div class="attributes">
                                    <h4>Attributes</h4>
                                    <ul>
                            `;
                            
                            data.attributes.forEach(attr => {
                                content += `<li><strong>${attr.key}:</strong> ${attr.value}</li>`;
                            });
                            
                            content += `
                                    </ul>
                                </div>
                            `;
                        }
                        
                        // Add edit button
                        content += `
                            <div class="sidebar-actions">
                                <a href="/admin/shop/product/${productId}/change/" class="button">Edit Product</a>
                            </div>
                        `;
                        
                        productInfo.innerHTML = content;
                        
                        // Hide loader and show product info
                        sidebar.querySelector('.sidebar-loader').style.display = 'none';
                        productInfo.style.display = 'block';
                        
                        // Initialize image slider
                        if (data.images.length > 1) {
                            initImageSlider();
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching product details:', error);
                        const productInfo = sidebar.querySelector('.product-info');
                        productInfo.innerHTML = '<p>Error loading product details</p>';
                        sidebar.querySelector('.sidebar-loader').style.display = 'none';
                        productInfo.style.display = 'block';
                    });
            });
            
            // Change cursor to indicate clickable
            cell.style.cursor = 'pointer';
        });
    }
    
    // Image slider functionality
    function initImageSlider() {
        const slider = document.querySelector('.slider-container');
        const slides = document.querySelectorAll('.slide');
        const prevBtn = document.querySelector('.prev-slide');
        const nextBtn = document.querySelector('.next-slide');
        
        if (!slider || slides.length <= 1) return;
        
        let currentSlide = 0;
        
        function showSlide(index) {
            if (index < 0) index = slides.length - 1;
            if (index >= slides.length) index = 0;
            
            slider.style.transform = `translateX(-${index * 100}%)`;
            currentSlide = index;
        }
        
        prevBtn.addEventListener('click', e => {
            e.stopPropagation();
            showSlide(currentSlide - 1);
        });
        
        nextBtn.addEventListener('click', e => {
            e.stopPropagation();
            showSlide(currentSlide + 1);
        });
        
        // Initialize first slide
        showSlide(0);
    }
    
    // Handle dynamic rows added by AJAX (e.g., after pagination or filtering)
    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            if (mutation.type === 'childList' && mutation.addedNodes.length) {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeName === 'TR') {
                        makeRowClickable(node);
                    }
                });
            }
        });
    });
    
    // Observe the table body for changes
    const tableBody = resultList.querySelector('tbody');
    if (tableBody) {
        observer.observe(tableBody, { childList: true, subtree: true });
    }
}); 