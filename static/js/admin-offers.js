/**
 * Admin Special Offers Management JavaScript
 * Handles CRUD operations, UI interactions, and data management
 */

class AdminOffersManager {
    constructor() {
        this.apiBase = '/shop/api/admin';
        this.publicApiBase = '/shop/api';
        this.currentOffers = [];
        this.selectedOffers = new Set();
        this.editingOffer = null;
        this.availableProducts = [];
        this.selectedProducts = new Map(); // productId -> {discount_percentage, discount_amount}
        
        // Initialize immediately since we're called from DOMContentLoaded
        this.initializeAfterDOMReady();
    }

    initializeAfterDOMReady() {
        console.log('Initializing AdminOffersManager...');
        this.loadOffers();
        this.loadStats();
        this.setupEventListeners();
        this.loadProducts();
    }

    async loadOffers() {
        try {
            console.log('Loading offers from API...');
            const response = await fetch(`${this.apiBase}/special-offers/`);
            const data = await response.json();
            
            console.log('API Response:', data);
            
            if (data.success) {
                this.offers = data.offers || [];
                this.currentOffers = this.offers;
                console.log(`Loaded ${this.offers.length} offers`);
                this.renderOffers();
                this.updateStats();
            } else {
                console.error('Failed to load offers:', data.error);
                this.showToast('خطا در بارگذاری پیشنهادات', 'error');
            }
        } catch (error) {
            console.error('Error loading offers:', error);
            this.showToast('خطا در بارگذاری پیشنهادات', 'error');
        }
    }

    async loadStats() {
        // Load statistics if needed
        // This can be implemented later
    }

    setupEventListeners() {
        // Setup any event listeners if needed
        // This can be implemented later
    }

    async loadProducts() {
        try {
            const response = await fetch(`${this.publicApiBase}/products/?per_page=100`);
            const data = await response.json();
            
            if (data.products) {
                this.availableProducts = data.products;
            }
        } catch (error) {
            console.error('Error loading products:', error);
        }
    }

