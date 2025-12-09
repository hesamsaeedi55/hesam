/**
 * Modern Special Offers JavaScript
 * Handles dynamic loading, interactions, and animations
 */

class ModernOffersManager {
    constructor() {
        this.apiBase = '/shop/api';
        this.currentOffers = [];
        this.countdownTimers = new Map();
        this.modal = null;
        
        this.init();
    }

    init() {
        this.setupDOM();
        this.loadOffers();
        this.setupEventListeners();
        this.setupIntersectionObserver();
    }

    setupDOM() {
        // Create modal if it doesn't exist
        if (!document.getElementById('offers-modal')) {
            this.createModal();
        }
        
        // Add loading states
        this.showLoading();
    }

    createModal() {
        const modalHTML = `
            <div id="offers-modal" class="modal-overlay">
                <div class="modal-content">
                    <button class="modal-close" onclick="offersManager.closeModal()">
                        <i class="fas fa-times"></i>
                    </button>
                    <div id="modal-body">
                        <!-- Content will be dynamically loaded -->
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('offers-modal');
        
        // Close modal on overlay click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.closeModal();
            }
        });
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-offers');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshOffers());
        }

        // Filter buttons
        document.querySelectorAll('[data-filter]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filter = e.target.dataset.filter;
                this.filterOffers(filter);
            });
        });

        // Keyboard events
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                this.closeModal();
            }
        });

        // Scroll to top functionality
        window.addEventListener('scroll', this.handleScroll.bind(this));
    }

    setupIntersectionObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in');
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '50px'
        });

        // Observe offer cards for animation
        setTimeout(() => {
            document.querySelectorAll('.offer-card').forEach(card => {
                observer.observe(card);
            });
        }, 100);
    }

    async loadOffers() {
        try {
            this.showLoading();
            
            const response = await fetch(`${this.apiBase}/special-offers/`);
            const data = await response.json();
            
            if (data.success && data.offers) {
                this.currentOffers = data.offers;
                this.renderOffers(data.offers);
                this.showToast('پیشنهادات با موفقیت بارگذاری شد', 'success');
            } else {
                throw new Error('Failed to load offers');
            }
        } catch (error) {
            console.error('Error loading offers:', error);
            this.showError('خطا در بارگذاری پیشنهادات. لطفاً دوباره تلاش کنید.');
        } finally {
            this.hideLoading();
        }
    }

    renderOffers(offers) {
        if (!offers || offers.length === 0) {
            this.showEmptyState();
            return;
        }

        // Render hero offer
        const heroOffer = offers.find(offer => 
            offer.display_style === 'hero_banner' || offer.offer_type === 'flash_sale'
        ) || offers[0];
        
        if (heroOffer) {
            this.renderHeroOffer(heroOffer);
        }

        // Render other offers
        const otherOffers = offers.filter(offer => offer.id !== heroOffer.id);
        this.renderOfferCards(otherOffers);

        // Setup animations
        setTimeout(() => this.setupIntersectionObserver(), 100);
    }

    renderHeroOffer(offer) {
        const heroContainer = document.getElementById('hero-offer');
        if (!heroContainer) return;

        const remainingTime = offer.remaining_time;
        const offerType = offer.offer_type;
        
        heroContainer.innerHTML = `
            <div class="hero-card ${offerType}" onclick="offersManager.openOfferModal('${offer.id}')">
                <div class="hero-content">
                    <div class="hero-text">
                        <div class="hero-badge">
                            <i class="${this.getOfferIcon(offerType)}"></i>
                            ${this.getOfferTypeBadge(offerType)}
                        </div>
                        <h1 class="hero-title">${offer.title}</h1>
                        <p class="hero-description">${offer.description}</p>
                        
                        ${remainingTime && remainingTime > 0 ? `
                            <div class="hero-timer">
                                <i class="fas fa-clock"></i>
                                <div class="countdown-timer">
                                    <div class="time-unit">
                                        <span class="time-number" id="hours-${offer.id}">00</span>
                                        <span class="time-label">ساعت</span>
                                    </div>
                                    <div class="time-unit">
                                        <span class="time-number" id="minutes-${offer.id}">00</span>
                                        <span class="time-label">دقیقه</span>
                                    </div>
                                    <div class="time-unit">
                                        <span class="time-number" id="seconds-${offer.id}">00</span>
                                        <span class="time-label">ثانیه</span>
                                    </div>
                                </div>
                            </div>
                        ` : `
                            <div class="hero-timer">
                                <i class="fas fa-box"></i>
                                ${offer.products.length} محصول در این پیشنهاد
                            </div>
                        `}
                    </div>
                    <div class="hero-icon-container">
                        <i class="hero-icon ${this.getOfferIcon(offerType)}"></i>
                        <a href="#" class="hero-cta" onclick="event.stopPropagation(); offersManager.openOfferModal('${offer.id}')">
                            مشاهده جزئیات
                        </a>
                    </div>
                </div>
            </div>
        `;

        // Start countdown if needed
        if (remainingTime && remainingTime > 0) {
            this.startCountdown(offer.id, remainingTime);
        }
    }

    renderOfferCards(offers) {
        const gridContainer = document.getElementById('offers-grid');
        if (!gridContainer) return;

        gridContainer.innerHTML = offers.map((offer, index) => `
            <div class="offer-card" 
                 onclick="offersManager.openOfferModal('${offer.id}')"
                 style="animation-delay: ${index * 0.1}s">
                <div class="offer-card-header ${offer.offer_type}">
                    <div class="floating-shapes">
                        <div class="floating-shape"></div>
                        <div class="floating-shape"></div>
                        <div class="floating-shape"></div>
                    </div>
                    <i class="card-icon ${this.getOfferIcon(offer.offer_type)}"></i>
                </div>
                <div class="offer-card-body">
                    <h3 class="offer-title">${offer.title}</h3>
                    <p class="offer-description">${offer.description}</p>
                    
                    ${offer.remaining_time && offer.remaining_time > 0 ? `
                        <div class="countdown-timer mb-3">
                            <div class="time-unit">
                                <span class="time-number" id="card-hours-${offer.id}">00</span>
                                <span class="time-label">ساعت</span>
                            </div>
                            <div class="time-unit">
                                <span class="time-number" id="card-minutes-${offer.id}">00</span>
                                <span class="time-label">دقیقه</span>
                            </div>
                        </div>
                    ` : ''}
                    
                    <div class="offer-meta">
                        <span class="product-count">
                            <i class="fas fa-box"></i>
                            ${offer.products.length} محصول
                        </span>
                        <div class="offer-arrow">
                            <i class="fas fa-arrow-left"></i>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        // Start countdowns for cards
        offers.forEach(offer => {
            if (offer.remaining_time && offer.remaining_time > 0) {
                this.startCountdown(`card-${offer.id}`, offer.remaining_time, true);
            }
        });
    }

