/**
 * Deep Space Communication Dashboard
 * Main JavaScript file for the dashboard UI
 */

// ============================================================
// INITIALIZATION AND GLOBALS
// ============================================================

// Socket.IO connection
const socket = io({
    reconnectionAttempts: 5,
    timeout: 10000
});

// Chart references
let positionChart, velocityChart, temperatureChart, signalQualityChart;

// Spacecraft tracking
let currentSpacecraft = null;
let spacecraftList = [];

// Anomaly tracking
const seenAnomalies = new Set();
let anomalyCount = 0;
const ANOMALY_RETENTION_TIME = 24 * 60 * 60 * 1000; // 24 hours

// SOS alert handling
let sosModal = null;
const sosSound = document.getElementById('sos-alert-sound');
const acknowledgedAlerts = new Set();
let lastAlertTime = 0;
const ALERT_COOLDOWN = 60000; // 60 seconds minimum between alerts


// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Deep Space Communication Dashboard');
    
    // Initialize Bootstrap components
    initializeBootstrapComponents();
    
    // Initialize telemetry charts
    initializeCharts();
    
    // Initialize spacecraft selector
    initializeSpacecraftSelector();
    
    // Set up event handlers
    setupEventHandlers();
    
    // Start periodic updates
    startPeriodicUpdates();
    
    // Initial data fetch
    fetchAllData();
});

// ============================================================
// SOCKET.IO EVENT LISTENERS
// ============================================================

// Connection events
socket.on('connect', () => {
    console.log('Socket.IO connected');
    updateConnectionStatus('connected');
});

socket.on('disconnect', () => {
    console.log('Socket.IO disconnected');
    updateConnectionStatus('disconnected');
});

socket.on('connect_error', (error) => {
    console.error('Socket connection error:', error);
    updateConnectionStatus('error');
});

// Listen for telemetry updates


// New anomaly alert
socket.on('new_anomaly', (anomaly) => {
    console.log('New anomaly received:', anomaly);
    updateAnomalyLog([anomaly]);
});

socket.on('telemetry_update', (telemetry) => {
    if (telemetry.spacecraft_id === currentSpacecraft) {
        const timestamp = new Date(telemetry.timestamp * 1000);
        updateCharts(telemetry, timestamp);
        updateTelemetryDisplay(telemetry);
    }
});

// ============================================================
// INITIALIZATION FUNCTIONS
// ============================================================

function initializeBootstrapComponents() {
    // Initialize SOS modal
    sosModal = new bootstrap.Modal(document.getElementById('sos-modal'));
    
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}