    renderOffers() {
        console.log('Rendering offers...');
        const tbody = document.getElementById('offers-tbody');
        const loading = document.getElementById('loading');
        const table = document.getElementById('offers-table');
        
        console.log('Found elements:', { tbody: !!tbody, loading: !!loading, table: !!table });
        
        if (!tbody) {
            console.error('offers-tbody element not found!');
            return;
        }
        
        // Hide loading, show table
        if (loading) loading.style.display = 'none';
        if (table) table.style.display = 'block';
        
        if (!this.offers || this.offers.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; padding: 40px; color: #666;">
                        <i class="fas fa-inbox" style="font-size: 48px; margin-bottom: 16px; color: #ddd;"></i>
                        <p>هیچ پیشنهادی یافت نشد</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = this.offers.map(offer => `
            <tr>
                <td>
                    <input type="checkbox" value="${offer.id}" onchange="adminOffers.toggleSelection(${offer.id})">
                </td>
                <td>
                    <span class="offer-type-badge ${offer.offer_type}">
                        ${this.getOfferTypeDisplay(offer.offer_type)}
                    </span>
                </td>
                <td>
                    <div style="max-width: 200px;">
                        <div style="font-weight: 600; margin-bottom: 4px;">${offer.title}</div>
                        <div style="color: #718096; font-size: 0.9rem;">${offer.description || ''}</div>
                    </div>
                </td>
                <td>
                    <span class="status-badge">
                        ${this.getDisplayStyleDisplay(offer.display_style)}
                    </span>
                </td>
                <td>
                    <button class="product-count-btn" onclick="adminOffers.manageProducts(${offer.id})" 
                            title="مدیریت محصولات">
                        <i class="fas fa-box"></i>
                        <span style="font-weight: 600;">${offer.products?.length || 0} محصول</span>
                    </button>
                </td>
                <td>
                    <span style="color: #4299e1; font-weight: 600;">${offer.views_count || 0}</span>
                </td>
                <td>
                    <span style="color: #48bb78; font-weight: 600;">${offer.clicks_count || 0}</span>
                </td>
                <td>
                    <span class="status-badge ${this.getStatusClass(offer)}">
                        ${this.getStatusDisplay(offer)}
                    </span>
                </td>
                <td>
                    <div class="action-buttons">

                        <button class="action-btn action-edit" onclick="adminOffers.editOffer(${offer.id})" 
                                title="ویرایش">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="action-btn action-products" onclick="adminOffers.manageProducts(${offer.id})" 
                                title="مدیریت محصولات">
                            <i class="fas fa-box"></i>
                        </button>
                        <button class="action-btn action-toggle" onclick="adminOffers.toggleOffer(${offer.id})" 
                                title="تغییر وضعیت">
                            <i class="fas fa-toggle-${offer.enabled ? 'on' : 'off'}"></i>
                        </button>
                        <button class="action-btn action-delete" onclick="adminOffers.deleteOffer(${offer.id})" 
                                title="حذف">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    getOfferTypeDisplay(type) {
        const types = {
            'flash_sale': '⚡ فروش ویژه',
            'discount': '💰 تخفیف',
            'bundle': '🎁 پکیج',
            'free_shipping': '📦 ارسال رایگان',
            'seasonal': '🌟 فصلی',
            'clearance': '🏷️ حراج',
            'coupon': '🎫 کوپن'
        };
        return types[type] || type;
    }

    getDisplayStyleDisplay(style) {
        const styles = {
            'hero_banner': 'بنر اصلی',
            'carousel': 'کاروسل',
            'grid': 'شبکه‌ای',
            'sidebar': 'نوار کناری',
            'popup': 'پاپ‌آپ'
        };
        return styles[style] || style;
    }

    getStatusClass(offer) {
        if (!offer.enabled) return 'inactive';
        
        // Use backend's is_currently_valid if available, otherwise calculate
        if (offer.is_currently_valid !== undefined) {
            return offer.is_currently_valid ? 'active' : 'expired';
        }
        
        // Fallback to date comparison with proper timezone handling
        const now = new Date();
        const validFrom = new Date(offer.valid_from);
        const validUntil = offer.valid_until ? new Date(offer.valid_until) : null;
        
        if (now < validFrom) return 'pending';
        if (validUntil && now > validUntil) return 'expired';
        return 'active';
    }

    getStatusDisplay(offer) {
        const statusClass = this.getStatusClass(offer);
        const statuses = {
            'active': 'فعال',
            'inactive': 'غیرفعال',
            'pending': 'در انتظار',
            'expired': 'منقضی'
        };
        return statuses[statusClass] || statusClass;
    }

    toggleSelection(offerId) {
        if (this.selectedOffers.has(offerId)) {
            this.selectedOffers.delete(offerId);
        } else {
            this.selectedOffers.add(offerId);
        }
        this.updateBulkActions();
    }

    updateBulkActions() {
        const bulkDelete = document.getElementById('bulk-delete');
        const bulkToggle = document.getElementById('bulk-toggle');
        const hasSelection = this.selectedOffers.size > 0;
        
        if (bulkDelete) bulkDelete.style.display = hasSelection ? 'inline-block' : 'none';
        if (bulkToggle) bulkToggle.style.display = hasSelection ? 'inline-block' : 'none';
    }

    async toggleOffer(offerId) {
        try {
            const offer = this.offers.find(o => o.id === offerId);
            if (!offer) return;
            
            const response = await fetch(`${this.apiBase}/special-offers/${offerId}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ enabled: !offer.enabled })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast(`پیشنهاد ${offer.enabled ? 'غیرفعال' : 'فعال'} شد`, 'success');
                this.loadOffers();
            } else {
                throw new Error(data.error || 'خطا در تغییر وضعیت');
            }
        } catch (error) {
            console.error('Error toggling offer:', error);
            this.showToast('خطا در تغییر وضعیت: ' + error.message, 'error');
        }
    }

    async deleteOffer(offerId) {
        if (!confirm('آیا از حذف این پیشنهاد اطمینان دارید؟')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBase}/special-offers/${offerId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('پیشنهاد با موفقیت حذف شد', 'success');
                this.loadOffers();
            } else {
                throw new Error(data.error || 'خطا در حذف پیشنهاد');
            }
        } catch (error) {
            console.error('Error deleting offer:', error);
            this.showToast('خطا در حذف پیشنهاد: ' + error.message, 'error');
        }
    }

    manageProducts(offerId) {
        const offer = this.offers.find(o => o.id === offerId);
        if (!offer) return;
        
        this.editingOffer = offer;
        this.loadProductsForOffer(offer);
        document.getElementById('products-modal').style.display = 'flex';
    }

    async loadProductsForOffer(offer) {
        // Load products and mark selected ones
        this.selectedProducts.clear();
        
        // Mark products that are in this offer
        if (offer.products) {
            offer.products.forEach(product => {
                this.selectedProducts.set(product.product.id, {
                    discount_percentage: product.discount_percentage || 0,
                    discount_amount: product.discount_amount || 0
                });
            });
        }
        
        this.renderProductsList();
    }

    renderProductsList() {
        const container = document.getElementById('products-list');
        if (!container) return;
        
        if (!this.availableProducts || this.availableProducts.length === 0) {
            container.innerHTML = '<p>در حال بارگذاری محصولات...</p>';
            return;
        }
        
        container.innerHTML = this.availableProducts.map(product => {
            const isSelected = this.selectedProducts.has(product.id);
            const discount = isSelected ? this.selectedProducts.get(product.id) : { discount_percentage: 0, discount_amount: 0 };
            
            return `
                <div class="product-item ${isSelected ? 'selected' : ''}">
                    <div class="product-info">
                        <input type="checkbox" ${isSelected ? 'checked' : ''} 
                               onchange="adminOffers.toggleProductSelection(${product.id})">
                        <div class="product-details">
                            <h4>${product.name}</h4>
                            <p>قیمت: ${product.price_toman} تومان</p>
                        </div>
                    </div>

                </div>
            `;
        }).join('');
    }

    toggleProductSelection(productId) {
        if (this.selectedProducts.has(productId)) {
            this.selectedProducts.delete(productId);
        } else {
            this.selectedProducts.set(productId, {
                discount_percentage: 0,
                discount_amount: 0
            });
        }
        this.renderProductsList();
    }



    closeProductsModal() {
        document.getElementById('products-modal').style.display = 'none';
        this.editingOffer = null;
        this.selectedProducts.clear();
    }

    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        const bgColor = {
            'success': '#10b981',
            'error': '#ef4444', 
            'warning': '#f59e0b',
            'info': '#3b82f6'
        }[type] || '#3b82f6';
        
        toast.style.cssText = `
            background: ${bgColor};
            color: white;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease;
            direction: rtl;
            text-align: right;
        `;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        }, 10);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }

    applyFilters() {
        const typeFilter = document.getElementById('filter-type')?.value || '';
        const statusFilter = document.getElementById('filter-status')?.value || '';
        const displayFilter = document.getElementById('filter-display')?.value || '';
        
        let filtered = [...this.offers];
        
        if (typeFilter) {
            filtered = filtered.filter(offer => offer.offer_type === typeFilter);
        }
        
        if (statusFilter) {
            filtered = filtered.filter(offer => {
                const status = this.getStatusClass(offer);
                return status === statusFilter;
            });
        }
        
        if (displayFilter) {
            filtered = filtered.filter(offer => offer.display_style === displayFilter);
        }
        
        // Temporarily store original offers and render filtered
        const originalOffers = this.offers;
        this.offers = filtered;
        this.renderOffers();
        this.offers = originalOffers;
    }

    clearFilters() {
        document.getElementById('filter-type').value = '';
        document.getElementById('filter-status').value = '';
        document.getElementById('filter-display').value = '';
        this.renderOffers();
    }

    toggleSelectAll() {
        const selectAll = document.getElementById('select-all');
        const checkboxes = document.querySelectorAll('#offers-tbody input[type="checkbox"]');
        
        if (selectAll.checked) {
            checkboxes.forEach(cb => {
                cb.checked = true;
                this.selectedOffers.add(parseInt(cb.value));
            });
        } else {
            checkboxes.forEach(cb => {
                cb.checked = false;
                this.selectedOffers.delete(parseInt(cb.value));
            });
        }
        
        this.updateBulkActions();
    }

    async bulkDelete() {
        if (this.selectedOffers.size === 0) return;
        
        if (!confirm(`آیا از حذف ${this.selectedOffers.size} پیشنهاد انتخاب شده اطمینان دارید؟`)) {
            return;
        }
        
        const promises = Array.from(this.selectedOffers).map(offerId => 
            fetch(`${this.apiBase}/special-offers/${offerId}/`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': this.getCSRFToken() }
            })
        );
        
        try {
            await Promise.all(promises);
            this.showToast('پیشنهادات انتخاب شده حذف شدند', 'success');
            this.selectedOffers.clear();
            this.loadOffers();
        } catch (error) {
            this.showToast('خطا در حذف پیشنهادات', 'error');
        }
    }

    async bulkToggle() {
        if (this.selectedOffers.size === 0) return;
        
        const promises = Array.from(this.selectedOffers).map(offerId => {
            const offer = this.offers.find(o => o.id === offerId);
            return fetch(`${this.apiBase}/special-offers/${offerId}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ enabled: !offer.enabled })
            });
        });
        
        try {
            await Promise.all(promises);
            this.showToast('وضعیت پیشنهادات تغییر کرد', 'success');
            this.selectedOffers.clear();
            this.loadOffers();
        } catch (error) {
            this.showToast('خطا در تغییر وضعیت', 'error');
        }
    }

    updateStats() {
        // Update statistics display
        // This can be implemented later
    }

    setupEventListeners() {
        // Filter change events (only if elements exist)
        const filterType = document.getElementById('filter-type');
        const filterStatus = document.getElementById('filter-status');
        const filterDisplay = document.getElementById('filter-display');
        
        if (filterType) {
            filterType.addEventListener('change', () => this.applyFilters());
        }
        if (filterStatus) {
            filterStatus.addEventListener('change', () => this.applyFilters());
        }
        if (filterDisplay) {
            filterDisplay.addEventListener('change', () => this.applyFilters());
        }
        
        console.log('Event listeners setup completed');

        // Modal events
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
                this.closeProductsModal();
            }
        });

        // Form validation
        document.getElementById('offer_type').addEventListener('change', this.updateFormValidation.bind(this));
        document.getElementById('banner_action_type').addEventListener('change', this.toggleBannerFields.bind(this));
    }

    // Data Loading
    async loadOffers() {
        try {
            this.showLoading(true);
            
            const response = await fetch(`${this.apiBase}/special-offers/`);
            const data = await response.json();
            
            if (data.success) {
                this.currentOffers = data.offers;
                this.renderOffers(this.currentOffers);
                this.updateStats();
            } else {
                throw new Error('Failed to load offers');
            }
        } catch (error) {
            console.error('Error loading offers:', error);
            this.showToast('خطا در بارگذاری پیشنهادات', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async loadStats() {
        try {
            // Calculate stats from current offers
            const stats = this.calculateStats();
            this.updateStatsDisplay(stats);
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async loadProducts() {
        try {
            const response = await fetch(`${this.publicApiBase}/products/`);
            const data = await response.json();
            
            // Handle both success format and direct products array
            if (data.success) {
                this.availableProducts = data.products || [];
            } else if (Array.isArray(data.products)) {
                this.availableProducts = data.products;
            } else if (Array.isArray(data)) {
                this.availableProducts = data;
            } else {
                this.availableProducts = [];
            }
            
            console.log('Loaded products:', this.availableProducts.length);
        } catch (error) {
            console.error('Error loading products:', error);
            this.availableProducts = [];
        }
    }

    // Rendering
    renderOffers(offers) {
        const tbody = document.getElementById('offers-tbody');
        const table = document.getElementById('offers-table');
        const emptyState = document.getElementById('empty-state');

        if (!offers || offers.length === 0) {
            table.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }

        table.style.display = 'block';
        emptyState.style.display = 'none';

        tbody.innerHTML = offers.map(offer => `
            <tr data-offer-id="${offer.id}">
                <td>
                    <input type="checkbox" class="offer-checkbox" value="${offer.id}" 
                           onchange="adminOffers.toggleSelection(${offer.id})">
                </td>
                <td>
                    <span style="font-weight: 600; color: #4299e1;">#${offer.id}</span>
                </td>
                <td>
                    <span class="type-badge type-${offer.offer_type}">
                        ${this.getOfferTypeDisplay(offer.offer_type)}
                    </span>
                </td>
                <td>
                    <div>
                        <strong>${offer.title}</strong>
                        <div style="color: #718096; font-size: 0.9rem;">${offer.description || ''}</div>
                    </div>
                </td>
                <td>
                    <span class="status-badge">
                        ${this.getDisplayStyleDisplay(offer.display_style)}
                    </span>
                </td>
                <td>
                    <button class="product-count-btn" onclick="adminOffers.manageProducts(${offer.id})" 
                            title="مدیریت محصولات">
                        <i class="fas fa-box"></i>
                        <span style="font-weight: 600;">${offer.products.length} محصول</span>
                    </button>
                </td>
                <td>
                    <span style="color: #4299e1; font-weight: 600;">${offer.views_count || 0}</span>
                </td>
                <td>
                    <span style="color: #48bb78; font-weight: 600;">${offer.clicks_count || 0}</span>
                </td>
                <td>
                    <span class="status-badge ${this.getStatusClass(offer)}">
                        ${this.getStatusDisplay(offer)}
                    </span>
                </td>
                <td>
                    <div class="action-buttons">

                        <button class="action-btn action-edit" onclick="adminOffers.editOffer(${offer.id})" 
                                title="ویرایش">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="action-btn action-products" onclick="adminOffers.manageProducts(${offer.id})" 
                                title="مدیریت محصولات">
                            <i class="fas fa-box"></i>
                        </button>
                        <button class="action-btn action-toggle" onclick="adminOffers.toggleOffer(${offer.id})" 
                                title="تغییر وضعیت">
                            <i class="fas fa-toggle-${offer.enabled ? 'on' : 'off'}"></i>
                        </button>
                        <button class="action-btn action-delete" onclick="adminOffers.deleteOffer(${offer.id})" 
                                title="حذف">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    // CRUD Operations
    async createOffer(formData) {
        try {
            const response = await fetch(`${this.apiBase}/special-offers/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                this.showToast('پیشنهاد با موفقیت ایجاد شد', 'success');
                this.closeModal();
                this.loadOffers();
                return data.offer;
            } else {
                throw new Error(data.error || 'خطا در ایجاد پیشنهاد');
            }
        } catch (error) {
            console.error('Error creating offer:', error);
            this.showToast('خطا در ایجاد پیشنهاد: ' + error.message, 'error');
            throw error;
        }
    }

    async updateOffer(offerId, formData) {
        try {
            const response = await fetch(`${this.apiBase}/special-offers/${offerId}/`, {
                method: 'PUT',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                this.showToast('پیشنهاد با موفقیت بروزرسانی شد', 'success');
                this.closeModal();
                this.loadOffers();
                return data.offer;
            } else {
                throw new Error(data.error || 'خطا در بروزرسانی پیشنهاد');
            }
        } catch (error) {
            console.error('Error updating offer:', error);
            this.showToast('خطا در بروزرسانی پیشنهاد: ' + error.message, 'error');
            throw error;
        }
    }

    async deleteOffer(offerId) {
        if (!confirm('آیا از حذف این پیشنهاد اطمینان دارید؟')) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/special-offers/${offerId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showToast('پیشنهاد با موفقیت حذف شد', 'success');
                this.loadOffers();
            } else {
                throw new Error(data.error || 'خطا در حذف پیشنهاد');
            }
        } catch (error) {
            console.error('Error deleting offer:', error);
            this.showToast('خطا در حذف پیشنهاد: ' + error.message, 'error');
        }
    }

    async toggleOffer(offerId) {
        try {
            const offer = this.currentOffers.find(o => o.id === offerId);
            if (!offer) return;

            const response = await fetch(`${this.apiBase}/special-offers/${offerId}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    enabled: !offer.enabled
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showToast(`پیشنهاد ${offer.enabled ? 'غیرفعال' : 'فعال'} شد`, 'success');
                this.loadOffers();
            } else {
                throw new Error(data.error || 'خطا در تغییر وضعیت');
            }
        } catch (error) {
            console.error('Error toggling offer:', error);
            this.showToast('خطا در تغییر وضعیت: ' + error.message, 'error');
        }
    }

    // UI Actions
    openCreateModal() {
        this.editingOffer = null;
        this.clearForm();
        document.getElementById('modal-title').textContent = 'ایجاد پیشنهاد جدید';
        this.showModal();
    }

    editOffer(offerId) {
        const offer = this.currentOffers.find(o => o.id === offerId);
        if (!offer) return;

        this.editingOffer = offer;
        this.populateForm(offer);
        document.getElementById('modal-title').textContent = 'ویرایش پیشنهاد';
        this.showModal();
    }



    manageProducts(offerId) {
        const offer = this.currentOffers.find(o => o.id === offerId);
        if (!offer) return;

        this.editingOffer = offer;
        this.populateProductsModal(offer);
        this.showProductsModal();
    }



    // Form Management
    resetForm() {
        document.getElementById('offer-form').reset();
        document.getElementById('enabled').checked = true;
        document.getElementById('is_active').checked = true;
        
        // Set default datetime
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        document.getElementById('valid_from').value = now.toISOString().slice(0, 16);
    }

    populateForm(offer) {
        document.getElementById('title').value = offer.title || '';
        document.getElementById('description').value = offer.description || '';
        document.getElementById('offer_type').value = offer.offer_type || '';
        document.getElementById('display_style').value = offer.display_style || '';
        document.getElementById('display_order').value = offer.display_order || 1;
        document.getElementById('banner_action_type').value = offer.banner_action_type || 'none';
        document.getElementById('banner_external_url').value = offer.banner_external_url || '';
        document.getElementById('enabled').checked = offer.enabled;
        document.getElementById('is_active').checked = offer.is_active;

        // Convert UTC datetime to local
        if (offer.valid_from) {
            const fromDate = new Date(offer.valid_from);
            fromDate.setMinutes(fromDate.getMinutes() - fromDate.getTimezoneOffset());
            document.getElementById('valid_from').value = fromDate.toISOString().slice(0, 16);
        }

        if (offer.valid_until) {
            const untilDate = new Date(offer.valid_until);
            untilDate.setMinutes(untilDate.getMinutes() - untilDate.getTimezoneOffset());
            document.getElementById('valid_until').value = untilDate.toISOString().slice(0, 16);
        }

        this.updateFormValidation();
        this.toggleBannerFields();
    }

    validateForm(formData) {
        const title = formData.get('title');
        const offerType = formData.get('offer_type');
        const displayStyle = formData.get('display_style');
        const validFrom = formData.get('valid_from');

        if (!title || !offerType || !displayStyle || !validFrom) {
            this.showToast('لطفاً تمام فیلدهای اجباری را پر کنید', 'error');
            return false;
        }

        return true;
    }

    formDataToJSON(formData) {
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            if (key === 'enabled' || key === 'is_active') {
                data[key] = document.getElementById(key).checked;
            } else if (value) {
                data[key] = value;
            }
        }

        return data;
    }

    updateFormValidation() {
        const offerType = document.getElementById('offer_type').value;
        
        // Show/hide fields based on offer type
        // Add specific validation logic if needed
    }

    toggleBannerFields() {
        const actionType = document.getElementById('banner_action_type').value;
        const urlField = document.getElementById('banner_external_url').parentElement;
        
        if (actionType === 'url') {
            urlField.style.display = 'block';
            document.getElementById('banner_external_url').required = true;
        } else {
            urlField.style.display = 'none';
            document.getElementById('banner_external_url').required = false;
        }
    }

    // Products Management
    populateProductsModal(offer) {
        this.selectedProducts.clear();
        
        // Pre-select products from the offer
        offer.products.forEach(product => {
            this.selectedProducts.set(product.product.id, {
                discount_percentage: product.discount_percentage || 0,
                discount_amount: product.discount_amount || 0
            });
        });

        this.renderProductsList();
    }

    renderProductsList() {
        const container = document.getElementById('products-list');
        
        container.innerHTML = this.availableProducts.map(product => {
            const isSelected = this.selectedProducts.has(product.id);
            const discount = this.selectedProducts.get(product.id) || { discount_percentage: 0, discount_amount: 0 };
            
            return `
                <div class="product-item">
                    <input type="checkbox" class="product-select" 
                           ${isSelected ? 'checked' : ''} 
                           onchange="adminOffers.toggleProduct(${product.id})">
                    <div class="product-info">
                        <div class="product-name">${product.name}</div>
                        <div class="product-price">${this.formatPrice(product.price_toman)} تومان</div>
                    </div>
                    <div class="discount-controls">
                        <div class="discount-group">
                            <label>درصد تخفیف:</label>
                            <input type="number" class="discount-input" 
                                   value="${discount.discount_percentage}" min="0" max="100"
                                   oninput="adminOffers.updateDiscountAndCalculate(${product.id}, this.value, ${product.price_toman})">
                            <span>%</span>
                        </div>
                        <div class="price-group">
                            <label>قیمت با تخفیف:</label>
                            <input type="number" class="price-display" 
                                   value="${product.price_toman * (1 - (discount.discount_percentage || 0) / 100)}" 
                                   readonly>
                            <span>تومان</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    toggleProduct(productId) {
        if (this.selectedProducts.has(productId)) {
            this.selectedProducts.delete(productId);
        } else {
            this.selectedProducts.set(productId, {
                discount_percentage: 0,
                discount_amount: 0
            });
        }
    }

    searchProducts(searchTerm) {
        const filteredProducts = this.availableProducts.filter(product => 
            product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (product.description && product.description.toLowerCase().includes(searchTerm.toLowerCase()))
        );
        this.renderFilteredProductsList(filteredProducts);
    }

    selectAllProducts() {
        this.availableProducts.forEach(product => {
            if (!this.selectedProducts.has(product.id)) {
                this.selectedProducts.set(product.id, {
                    discount_percentage: 0,
                    discount_amount: 0
                });
            }
        });
        this.renderProductsList();
        this.showToast(`${this.availableProducts.length} محصول انتخاب شد`, 'success');
    }

    clearSelection() {
        this.selectedProducts.clear();
        this.renderProductsList();
        this.showToast('انتخاب محصولات پاک شد', 'info');
    }

    renderFilteredProductsList(products) {
        const container = document.getElementById('products-list');
        
        container.innerHTML = products.map(product => {
            const isSelected = this.selectedProducts.has(product.id);
            const discount = this.selectedProducts.get(product.id) || { discount_percentage: 0, discount_amount: 0 };
            
            return `
                <div class="product-item">
                    <input type="checkbox" class="product-select" 
                           ${isSelected ? 'checked' : ''} 
                           onchange="adminOffers.toggleProduct(${product.id})">
                    <div class="product-info">
                        <div class="product-name">${product.name}</div>
                        <div class="product-price">${this.formatPrice(product.price_toman || 0)} تومان</div>
                        <div class="product-description" style="font-size: 0.8rem; color: #718096;">
                            ${product.description ? product.description.substring(0, 100) + '...' : 'بدون توضیحات'}
                        </div>
                    </div>
                    <div class="discount-controls">
                        <div class="discount-group">
                            <label>درصد تخفیف:</label>
                            <input type="number" class="discount-input" 
                                   value="${discount.discount_percentage}" min="0" max="100"
                                   oninput="adminOffers.updateDiscountAndCalculate(${product.id}, this.value, ${product.price_toman})">
                            <span>%</span>
                        </div>
                        <div class="price-group">
                            <label>قیمت با تخفیف:</label>
                            <input type="number" class="price-display" 
                                   value="${(product.price_toman || 0) * (1 - (discount.discount_percentage || 0) / 100)}" 
                                   readonly>
                            <span>تومان</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }





    updateDiscount(productId, type, value) {
        const discount = this.selectedProducts.get(productId) || { discount_percentage: 0, discount_amount: 0 };
        
        if (type === 'percentage') {
            discount.discount_percentage = parseInt(value) || 0;
        }
        
        this.selectedProducts.set(productId, discount);
    }

    calculateDiscountedPrice(originalPrice, discountPercentage) {
        if (!originalPrice || !discountPercentage) return originalPrice || 0;
        const price = parseFloat(originalPrice);
        const percentage = parseFloat(discountPercentage);
        const discountedPrice = price * (1 - percentage / 100);
        return Math.round(discountedPrice);
    }

    updateDiscountAndCalculate(productId, discountPercentage, originalPrice) {
        // Update the discount
        this.updateDiscount(productId, 'percentage', discountPercentage);
        
        // Calculate and update the discounted price field
        const discountedPrice = this.calculateDiscountedPrice(originalPrice, discountPercentage);
        
        // Find the specific price display field for this product
        const productItem = document.querySelector(`[oninput*="updateDiscountAndCalculate(${productId}"]`);
        if (productItem) {
            const priceField = productItem.closest('.product-item').querySelector('.price-display');
            if (priceField) {
                priceField.value = discountedPrice;
                
                // Visual feedback
                if (discountPercentage > 0) {
                    priceField.style.backgroundColor = '#d4edda';
                    priceField.style.borderColor = '#28a745';
                    priceField.style.color = '#155724';
                    priceField.style.fontWeight = 'bold';
                } else {
                    priceField.style.backgroundColor = '#f8f9fa';
                    priceField.style.borderColor = '#dee2e6';
                    priceField.style.color = '#495057';
                    priceField.style.fontWeight = 'normal';
                }
            }
        }
    }

    async saveProducts() {
        if (!this.editingOffer) return;

        try {
            const products = Array.from(this.selectedProducts.entries()).map(([productId, discount]) => ({
                product_id: productId,
                discount_percentage: discount.discount_percentage,
                discount_amount: discount.discount_amount
            }));

            const response = await fetch(`${this.apiBase}/special-offers/${this.editingOffer.id}/products/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ products })
            });

            const data = await response.json();

            if (data.success) {
                this.showToast('محصولات با موفقیت ذخیره شد', 'success');
                this.closeProductsModal();
                this.loadOffers();
            } else {
                throw new Error(data.error || 'خطا در ذخیره محصولات');
            }
        } catch (error) {
            console.error('Error saving products:', error);
            this.showToast('خطا در ذخیره محصولات: ' + error.message, 'error');
        }
    }

    // Filtering
    applyFilters() {
        const typeFilter = document.getElementById('filter-type').value;
        const statusFilter = document.getElementById('filter-status').value;
        const displayFilter = document.getElementById('filter-display').value;

        let filteredOffers = [...this.currentOffers];

        if (typeFilter) {
            filteredOffers = filteredOffers.filter(offer => offer.offer_type === typeFilter);
        }

        if (statusFilter) {
            filteredOffers = filteredOffers.filter(offer => {
                switch (statusFilter) {
                    case 'active':
                        return offer.enabled && offer.is_active && offer.is_currently_valid;
                    case 'inactive':
                        return !offer.enabled || !offer.is_active;
                    case 'expired':
                        return !offer.is_currently_valid;
                    default:
                        return true;
                }
            });
        }

        if (displayFilter) {
            filteredOffers = filteredOffers.filter(offer => offer.display_style === displayFilter);
        }

        this.renderOffers(filteredOffers);
    }

    clearFilters() {
        document.getElementById('filter-type').value = '';
        document.getElementById('filter-status').value = '';
        document.getElementById('filter-display').value = '';
        this.renderOffers(this.currentOffers);
    }

    // Selection Management
    toggleSelection(offerId) {
        if (this.selectedOffers.has(offerId)) {
            this.selectedOffers.delete(offerId);
        } else {
            this.selectedOffers.add(offerId);
        }

        this.updateBulkActions();
    }

    toggleSelectAll() {
        const checkbox = document.getElementById('select-all');
        const checkboxes = document.querySelectorAll('.offer-checkbox');
        
        checkboxes.forEach(cb => {
            cb.checked = checkbox.checked;
            const offerId = parseInt(cb.value);
            
            if (checkbox.checked) {
                this.selectedOffers.add(offerId);
            } else {
                this.selectedOffers.delete(offerId);
            }
        });

        this.updateBulkActions();
    }

    updateBulkActions() {
        const bulkDelete = document.getElementById('bulk-delete');
        const bulkToggle = document.getElementById('bulk-toggle');
        const hasSelection = this.selectedOffers.size > 0;

        bulkDelete.style.display = hasSelection ? 'inline-flex' : 'none';
        bulkToggle.style.display = hasSelection ? 'inline-flex' : 'none';
    }

    async bulkDelete() {
        if (this.selectedOffers.size === 0) return;
        
        if (!confirm(`آیا از حذف ${this.selectedOffers.size} پیشنهاد انتخاب شده اطمینان دارید؟`)) {
            return;
        }

        try {
            const promises = Array.from(this.selectedOffers).map(offerId => 
                this.deleteOffer(offerId)
            );
            
            await Promise.all(promises);
            this.selectedOffers.clear();
            this.updateBulkActions();
            
        } catch (error) {
            console.error('Error in bulk delete:', error);
        }
    }

    async bulkToggle() {
        if (this.selectedOffers.size === 0) return;

        try {
            const promises = Array.from(this.selectedOffers).map(offerId => 
                this.toggleOffer(offerId)
            );
            
            await Promise.all(promises);
            this.selectedOffers.clear();
            this.updateBulkActions();
            
        } catch (error) {
            console.error('Error in bulk toggle:', error);
        }
    }

    // Stats and Analytics
    calculateStats() {
        const activeOffers = this.currentOffers.filter(offer => 
            offer.enabled && offer.is_active && offer.is_currently_valid
        );
        
        const totalViews = this.currentOffers.reduce((sum, offer) => 
            sum + (offer.views_count || 0), 0
        );
        
        const totalClicks = this.currentOffers.reduce((sum, offer) => 
            sum + (offer.clicks_count || 0), 0
        );

        // Calculate estimated revenue (simplified)
        const estimatedRevenue = totalClicks * 50000; // Assuming average order value

        return {
            activeCount: activeOffers.length,
            totalViews,
            totalClicks,
            estimatedRevenue
        };
    }

    updateStats() {
        const stats = this.calculateStats();
        this.updateStatsDisplay(stats);
    }

    updateStatsDisplay(stats) {
        document.getElementById('active-count').textContent = stats.activeCount;
        document.getElementById('total-views').textContent = this.formatNumber(stats.totalViews);
        document.getElementById('total-clicks').textContent = this.formatNumber(stats.totalClicks);
        document.getElementById('revenue').textContent = this.formatPrice(stats.estimatedRevenue);
    }

    // Modal Management
    showModal() {
        document.getElementById('offer-modal').classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        document.getElementById('offer-modal').classList.remove('show');
        document.body.style.overflow = '';
        this.editingOffer = null;
    }

    showProductsModal() {
        document.getElementById('products-modal').classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    closeProductsModal() {
        document.getElementById('products-modal').classList.remove('show');
        document.body.style.overflow = '';
    }

    // UI Helpers
    showLoading(show) {
        document.getElementById('loading').style.display = show ? 'block' : 'none';
        document.getElementById('offers-table').style.display = show ? 'none' : 'block';
    }

    showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="fas fa-${this.getToastIcon(type)}"></i>
            <span>${message}</span>
        `;

        container.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => container.removeChild(toast), 300);
        }, 3000);
    }

    getToastIcon(type) {
        const icons = {
            'success': 'check-circle',
            'error': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    // Utility Functions
    getOfferTypeDisplay(type) {
        const types = {
            'flash_sale': '⚡ فروش ویژه',
            'discount': '💰 تخفیف',
            'bundle': '🎁 پکیج',
            'free_shipping': '📦 ارسال رایگان',
            'seasonal': '🌟 فصلی',
            'clearance': '🏷️ حراج',
            'coupon': '🎫 کوپن'
        };
        return types[type] || type;
    }

    getDisplayStyleDisplay(style) {
        const styles = {
            'hero_banner': 'بنر اصلی',
            'carousel': 'کاروسل',
            'grid': 'شبکه‌ای'
        };
        return styles[style] || style;
    }

    getStatusClass(offer) {
        if (!offer.enabled || !offer.is_active) return 'status-inactive';
        if (!offer.is_currently_valid) return 'status-expired';
        return 'status-active';
    }

    getStatusDisplay(offer) {
        if (!offer.enabled || !offer.is_active) return 'غیرفعال';
        if (!offer.is_currently_valid) return 'منقضی';
        return 'فعال';
    }

    formatPrice(price) {
        return new Intl.NumberFormat('fa-IR').format(price);
    }

    formatNumber(number) {
        return new Intl.NumberFormat('fa-IR').format(number);
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    // Modal management






    clearForm() {
        const form = document.getElementById('offer-form');
        if (form) {
            form.reset();
        }
    }



    populateForm(offer) {
        // Populate form fields with offer data
        const fields = ['title', 'description', 'offer_type', 'display_style', 
                       'banner_action_type', 'banner_action_target', 'banner_external_url',
                       'valid_from', 'valid_until', 'enabled', 'is_active', 'display_order'];
        
        fields.forEach(field => {
            const element = document.getElementById(field);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = offer[field] || false;
                } else if (field.includes('valid_') && offer[field]) {
                    // Format datetime for datetime-local input
                    const date = new Date(offer[field]);
                    element.value = date.toISOString().slice(0, 16);
                } else {
                    element.value = offer[field] || '';
                }
            }
        });
    }

    collectFormData() {
        const formData = new FormData();
        const fields = ['title', 'description', 'offer_type', 'display_style', 
                       'banner_action_type', 'banner_action_target', 'banner_external_url',
                       'valid_from', 'valid_until', 'enabled', 'is_active', 'display_order'];
        
        fields.forEach(field => {
            const element = document.getElementById(field);
            if (element) {
                if (element.type === 'checkbox') {
                    formData.append(field, element.checked ? 'true' : 'false');
                } else if (element.type === 'number') {
                    formData.append(field, parseInt(element.value) || 0);
                } else {
                    formData.append(field, element.value || '');
                }
            }
        });
        
        // Handle file upload
        const bannerImageElement = document.getElementById('banner_image');
        if (bannerImageElement && bannerImageElement.files.length > 0) {
            formData.append('banner_image', bannerImageElement.files[0]);
        }
        
        return formData;
    }

    async saveOffer() {
        try {
            const formData = this.collectFormData();
            
            // Validate required fields
            if (!formData.get('title') || !formData.get('offer_type') || !formData.get('display_style') || !formData.get('valid_from')) {
                this.showToast('لطفاً تمام فیلدهای الزامی را پر کنید', 'error');
                return;
            }
            
            if (this.editingOffer) {
                // Update existing offer
                await this.updateOffer(this.editingOffer.id, formData);
            } else {
                // Create new offer
                await this.createOffer(formData);
            }
        } catch (error) {
            console.error('Error saving offer:', error);
        }
    }

    // Public methods for global access
    refreshOffers() {
        this.loadOffers();
        this.showToast('پیشنهادات بروزرسانی شد', 'info');
    }
}

// Global functions for onclick handlers
window.openCreateModal = () => window.adminOffers?.openCreateModal();
window.editOffer = (offerId) => window.adminOffers?.editOffer(offerId);
window.refreshOffers = () => window.adminOffers?.refreshOffers();
window.closeModal = () => window.adminOffers?.closeModal();
window.closeProductsModal = () => window.adminOffers?.closeProductsModal();
window.saveOffer = () => window.adminOffers?.saveOffer();
window.saveProducts = () => window.adminOffers?.saveProducts();
window.addProduct = () => window.adminOffers?.addProduct();
window.clearFilters = () => window.adminOffers?.clearFilters();
window.toggleSelectAll = () => window.adminOffers?.toggleSelectAll();
window.bulkDelete = () => window.adminOffers?.bulkDelete();
window.bulkToggle = () => window.adminOffers?.bulkToggle();

// Additional global functions

window.toggleOffer = (offerId) => window.adminOffers?.toggleOffer(offerId);
window.deleteOffer = (offerId) => window.adminOffers?.deleteOffer(offerId);
window.manageProducts = (offerId) => window.adminOffers?.manageProducts(offerId);