    async openOfferModal(offerId) {
        try {
            // Track click
            await this.trackOfferClick(offerId);
            
            // Find offer data
            const offer = this.currentOffers.find(o => o.id == offerId);
            if (!offer) {
                this.showError('پیشنهاد مورد نظر یافت نشد');
                return;
            }

            // Render modal content
            const modalBody = document.getElementById('modal-body');
            modalBody.innerHTML = `
                <div class="modal-header mb-4">
                    <h2 class="modal-title">${offer.title}</h2>
                    <p class="modal-description">${offer.description}</p>
                    
                    ${offer.remaining_time && offer.remaining_time > 0 ? `
                        <div class="hero-timer">
                            <i class="fas fa-clock"></i>
                            <div class="countdown-timer">
                                <div class="time-unit">
                                    <span class="time-number" id="modal-hours-${offer.id}">00</span>
                                    <span class="time-label">ساعت</span>
                                </div>
                                <div class="time-unit">
                                    <span class="time-number" id="modal-minutes-${offer.id}">00</span>
                                    <span class="time-label">دقیقه</span>
                                </div>
                                <div class="time-unit">
                                    <span class="time-number" id="modal-seconds-${offer.id}">00</span>
                                    <span class="time-label">ثانیه</span>
                                </div>
                            </div>
                        </div>
                    ` : ''}
                </div>
                
                <div class="modal-products-grid">
                    ${offer.products.slice(0, 8).map(product => `
                        <div class="modal-product-card" onclick="offersManager.viewProduct(${product.product.id})">
                            <img src="${product.product.images[0]?.url || '/static/images/placeholder.jpg'}" 
                                 alt="${product.product.name}" 
                                 class="modal-product-image"
                                 onerror="this.src='/static/images/placeholder.jpg'">
                            <h4 class="modal-product-name">${product.product.name}</h4>
                            <div class="modal-product-discount">${product.discount_display}</div>
                            <div class="product-price">
                                ${product.discounted_price ? `
                                    <span class="original-price">${this.formatPrice(product.original_price)}</span>
                                    <span class="discounted-price">${this.formatPrice(product.discounted_price)}</span>
                                ` : `
                                    <span class="current-price">${this.formatPrice(product.product.price_toman)}</span>
                                `}
                            </div>
                        </div>
                    `).join('')}
                </div>
                
                ${offer.products.length > 8 ? `
                    <div class="text-center mb-4">
                        <button class="btn btn-primary" onclick="offersManager.viewAllProducts('${offer.id}')">
                            مشاهده همه محصولات (${offer.products.length})
                        </button>
                    </div>
                ` : ''}
            `;

            // Show modal
            this.modal.classList.add('show');
            document.body.style.overflow = 'hidden';

            // Start countdown in modal if needed
            if (offer.remaining_time && offer.remaining_time > 0) {
                this.startCountdown(`modal-${offer.id}`, offer.remaining_time);
            }

        } catch (error) {
            console.error('Error opening modal:', error);
            this.showError('خطا در نمایش جزئیات پیشنهاد');
        }
    }