function initializeCharts() {
    const chartOptions = {
        animation: {
            duration: 300
        },
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: {
                type: 'time',
                time: {
                    unit: 'minute',
                    tooltipFormat: 'HH:mm:ss',
                    displayFormats: {
                        minute: 'HH:mm:ss'
                    }
                },
                grid: {
                    color: '#333333'
                },
                ticks: {
                    color: '#cccccc'
                }
            },
            y: {
                grid: {
                    color: '#333333'
                },
                ticks: {
                    color: '#cccccc'
                }
            }
        },
        plugins: {
            legend: {
                labels: {
                    color: '#cccccc'
                }
            }
        }
    };
    
    // Position Chart
    positionChart = new Chart(
        document.getElementById('positionChart').getContext('2d'),
        {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'X Position (km)',
                        borderColor: '#ff6384',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        data: []
                    },
                    {
                        label: 'Y Position (km)',
                        borderColor: '#36a2eb',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        data: []
                    },
                    {
                        label: 'Z Position (km)',
                        borderColor: '#ffcd56',
                        backgroundColor: 'rgba(255, 205, 86, 0.2)',
                        data: []
                    }
                ]
            },
            options: chartOptions
        }
    );
    
    // Velocity Chart
    velocityChart = new Chart(
        document.getElementById('velocityChart').getContext('2d'),
        {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'X Velocity (km/s)',
                        borderColor: '#ff6384',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        data: []
                    },
                    {
                        label: 'Y Velocity (km/s)',
                        borderColor: '#36a2eb',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        data: []
                    },
                    {
                        label: 'Z Velocity (km/s)',
                        borderColor: '#ffcd56',
                        backgroundColor: 'rgba(255, 205, 86, 0.2)',
                        data: []
                    }
                ]
            },
            options: chartOptions
        }
    );
    
    // Temperature Chart
    temperatureChart = new Chart(
        document.getElementById('temperatureChart').getContext('2d'),
        {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'Temperature (°C)',
                        borderColor: '#ff9f40',
                        backgroundColor: 'rgba(255, 159, 64, 0.2)',
                        data: []
                    }
                ]
            },
            options: chartOptions
        }
    );
    
    // Signal Quality Chart
    signalQualityChart = new Chart(
        document.getElementById('signalQualityChart').getContext('2d'),
        {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'Signal Quality (%)',
                        borderColor: '#4bc0c0',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        data: []
                    },
                    {
                        label: 'Signal Delay (s)',
                        borderColor: '#9966ff',
                        backgroundColor: 'rgba(153, 102, 255, 0.2)',
                        data: [],
                        yAxisID: 'delay'
                    }
                ]
            },
            options: {
                ...chartOptions,
                scales: {
                    ...chartOptions.scales,
                    y: {
                        grid: {
                            color: '#333333'
                        },
                        ticks: {
                            color: '#cccccc'
                        },
                        min: 0,
                        max: 100
                    },
                    delay: {
                        position: 'right',
                        grid: {
                            color: '#333333'
                        },
                        ticks: {
                            color: '#cccccc'
                        },
                        min: 0
                    }
                }
            }
        }
    );
}

function initializeSpacecraftSelector() {
    const selector = document.getElementById('spacecraft-selector');
    if (!selector) {
        console.warn('Spacecraft selector not found');
        return;
    }
    
    selector.addEventListener('change', function() {
        currentSpacecraft = this.value;
        console.log('Selected spacecraft:', currentSpacecraft);
        
        // Update dashboard title
        const title = document.querySelector('.navbar-brand');
        if (title) {
            title.textContent = currentSpacecraft ? 
                `Deep Space Communication - ${currentSpacecraft}` : 
                'Deep Space Communication System';
        }
        
        // Fetch latest data for selected spacecraft
        fetchTelemetryForSpacecraft(currentSpacecraft);
        
        // Focus 3D visualization on selected spacecraft
        if (window.spacecraftViz && currentSpacecraft) {
            window.spacecraftViz.focusOnSpacecraft(currentSpacecraft);
        }
    });
}

function setupEventHandlers() {
    // Pause button
    const pauseButton = document.getElementById('pause-button');
    if (pauseButton) {
        pauseButton.addEventListener('click', function() {
            const isPaused = this.classList.contains('btn-success');
            
            fetch('/api/spacecraft/pause', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ paused: !isPaused })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    if (data.paused) {
                        this.innerHTML = '<i class="bi bi-play-fill"></i> Resume Spacecraft';
                        this.classList.remove('btn-warning');
                        this.classList.add('btn-success');
                        const indicator = document.getElementById('spacecraft-status');
                        if (indicator) indicator.textContent = 'PAUSED';
                    } else {
                        this.innerHTML = '<i class="bi bi-pause-fill"></i> Pause Spacecraft';
                        this.classList.remove('btn-success');
                        this.classList.add('btn-warning');
                        const indicator = document.getElementById('spacecraft-status');
                        if (indicator) indicator.textContent = 'OPERATING';
                    }
                }
            })
            .catch(error => console.error('Error toggling pause state:', error));
        });
    }
    
    // Tab switching
    document.querySelectorAll('#telemetryTabs .nav-link').forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('#telemetryTabs .nav-link').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('show', 'active'));
            document.querySelector(this.getAttribute('data-bs-target')).classList.add('show', 'active');
        });
    });
}

// ============================================================
// UPDATING FUNCTIONS
// ============================================================

