// Billing invoice creation JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const loadLessonsBtn = document.getElementById('load-lessons-btn');
    if (loadLessonsBtn) {
        loadLessonsBtn.addEventListener('click', function() {
            loadLessons();
        });
    }
});

function loadLessons() {
    const periodStartInput = document.querySelector('input[name="period_start"]');
    const periodEndInput = document.querySelector('input[name="period_end"]');
    const contractInput = document.querySelector('select[name="contract"]');
    
    if (!periodStartInput || !periodEndInput) {
        return;
    }
    
    const periodStart = periodStartInput.value;
    const periodEnd = periodEndInput.value;
    const contract = contractInput ? contractInput.value : '';
    
    if (!periodStart || !periodEnd) {
        // Get translation from data attribute or use fallback
        const alertMsg = document.getElementById('load-lessons-btn')?.dataset?.alertMsg || 'Please enter a period.';
        alert(alertMsg);
        return;
    }
    
    const url = new URL(window.location.href);
    url.searchParams.set('period_start', periodStart);
    url.searchParams.set('period_end', periodEnd);
    if (contract) {
        url.searchParams.set('contract', contract);
    }
    
    window.location.href = url.toString();
}

