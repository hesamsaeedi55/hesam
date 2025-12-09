/**
 * Dynamic tag loading based on category selection
 */
document.addEventListener('DOMContentLoaded', function() {
    // Get the category select and tag select elements
    const categorySelect = document.getElementById('id_category') || document.querySelector('select[name="category"]');
    const tagSelect = document.querySelector('#id_tags') || document.querySelector('select[name="tags"]');
    
    if (!categorySelect || !tagSelect) {
        console.error('Category or tag select elements not found.');
        return;
    }
    
    // Get the category tags data from the template
    const categoryTagsData = JSON.parse(document.getElementById('category-tags-data')?.textContent || '{}');
    const selectedTagsData = JSON.parse(document.getElementById('selected-tags-data')?.textContent || '[]');
    
    // Function to fetch tags for a category
    function fetchTagsForCategory(categoryId) {
        if (!categoryId) {
            // Clear tags if no category is selected
            clearTags();
            return;
        }
        
        // If we have the tags data in the template, use it
        if (categoryTagsData[categoryId]) {
            updateTagOptions(categoryTagsData[categoryId]);
            return;
        }
        
        // Otherwise, fetch from the server
        const url = `/shop/get-tags-for-category/?category_id=${categoryId}`;
        
        // Make the AJAX request
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    console.error('Error from server:', data.error);
                    return;
                }
                updateTagOptions(data.tags);
            })
            .catch(error => {
                console.error('Error fetching tags:', error);
            });
    }
    
    // Function to update tag options
    function updateTagOptions(tags) {
        // Clear existing options
        clearTags();
        
        // Add new options
        tags.forEach(tag => {
            const option = document.createElement('option');
            option.value = tag.id;
            option.textContent = tag.name;
            
            // If this tag was previously selected, select it again
            if (selectedTagsData.includes(tag.id)) {
                option.selected = true;
            }
            
            tagSelect.appendChild(option);
        });
        
        // If Select2 is available, refresh it
        if (typeof $ !== 'undefined' && $.fn.select2) {
            // Destroy existing Select2 instance if it exists
            if ($(tagSelect).data('select2')) {
                $(tagSelect).select2('destroy');
            }
            
            // Initialize Select2
            $(tagSelect).select2({
                placeholder: 'انتخاب برچسب‌ها',
                allowClear: true,
                width: '100%',
                multiple: true,
                templateResult: formatTagOption,
                templateSelection: formatTagOption
            });
            
            // Trigger change to update Select2 with current selections
            $(tagSelect).trigger('change');
        }
    }
    
    // Function to format tag options in Select2
    function formatTagOption(tag) {
        if (!tag.id) {
            return tag.text;
        }
        
        const $tag = $(
            '<span class="select2-selection__choice">' +
            '<span class="select2-selection__choice__remove" role="presentation">×</span>' +
            '<span class="select2-selection__choice__display">' + tag.text + '</span>' +
            '</span>'
        );
        
        return $tag;
    }
    
    // Function to clear tag options
    function clearTags() {
        // Remove all options
        while (tagSelect.options.length > 0) {
            tagSelect.remove(0);
        }
    }
    
    // Initial load of tags if a category is already selected (edit mode)
    if (categorySelect.value) {
        fetchTagsForCategory(categorySelect.value);
    }
    
    // Add change event listener to category select
    categorySelect.addEventListener('change', function() {
        fetchTagsForCategory(this.value);
    });
    
    // Initialize Select2 for tags if available
    if (typeof $ !== 'undefined' && $.fn.select2) {
        $(tagSelect).select2({
            placeholder: 'انتخاب برچسب‌ها',
            allowClear: true,
            width: '100%',
            multiple: true,
            templateResult: formatTagOption,
            templateSelection: formatTagOption
        });
    }
});