function startPeriodicUpdates() {
    // Update mission time every second
    setInterval(updateMissionTime, 1000);
    
    // Fetch data every 2 seconds
    setInterval(fetchAllData, 2000);
    
    // Update spacecraft list every 10 seconds
    setInterval(updateSpacecraftList, 10000);
}

function updateMissionTime() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    
    const timeDisplay = document.getElementById('mission-timestamp');
    if (timeDisplay) {
        timeDisplay.textContent = `Mission Time: ${hours}:${minutes}:${seconds}`;
    }
}

function updateConnectionStatus(status) {
    const indicator = document.getElementById('connection-status');
    if (!indicator) return;
    
    indicator.innerHTML = '';
    
    if (status === 'connected') {
        indicator.innerHTML = '<span class="text-success">Connected</span>';
    } else if (status === 'disconnected') {
        indicator.innerHTML = '<span class="text-danger">Disconnected</span>';
    } else {
        indicator.innerHTML = '<span class="text-warning">Error</span>';
    }
}

function updateSpacecraftList() {
    fetch('/api/spacecraft/list')
        .then(response => response.json())
        .then(list => {
            if (!Array.isArray(list)) {
                console.error("Invalid spacecraft list response:", list);
                return;
            }
            
            spacecraftList = list;
            
            const selector = document.getElementById('spacecraft-selector');
            if (!selector) return;
            
            const currentValue = selector.value;
            selector.innerHTML = '';
            
            if (list.length > 1) {
                const defaultOption = document.createElement('option');
                defaultOption.textContent = '-- Select Spacecraft --';
                defaultOption.value = '';
                selector.appendChild(defaultOption);
            }
            
            list.forEach(id => {
                const option = document.createElement('option');
                option.textContent = id;
                option.value = id;
                selector.appendChild(option);
            });
            
            if (currentValue && list.includes(currentValue)) {
                selector.value = currentValue;
            } else if (list.length > 0 && (!currentValue || !list.includes(currentValue))) {
                selector.value = list[0];
                currentSpacecraft = list[0];
                
                // Focus the 3D visualization on the first spacecraft
                if (window.spacecraftViz && currentSpacecraft) {
                    window.spacecraftViz.focusOnSpacecraft(currentSpacecraft);
                }
                
                // Fetch data for the newly selected spacecraft
                fetchTelemetryForSpacecraft(currentSpacecraft);
            }
        })
        .catch(error => console.error('Error fetching spacecraft list:', error));
}


// ============================================================
// DATA FETCHING FUNCTIONS
// ============================================================

async function fetchAllData() {
    try {
        // Get latest telemetry for the current spacecraft
        if (currentSpacecraft) {
            await fetchTelemetryForSpacecraft(currentSpacecraft);
        }
        
        // Get system status
        const statusResponse = await fetch('/api/system/status');
        const status = await statusResponse.json();

        // Only show SOS alert if it's new (from edge processing)
        if (status.sos_required && status.sos_is_new === true) {  // Strict comparison with true
            console.log("New SOS alert detected:", status.sos_reason);
            showSosAlert(status.sos_reason || "Unknown emergency");
        }
        updateSystemStatusDisplay(status);
        
        // Get communication stats
        const commStatsResponse = await fetch('/api/comm/stats');
        const commStats = await commStatsResponse.json();
        updateCommStatsDisplay(commStats);
        
        // Get anomalies
        const anomaliesResponse = await fetch('/api/anomalies');
        const anomalies = await anomaliesResponse.json();
        updateAnomalyLog(anomalies);
        
        // Get autonomous decisions
        const decisionsResponse = await fetch('/api/autonomous/decisions');
        const decisions = await decisionsResponse.json();
        updateAutonomousDecisions(decisions);

        // Get space weather data
        const weatherResponse = await fetch('/api/space-weather');
        const weatherData = await weatherResponse.json();
        updateSpaceWeather(weatherData);
        
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
    }
}

