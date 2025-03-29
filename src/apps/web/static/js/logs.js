/**
 * Neo Web Chat Logs JavaScript
 * 
 * Handles the interactivity for log entries:
 * - Expanding/collapsing log entries
 * - Truncating and expanding complex data types 
 * - Drilling down into nested objects and arrays
 */

document.addEventListener('DOMContentLoaded', function() {
    // Add click handlers to all log entry headers
    document.querySelectorAll('.log-entry-header').forEach(header => {
        header.addEventListener('click', function() {
            // Toggle expanded class on the parent log entry
            const logEntry = this.closest('.log-entry');
            logEntry.classList.toggle('expanded');
            
            // Toggle visibility of content
            const content = logEntry.querySelector('.log-entry-content');
            if (content) {
                if (logEntry.classList.contains('expanded')) {
                    content.style.display = 'block';
                } else {
                    content.style.display = 'none';
                }
            }
        });
    });
    
    // Initially hide all content sections
    document.querySelectorAll('.log-entry-content').forEach(content => {
        content.style.display = 'none';
    });

    // Add click handlers to expandable field values
    document.querySelectorAll('.field-value-toggle').forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent parent handlers from firing
            
            // Determine if we're in truncated or full view based on where the button is
            const isInTruncated = this.closest('.truncated-value') !== null;
            const isInFull = this.closest('.full-value') !== null;
            
            // Get the value container that contains both views
            const valueContainer = this.closest('.field-value-container');
            if (!valueContainer) return;
            
            // Get the truncated and full value elements
            const truncatedValue = valueContainer.querySelector('.truncated-value');
            const fullValue = valueContainer.querySelector('.full-value');
            
            if (!truncatedValue || !fullValue) return;
            
            // Toggle visibility based on which view we're in
            if (isInTruncated) {
                // We're in truncated view, expand to full view
                truncatedValue.style.display = 'none';
                fullValue.style.display = 'block';
            } else if (isInFull) {
                // We're in full view, collapse to truncated view
                truncatedValue.style.display = 'block';
                fullValue.style.display = 'none';
            }
        });
    });
    
    // Initialize all field-value-containers
    document.querySelectorAll('.field-value-container').forEach(container => {
        const truncatedValue = container.querySelector('.truncated-value');
        const fullValue = container.querySelector('.full-value');
        
        if (truncatedValue && fullValue) {
            // Initially show truncated, hide full
            truncatedValue.style.display = 'block';
            fullValue.style.display = 'none';
        }
    });

    // Add click handlers to object property toggles
    document.querySelectorAll('.object-property-toggle').forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent parent handlers from firing
            const property = this.closest('.object-property');
            property.classList.toggle('expanded');
            
            // Update the toggle icon
            const icon = this.querySelector('i');
            if (property.classList.contains('expanded')) {
                icon.classList.remove('fa-plus');
                icon.classList.add('fa-minus');
            } else {
                icon.classList.remove('fa-minus');
                icon.classList.add('fa-plus');
            }
        });
    });
});

/**
 * Formats a JSON object or array for display with collapsible sections
 * 
 * @param {Object|Array} data - The data to format
 * @param {number} maxDepth - Maximum depth to expand by default
 * @param {number} currentDepth - Current depth in the nested structure
 * @returns {string} HTML markup for displaying the data
 */
function formatComplexData(data, maxDepth = 1, currentDepth = 0) {
    if (data === null) return '<span class="null-value">null</span>';
    
    const isExpanded = currentDepth < maxDepth;
    
    if (Array.isArray(data)) {
        if (data.length === 0) return '[]';
        
        if (currentDepth >= maxDepth) {
            return `<span class="array-preview">[Array: ${data.length} items]</span>`;
        }
        
        let html = '<div class="array-container">';
        data.forEach((item, index) => {
            html += `<div class="array-item">
                <div class="array-index">[${index}]</div>
                <div class="array-value">${formatComplexData(item, maxDepth, currentDepth + 1)}</div>
            </div>`;
        });
        html += '</div>';
        return html;
    }
    
    if (typeof data === 'object') {
        const keys = Object.keys(data);
        if (keys.length === 0) return '{}';
        
        if (currentDepth >= maxDepth) {
            return `<span class="object-preview">{Object: ${keys.length} properties}</span>`;
        }
        
        let html = '<div class="object-container">';
        keys.forEach(key => {
            const value = data[key];
            const isComplex = typeof value === 'object' && value !== null;
            
            html += `<div class="object-property ${isExpanded ? 'expanded' : ''}">
                <div class="object-property-toggle">
                    ${isComplex ? `<i class="fas ${isExpanded ? 'fa-minus' : 'fa-plus'}"></i>` : ''}
                    <span class="property-key">${key}:</span>
                </div>
                <div class="property-value">${formatComplexData(value, maxDepth, currentDepth + 1)}</div>
            </div>`;
        });
        html += '</div>';
        return html;
    }
    
    if (typeof data === 'string') {
        // Escape HTML and add quotes
        return `<span class="string-value">"${escapeHtml(data)}"</span>`;
    }
    
    if (typeof data === 'number') {
        return `<span class="number-value">${data}</span>`;
    }
    
    if (typeof data === 'boolean') {
        return `<span class="boolean-value">${data}</span>`;
    }
    
    return String(data);
}

/**
 * Escape HTML special characters
 * 
 * @param {string} text - Text to escape
 * @returns {string} Escaped HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