    closeModal() {
        this.modal.classList.remove('show');
        document.body.style.overflow = '';
        
        // Clear modal countdowns
        this.countdownTimers.forEach((timer, key) => {
            if (key.includes('modal-')) {
                clearInterval(timer);
                this.countdownTimers.delete(key);
            }
        });
    }

    startCountdown(offerId, remainingSeconds, isCard = false) {
        const prefix = isCard ? 'card-' : '';
        const hoursEl = document.getElementById(`${prefix}hours-${offerId}`);
        const minutesEl = document.getElementById(`${prefix}minutes-${offerId}`);
        const secondsEl = document.getElementById(`${prefix}seconds-${offerId}`);

        if (!hoursEl && !minutesEl && !secondsEl) return;

        let timeLeft = remainingSeconds;
        
        const updateDisplay = () => {
            const hours = Math.floor(timeLeft / 3600);
            const minutes = Math.floor((timeLeft % 3600) / 60);
            const seconds = timeLeft % 60;

            if (hoursEl) hoursEl.textContent = hours.toString().padStart(2, '0');
            if (minutesEl) minutesEl.textContent = minutes.toString().padStart(2, '0');
            if (secondsEl) secondsEl.textContent = seconds.toString().padStart(2, '0');
        };

        // Initial display
        updateDisplay();

        // Start timer
        const timer = setInterval(() => {
            timeLeft--;
            
            if (timeLeft <= 0) {
                clearInterval(timer);
                this.countdownTimers.delete(`${prefix}${offerId}`);
                
                // Show expired state
                if (hoursEl) hoursEl.textContent = '00';
                if (minutesEl) minutesEl.textContent = '00';
                if (secondsEl) secondsEl.textContent = '00';
                
                this.showToast('زمان پیشنهاد به پایان رسید', 'warning');
                return;
            }
            
            updateDisplay();
        }, 1000);

        this.countdownTimers.set(`${prefix}${offerId}`, timer);
    }