async function fetchTelemetryForSpacecraft(spacecraftId) {
    if (!spacecraftId) return;
    
    try {
        const response = await fetch(`/api/telemetry/history?spacecraft_id=${spacecraftId}&limit=100`);
        const result = await response.json();

        const telemetryList = result[spacecraftId];
        if (!telemetryList || telemetryList.length === 0) {
            console.warn(`No telemetry history for ${spacecraftId}`);
            return;
        }

        // Clear old chart data
        positionChart.data.datasets.forEach(ds => ds.data = []);
        velocityChart.data.datasets.forEach(ds => ds.data = []);
        temperatureChart.data.datasets.forEach(ds => ds.data = []);
        signalQualityChart.data.datasets.forEach(ds => ds.data = []);

        // Replay historical data
        for (const telemetry of telemetryList) {
            let timestamp = new Date();
            try {
                if (typeof telemetry.timestamp === 'number') {
                    timestamp = new Date(telemetry.timestamp * 1000);
                } else if (typeof telemetry.timestamp === 'string') {
                    timestamp = new Date(parseFloat(telemetry.timestamp) * 1000);
                }
            } catch (e) {
                console.error("Failed to parse timestamp:", e);
            }

            updateCharts(telemetry, timestamp);
        }

        // Update dashboard elements with the latest telemetry point
        updateTelemetryDisplay(telemetryList[telemetryList.length - 1]);

    } catch (error) {
        console.error(`Error fetching telemetry history for ${spacecraftId}:`, error);
    }
}


// ============================================================
// DISPLAY UPDATE FUNCTIONS
// ============================================================

function formatTelemetryValue(value, unit, divider = 1, decimals = 1) {
    if (value === undefined || value === null || isNaN(value)) {
        return 'N/A';
    }
    return `${(value/divider).toFixed(decimals)} ${unit}`;
}

function updateTelemetryDisplay(telemetry) {
    if (!telemetry) return;
    
    // Format timestamp
    let timestamp;
    try {
        if (typeof telemetry.timestamp === 'number') {
            timestamp = new Date(telemetry.timestamp * 1000);
        } else if (typeof telemetry.timestamp === 'string') {
            if (telemetry.timestamp.includes('T')) {
                timestamp = new Date(telemetry.timestamp);
            } else {
                timestamp = new Date(parseFloat(telemetry.timestamp) * 1000);
            }
        } else {
            timestamp = new Date();
        }
        
        if (isNaN(timestamp.getTime())) {
            timestamp = new Date();
        }
    } catch (e) {
        console.error("Error parsing timestamp:", e);
        timestamp = new Date();
    }
    
    // Update position displays (AU for deep space - 1 AU = 149,597,870.7 km)
    const kmToAU = 149597870.7;
    safeUpdateElement('position-x', formatTelemetryValue(telemetry.position_x, 'AU', kmToAU, 3));
    safeUpdateElement('position-y', formatTelemetryValue(telemetry.position_y, 'AU', kmToAU, 3));
    safeUpdateElement('position-z', formatTelemetryValue(telemetry.position_z, 'AU', kmToAU, 3));
    
    // Update velocity displays (km/s is standard for spacecraft)
    safeUpdateElement('velocity-x', formatTelemetryValue(telemetry.velocity_x, 'km/s', 1, 3));
    safeUpdateElement('velocity-y', formatTelemetryValue(telemetry.velocity_y, 'km/s', 1, 3));
    safeUpdateElement('velocity-z', formatTelemetryValue(telemetry.velocity_z, 'km/s', 1, 3));
    
    // Update temperature
    safeUpdateElement('temperature', formatTelemetryValue(telemetry.temperature, '°C', 1, 1));
    
    // Update communication stats
    if (telemetry.comm_stats) {
        safeUpdateElement('packets-lost', telemetry.comm_stats.packets_lost || 0);
        safeUpdateElement('packet-loss-rate', `${(telemetry.comm_stats.packet_loss_rate || 0).toFixed(1)}%`);
        safeUpdateElement('signal-delay', `${(telemetry.comm_stats.signal_delay || 0).toFixed(2)} s`);
    }
    
    // Update last update time
    safeUpdateElement('last-update-time', timestamp.toLocaleTimeString());
    
    // Update anomaly status
    if (telemetry.anomaly_detected) {
        safeUpdateElement('anomaly-status', 'DETECTED');
        document.getElementById('anomaly-status')?.classList.add('text-danger');
    } else {
        safeUpdateElement('anomaly-status', 'NORMAL');
        document.getElementById('anomaly-status')?.classList.remove('text-danger');
    }
    
    // Update charts
    updateCharts(telemetry, timestamp);
}

