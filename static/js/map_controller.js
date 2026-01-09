// Global variables
let dates = [];
let currentIndex = 0;

// Initialize the application
document.addEventListener('DOMContentLoaded', async () => {
    await loadDates();
    setupEventListeners();
    updateDownloadControls();
});

// Load available dates from API
async function loadDates() {
    try {
        const response = await fetch('/api/dates');
        const data = await response.json();
        dates = data.dates;
        
        if (dates.length > 0) {
            // Set slider max value
            const slider = document.getElementById('timeSlider');
            slider.max = dates.length - 1;
            slider.value = dates.length - 1; // Start with most recent date
            currentIndex = dates.length - 1;
            
            // Update date displays
            document.getElementById('startDate').textContent = formatDate(dates[0]);
            document.getElementById('endDate').textContent = formatDate(dates[dates.length - 1]);
            
            // Set date input ranges
            document.getElementById('startDateInput').value = dates[0];
            document.getElementById('endDateInput').value = dates[dates.length - 1];
            document.getElementById('startDateInput').min = dates[0];
            document.getElementById('startDateInput').max = dates[dates.length - 1];
            document.getElementById('endDateInput').min = dates[0];
            document.getElementById('endDateInput').max = dates[dates.length - 1];
            
            // Load initial map
            await loadMap(dates[currentIndex]);
        }
    } catch (error) {
        console.error('Error loading dates:', error);
        showError('Error al cargar las fechas disponibles');
    }
}

// Load map for specific date
async function loadMap(date) {
    try {
        const mapContainer = document.getElementById('map');
        mapContainer.innerHTML = '<div class="loading"><div class="spinner"></div><p>Cargando mapa...</p></div>';
        
        const response = await fetch(`/api/map/${date}`);
        if (response.ok) {
            const html = await response.text();
            mapContainer.innerHTML = html;
            
            // Update current date display
            document.getElementById('currentDate').textContent = formatDate(date);
        } else {
            throw new Error('Error loading map');
        }
    } catch (error) {
        console.error('Error loading map:', error);
        showError('Error al cargar el mapa');
    }
}

// Format date for display
function formatDate(dateStr) {
    const date = new Date(dateStr);
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return date.toLocaleDateString('es-ES', options);
}

// Setup event listeners
function setupEventListeners() {
    // Time slider
    const slider = document.getElementById('timeSlider');
    slider.addEventListener('input', (e) => {
        currentIndex = parseInt(e.target.value);
        loadMap(dates[currentIndex]);
    });
    
    // Previous button
    document.getElementById('prevBtn').addEventListener('click', () => {
        if (currentIndex > 0) {
            currentIndex--;
            slider.value = currentIndex;
            loadMap(dates[currentIndex]);
        }
    });
    
    // Next button
    document.getElementById('nextBtn').addEventListener('click', () => {
        if (currentIndex < dates.length - 1) {
            currentIndex++;
            slider.value = currentIndex;
            loadMap(dates[currentIndex]);
        }
    });
    
    // Download type selector
    document.getElementById('downloadType').addEventListener('change', updateDownloadControls);
    
    // Download button
    document.getElementById('downloadBtn').addEventListener('click', handleDownload);
    
    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft' && currentIndex > 0) {
            currentIndex--;
            slider.value = currentIndex;
            loadMap(dates[currentIndex]);
        } else if (e.key === 'ArrowRight' && currentIndex < dates.length - 1) {
            currentIndex++;
            slider.value = currentIndex;
            loadMap(dates[currentIndex]);
        }
    });
}

// Update download controls visibility
function updateDownloadControls() {
    const downloadType = document.getElementById('downloadType').value;
    const countryGroup = document.getElementById('countryGroup');
    const dateRangeGroup = document.getElementById('dateRangeGroup');
    
    // Show/hide country selector
    if (downloadType === 'single' || downloadType === 'range_single') {
        countryGroup.style.display = 'flex';
    } else {
        countryGroup.style.display = 'none';
    }
    
    // Show/hide date range inputs
    if (downloadType === 'range_single' || downloadType === 'range_all') {
        dateRangeGroup.style.display = 'grid';
    } else {
        dateRangeGroup.style.display = 'none';
    }
}

// Handle download
function handleDownload() {
    const downloadType = document.getElementById('downloadType').value;
    const country = document.getElementById('countrySelect').value;
    const currentDate = dates[currentIndex];
    const startDate = document.getElementById('startDateInput').value;
    const endDate = document.getElementById('endDateInput').value;
    
    let url = '';
    
    switch (downloadType) {
        case 'single':
            url = `/api/download/country/${country}/${currentDate}`;
            break;
        case 'all':
            url = `/api/download/all/${currentDate}`;
            break;
        case 'range_single':
            if (!startDate || !endDate) {
                alert('Por favor selecciona las fechas de inicio y fin');
                return;
            }
            url = `/api/download/range/${country}/${startDate}/${endDate}`;
            break;
        case 'range_all':
            if (!startDate || !endDate) {
                alert('Por favor selecciona las fechas de inicio y fin');
                return;
            }
            url = `/api/download/range/all/${startDate}/${endDate}`;
            break;
    }
    
    // Trigger download
    window.location.href = url;
}

// Show error message
function showError(message) {
    const mapContainer = document.getElementById('map');
    mapContainer.innerHTML = `
        <div class="loading">
            <p style="color: #e74c3c; font-size: 1.2rem;">❌ ${message}</p>
        </div>
    `;
}