    async trackOfferClick(offerId) {
        try {
            await fetch(`${this.apiBase}/special-offers/${offerId}/click/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
        } catch (error) {
            console.error('Error tracking click:', error);
        }
    }

    async refreshOffers() {
        this.showToast('در حال بروزرسانی...', 'info');
        await this.loadOffers();
    }

    filterOffers(filterType) {
        const filteredOffers = filterType === 'all' 
            ? this.currentOffers 
            : this.currentOffers.filter(offer => offer.offer_type === filterType);
        
        this.renderOffers(filteredOffers);
        this.showToast(`فیلتر ${this.getOfferTypeBadge(filterType)} اعمال شد`, 'info');
    }

    viewProduct(productId) {
        window.location.href = `/shop/product/${productId}/`;
    }

    viewAllProducts(offerId) {
        window.location.href = `/shop/offers/${offerId}/products/`;
    }

    // Utility functions
    getOfferTypeBadge(type) {
        const badges = {
            'flash_sale': '⚡ فروش ویژه',
            'discount': '💰 تخفیف',
            'bundle': '🎁 پکیج',
            'free_shipping': '📦 ارسال رایگان',
            'seasonal': '🌟 فصلی',
            'clearance': '🏷️ حراج',
            'coupon': '🎫 کوپن'
        };
        return badges[type] || '✨ ویژه';
    }

    getOfferIcon(type) {
        const icons = {
            'flash_sale': 'fas fa-bolt',
            'discount': 'fas fa-percentage',
            'bundle': 'fas fa-gift',
            'free_shipping': 'fas fa-shipping-fast',
            'seasonal': 'fas fa-leaf',
            'clearance': 'fas fa-tags',
            'coupon': 'fas fa-ticket-alt'
        };
        return icons[type] || 'fas fa-star';
    }

    formatPrice(price) {
        return new Intl.NumberFormat('fa-IR').format(price) + ' تومان';
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    // UI State Management
    showLoading() {
        const container = document.getElementById('offers-container');
        if (container) {
            container.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">در حال بارگذاری پیشنهادات...</div>
                </div>
            `;
        }
    }

    hideLoading() {
        // Content will be replaced by renderOffers
    }

    showEmptyState() {
        const container = document.getElementById('offers-container');
        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="empty-icon fas fa-gift"></i>
                    <h2 class="empty-title">هیچ پیشنهاد ویژه‌ای موجود نیست</h2>
                    <p class="empty-description">به زودی پیشنهادات جدیدی اضافه خواهد شد</p>
                    <button class="btn btn-primary" onclick="offersManager.refreshOffers()">
                        بروزرسانی
                    </button>
                </div>
            `;
        }
    }

    showToast(message, type = 'success') {
        // Remove existing toast
        const existingToast = document.querySelector('.toast');
        if (existingToast) {
            existingToast.remove();
        }

        // Create new toast
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${this.getToastIcon(type)}"></i>
            <span>${message}</span>
        `;

        document.body.appendChild(toast);

        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);

        // Auto hide
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    showError(message) {
        this.showToast(message, 'error');
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

    handleScroll() {
        const scrollBtn = document.getElementById('scroll-to-top');
        if (scrollBtn) {
            if (window.scrollY > 300) {
                scrollBtn.classList.add('show');
            } else {
                scrollBtn.classList.remove('show');
            }
        }
    }

    scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    }
}

// Initialize when DOM is ready
let offersManager;
document.addEventListener('DOMContentLoaded', () => {
    offersManager = new ModernOffersManager();
});

// Export for global access
window.offersManager = offersManager;