function updateCharts(telemetry, timestamp) {
    // Position chart (in AU)
    const kmToAU = 149597870.7;
    if (positionChart) {
        if (telemetry.position_x !== undefined) 
            addData(positionChart, 0, timestamp, telemetry.position_x/kmToAU);
        if (telemetry.position_y !== undefined)
            addData(positionChart, 1, timestamp, telemetry.position_y/kmToAU);
        if (telemetry.position_z !== undefined) 
            addData(positionChart, 2, timestamp, telemetry.position_z/kmToAU);
    }
    
    // Velocity chart (in km/s)
    if (velocityChart) {
        if (telemetry.velocity_x !== undefined) 
            addData(velocityChart, 0, timestamp, telemetry.velocity_x);
        if (telemetry.velocity_y !== undefined)
            addData(velocityChart, 1, timestamp, telemetry.velocity_y);
        if (telemetry.velocity_z !== undefined)
            addData(velocityChart, 2, timestamp, telemetry.velocity_z);
    }
    
    // Temperature chart
    if (temperatureChart && telemetry.temperature !== undefined) {
        addData(temperatureChart, 0, timestamp, telemetry.temperature);
    }
    
    // Signal quality chart (from comm stats)
    if (signalQualityChart && telemetry.signal_quality !== undefined) {
        addData(signalQualityChart, 0, timestamp, telemetry.signal_quality);
    }
}

function updateSystemStatusDisplay(status) {
    if (!status) return;
    
    // Update power level
    const powerLevelElement = document.getElementById('power-level');
    const powerBarElement = document.getElementById('power-bar');
    
    if (powerLevelElement && powerBarElement && status.power_level !== undefined) {
        powerLevelElement.textContent = `${status.power_level}%`;
        powerBarElement.style.width = `${status.power_level}%`;
        
        if (status.power_level < 20) {
            powerBarElement.className = 'progress-bar bg-danger';
        } else if (status.power_level < 50) {
            powerBarElement.className = 'progress-bar bg-warning';
        } else {
            powerBarElement.className = 'progress-bar bg-success';
        }
    }
    
    // Update mode
    safeUpdateElement('system-mode', status.system_mode?.toUpperCase() || 'UNKNOWN');
    
    // Handle SOS situations
    if (status.sos_required) {
        showSosAlert(status.sos_reason || 'Unknown emergency');
    }
}

function updateCommStatsDisplay(data) {
    if (!data) return;
    
    document.getElementById('packets-sent').textContent = safeNumber(data.packets_sent, 0);
    document.getElementById('packets-received').textContent = safeNumber(data.packets_received, 0);
    document.getElementById('packets-lost').textContent = safeNumber(data.packets_lost, 0);
    document.getElementById('packet-loss-rate').textContent = safeNumber(data.packet_loss_rate, 2) + '%';
    document.getElementById('signal-delay').textContent = safeNumber(data.signal_delay, 3) + 's';
    document.getElementById('data-volume').textContent = safeNumber(data.data_volume_kb, 1) + ' KB';

    // Update signal quality indicator
    updateSignalQualityIndicator(data.signal_quality);
}

function updateSignalQualityIndicator(quality) {
    const indicator = document.getElementById('signal-status-indicator');
    if (!indicator) return;
    
    indicator.classList.remove('status-good', 'status-warning', 'status-critical');
    
    if (quality >= 80) {
        indicator.classList.add('status-good');
    } else if (quality >= 50) {
        indicator.classList.add('status-warning');
    } else {
        indicator.classList.add('status-critical');
    }
}

function updateAnomalyLog(anomalies) {
    // Skip if no anomalies or invalid data
    if (!anomalies || !Array.isArray(anomalies) || anomalies.length === 0) return;
    
    const anomalyLog = document.getElementById('anomaly-log');
    if (!anomalyLog) return;
    
    let newAnomaliesFound = false;
    
    for (const anomaly of anomalies) {
        // Skip invalid anomalies
        if (!anomaly || !anomaly.message) continue;
        
        // Format timestamp
        let time;
        try {
            if (typeof anomaly.timestamp === 'number') {
                time = new Date(anomaly.timestamp * 1000);
            } else if (typeof anomaly.timestamp === 'string') {
                if (anomaly.timestamp.includes('T')) {
                    time = new Date(anomaly.timestamp);
                } else {
                    time = new Date(parseFloat(anomaly.timestamp) * 1000);
                }
            } else {
                time = new Date();
            }
            
            if (isNaN(time.getTime())) {
                time = new Date();
            }
        } catch (e) {
            console.error("Error parsing timestamp:", e);
            time = new Date();
        }
        
        const timeString = time.toLocaleTimeString();
        const uniqueKey = `${anomaly.timestamp}-${anomaly.message}-${anomaly.severity || ''}`;
        
        // Skip duplicates
        if (seenAnomalies.has(uniqueKey)) continue;
        
        // Mark as seen
        seenAnomalies.add(uniqueKey);
        newAnomaliesFound = true;
        anomalyCount++;
        
        // Create table row
        const row = document.createElement('tr');
        
        // Set row class based on severity
        if (anomaly.severity === 'critical') {
            row.classList.add('table-danger');
            row.classList.add('flash-animation');
            setTimeout(() => row.classList.remove('flash-animation'), 5000);
        } else if (anomaly.severity === 'warning') {
            row.classList.add('table-warning');
        }
        
        // Prepare spacecraft ID
        const spacecraft = anomaly.spacecraft_id || 'Unknown';
        
        // Add cells
        row.innerHTML = `
            <td>${timeString}</td>
            <td>${spacecraft}</td>
            <td><span class="badge ${anomaly.severity === 'critical' ? 'bg-danger' : 'bg-warning'}">${anomaly.severity?.toUpperCase() || 'INFO'}</span></td>
            <td>${anomaly.message}</td>
        `;
        
        // Add to table (prepend to show newest first)
        anomalyLog.prepend(row);
        
        // Keep table a reasonable size
        if (anomalyLog.children.length > 100) {
            anomalyLog.removeChild(anomalyLog.lastChild);
        }
    }
    
    // Update mission log title with count
    if (newAnomaliesFound) {
        const missionLogTitle = document.getElementById('mission-log-title');
        if (missionLogTitle) {
            missionLogTitle.textContent = `Mission Log (${anomalyCount})`;
            missionLogTitle.classList.add('has-alerts');
            
            missionLogTitle.classList.add('highlight');
            setTimeout(() => missionLogTitle.classList.remove('highlight'), 2000);
        }
    }
    
    // Clean up old anomalies in memory
    const now = Date.now();
    for (const key of seenAnomalies.keys()) {
        const timestamp = parseInt(key.split('-')[0]) * 1000;
        if (now - timestamp > ANOMALY_RETENTION_TIME) {
            seenAnomalies.delete(key);
        }
    }
}

function updateAutonomousDecisions(decisions) {
    if (!decisions || !Array.isArray(decisions) || decisions.length === 0) return;
    
    const decisionLog = document.getElementById('autonomous-decisions');
    if (!decisionLog) return;
    
    for (const decision of decisions) {
        // Skip invalid entries
        if (!decision || !decision.decision) continue;
        
        // Format timestamp
        let time;
        try {
            if (typeof decision.timestamp === 'number') {
                time = new Date(decision.timestamp * 1000);
            } else if (typeof decision.timestamp === 'string') {
                time = new Date(parseFloat(decision.timestamp) * 1000);
            } else {
                time = new Date();
            }
        } catch (e) {
            time = new Date();
        }
        
        // Create row
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${time.toLocaleTimeString()}</td>
            <td>${decision.spacecraft_id || ''}</td>
            <td>${decision.decision}</td>
            <td><span class="badge ${decision.result === 'Success' ? 'bg-success' : 'bg-danger'}">${decision.result || 'Unknown'}</span></td>
        `;
        
        // Add to table
        decisionLog.prepend(row);
        
        // Keep table a reasonable size
        if (decisionLog.children.length > 50) {
            decisionLog.removeChild(decisionLog.lastChild);
        }
    }
}

function showSosAlert(reason) {
    // Create a unique key for this alert
    const alertKey = `sos-${reason}`;
    const now = Date.now();
    
    // Don't show if already acknowledged or shown recently
    if (acknowledgedAlerts.has(alertKey) || now - lastAlertTime < ALERT_COOLDOWN) {
        console.log("Suppressing repeat SOS alert:", reason);
        return;
    }
    
    console.log("Showing SOS alert:", reason);
    lastAlertTime = now;
    
    // Update modal content
    const reasonElement = document.getElementById('sos-reason');
    if (reasonElement) {
        reasonElement.textContent = reason;
    }
    
    // Show modal using Bootstrap's API
    const sosModal = new bootstrap.Modal(document.getElementById('sos-modal'));
    sosModal.show();
    
    // Play sound if available
    const sound = document.getElementById('sos-alert-sound');
    if (sound) {
        sound.volume = 0.5;
        sound.play().catch(e => console.log("Sound play prevented:", e));
    }
}

function acknowledgeAlert() {
    const reason = document.getElementById('sos-reason').textContent;
    const alertKey = `sos-${reason}`;
    acknowledgedAlerts.add(alertKey);
    
    // Auto-clear acknowledgment after 10 minutes
    setTimeout(() => {
        acknowledgedAlerts.delete(alertKey);
    }, 10 * 60 * 1000);
}

function updateSpaceWeather(data) {
    if (!data) return;
    
    // Update space weather readings
    safeUpdateElement('solar-flux', `${data.solar_flux.toFixed(1)} SFU`);
    safeUpdateElement('solar-wind', `${data.solar_wind_speed.toFixed(0)} km/s`);
    safeUpdateElement('kp-index', data.geomagnetic_kp.toFixed(1));
    
    // Update radiation indicator
    const radiationElement = document.getElementById('radiation-level');
    if (radiationElement) {
        radiationElement.textContent = data.radiation_level.toUpperCase();
        radiationElement.className = ''; // Reset classes
        if (data.radiation_level === 'elevated') {
            radiationElement.classList.add('text-warning');
        } else if (data.radiation_level === 'high') {
            radiationElement.classList.add('text-danger');
        }
    }
    
    // Display any warnings
    const warningsElement = document.getElementById('space-weather-warnings');
    if (warningsElement && data.warnings && data.warnings.length > 0) {
        warningsElement.innerHTML = '';
        data.warnings.forEach(warning => {
            const alert = document.createElement('div');
            alert.className = 'alert alert-warning mb-1 py-1';
            alert.textContent = `${warning.severity} ${warning.type}: ${warning.description}`;
            warningsElement.appendChild(alert);
        });
        warningsElement.classList.remove('d-none');
    } else if (warningsElement) {
        warningsElement.classList.add('d-none');
    }
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function safeNumber(value, decimals = 2) {
    if (value === undefined || value === null || isNaN(value)) {
        return 'N/A';
    }
    return Number(value).toFixed(decimals);
}

function safeValue(value) {
    if (value === undefined || value === null) {
        return 'N/A';
    }
    return value;
}

function safeUpdateElement(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function addData(chart, datasetIndex, label, data) {
    if (!chart || !chart.data || !chart.data.datasets || !chart.data.datasets[datasetIndex]) {
        return;
    }
    
    chart.data.datasets[datasetIndex].data.push({
        x: label,
        y: data
    });
    
    // Remove old data to keep chart performant
    if (chart.data.datasets[datasetIndex].data.length > 30) {
        chart.data.datasets[datasetIndex].data.shift();
    }
    
    chart.update('quiet');
}

function openControlPanel() {
    window.open('/control-panel.html', '_blank');
}