// dashboard/static/js/dashboard.js

// Initialize socket connection
const socket = io();

// Data arrays for charts
const velocityData = {
    labels: [],
    series: [[]]
};

const temperatureData = {
    labels: [],
    series: [[]]
};

const energyData = {
    labels: [],
    series: [[]]
};

const radiationData = {
    labels: [],
    series: [[]]
};

// Maximum data points to show in charts
const MAX_DATA_POINTS = 20;

// Chart options
const chartOptions = {
    fullWidth: true,
    chartPadding: {
        right: 30,
        left: 20
    },
    axisY: {
        onlyInteger: false,
        showGrid: true,
        offset: 30
    },
    axisX: {
        showGrid: false,
        labelInterpolationFnc: function(value, index) {
            return index % 2 === 0 ? new Date(value * 1000).toLocaleTimeString() : '';
        }
    },
    lineSmooth: Chartist.Interpolation.cardinal({
        tension: 0.2
    }),
    low: 0
};

// Initialize charts
const velocityChart = new Chartist.Line('#velocity-chart', velocityData, chartOptions);
const temperatureChart = new Chartist.Line('#temperature-chart', temperatureData, chartOptions);
const energyChart = new Chartist.Line('#energy-chart', energyData, Object.assign({}, chartOptions, {high: 100}));
const radiationChart = new Chartist.Line('#radiation-chart', radiationData, Object.assign({}, chartOptions));

// Setup position canvas
const canvas = document.getElementById('position-canvas');
const ctx = canvas.getContext('2d');
const centerX = canvas.width / 2;
const centerY = canvas.height / 2;

// Store command history
const commandHistory = [];

// Store position history for trails
const positionHistory = [];
const MAX_TRAIL_POINTS = 50;

// Function to draw spacecraft position
function drawPosition(x, y, z) {
    // Store position for trail
    positionHistory.push({x, y, z});
    if (positionHistory.length > MAX_TRAIL_POINTS) {
        positionHistory.shift();
    }

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw space background with stars
    // ...existing code...
    
    // Calculate appropriate scale for deep space
    // Use logarithmic scaling for better visualization
    const AU = 149597870700; // meters
    const LIGHT_YEAR = 9.461e15; // meters
    
    // Get magnitude of position
    const distanceFromOrigin = Math.sqrt(x*x + y*y + z*z);
    
    // Determine scale factor based on distance
    let scaleFactor;
    let scaleLabel;
    
    if (distanceFromOrigin < 100 * AU) {
        // Nearby space (within 100 AU)
        scaleFactor = canvas.width / (200 * AU);
        scaleLabel = `1 pixel = ${(1/scaleFactor/1000).toFixed(0)} × 10³ km`;
    } else if (distanceFromOrigin < 10 * LIGHT_YEAR) {
        // Deep space (up to 10 light-years)
        scaleFactor = canvas.width / (20 * LIGHT_YEAR);
        scaleLabel = `1 pixel = ${(1/scaleFactor/AU).toFixed(2)} AU`;
    } else {
        // Very deep space (beyond 10 light-years)
        scaleFactor = canvas.width / (50 * LIGHT_YEAR);
        scaleLabel = `1 pixel = ${(1/scaleFactor/LIGHT_YEAR).toFixed(2)} light-years`;
    }
    
    // Calculate position on canvas
    const posX = centerX + x * scaleFactor;
    const posY = centerY - z * scaleFactor;  // Y is inverted in canvas
    
    // Draw Earth (origin)
    // Draw a small blue dot at the origin point
    ctx.fillStyle = '#1a66ff';
    ctx.beginPath();
    ctx.arc(centerX, centerY, 4, 0, Math.PI * 2);
    ctx.fill();
    
    // Label Earth
    ctx.fillStyle = '#1a66ff';
    ctx.font = '12px Arial';
    ctx.fillText("Earth", centerX + 8, centerY - 8);
    
    // Rest of the drawing code for spacecraft and trails
    if (positionHistory.length > 1) {
        ctx.strokeStyle = 'rgba(48, 75, 142, 0.6)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        const firstPos = positionHistory[0];
        const firstPosX = centerX + firstPos.x * scaleFactor;
        const firstPosY = centerY - firstPos.z * scaleFactor;
        
        ctx.moveTo(firstPosX, firstPosY);
        
        for (let i = 1; i < positionHistory.length; i++) {
            const pos = positionHistory[i];
            const px = centerX + pos.x * scaleFactor;
            const py = centerY - pos.z * scaleFactor;
            ctx.lineTo(px, py);
        }
        ctx.stroke();
    }
    
    // Draw spacecraft with glow effect
    const glowRadius = 12;
    const glowGradient = ctx.createRadialGradient(posX, posY, 0, posX, posY, glowRadius);
    glowGradient.addColorStop(0, 'rgba(125, 188, 255, 0.8)');
    glowGradient.addColorStop(1, 'rgba(125, 188, 255, 0)');
    
    ctx.fillStyle = glowGradient;
    ctx.beginPath();
    ctx.arc(posX, posY, glowRadius, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.fillStyle = '#7dbcff';
    ctx.beginPath();
    ctx.arc(posX, posY, 6, 0, Math.PI * 2);
    ctx.fill();
    
    // Show current scale
    ctx.fillStyle = 'rgba(10, 13, 28, 0.7)';
    const scaleWidth = ctx.measureText(scaleLabel).width;
    ctx.fillRect(10, canvas.height - 25, scaleWidth + 10, 20);
    
    ctx.fillStyle = '#7dbcff';
    ctx.fillText(scaleLabel, 15, canvas.height - 10);
    
    // Update coordinate display (in more appropriate units)
    document.getElementById('pos-x').textContent = formatDistanceValue(x);
    document.getElementById('pos-y').textContent = formatDistanceValue(y);
    document.getElementById('pos-z').textContent = formatDistanceValue(z);
}

// Helper function to format large distance values
function formatDistanceValue(meters) {
    const AU = 149597870700; // meters
    const LIGHT_YEAR = 9.461e15; // meters
    
    if (Math.abs(meters) < AU) {
        return `${(meters / 1000).toFixed(0)} km`;
    } else if (Math.abs(meters) < LIGHT_YEAR) {
        return `${(meters / AU).toFixed(2)} AU`;
    } else {
        return `${(meters / LIGHT_YEAR).toFixed(2)} ly`;
    }
}

// Function to add a data point to charts
function addDataPoint(data) {
    // Add timestamp to labels
    const timestamp = data.timestamp || Date.now() / 1000;
    velocityData.labels.push(timestamp);
    temperatureData.labels.push(timestamp);
    energyData.labels.push(timestamp);
    radiationData.labels.push(timestamp);
    
    // Calculate velocity if not provided
    const velocity = data.velocity || 
        Math.sqrt(Math.pow(data.velocity_x || 0, 2) + 
                 Math.pow(data.velocity_y || 0, 2) + 
                 Math.pow(data.velocity_z || 0, 2));
    
    // Add values to series
    velocityData.series[0].push(velocity);
    temperatureData.series[0].push(data.temperature);
    energyData.series[0].push(data.energy_level || 0);
    radiationData.series[0].push(data.radiation_level || 0);
    
    // Keep only MAX_DATA_POINTS in the charts
    if (velocityData.labels.length > MAX_DATA_POINTS) {
        velocityData.labels.shift();
        velocityData.series[0].shift();
        temperatureData.labels.shift();
        temperatureData.series[0].shift();
        energyData.labels.shift();
        energyData.series[0].shift();
        radiationData.labels.shift();
        radiationData.series[0].shift();
    }
}

// Update dashboard with new telemetry data
function updateDashboard(data) {
    // Update spacecraft ID
    document.getElementById('spacecraft-id').textContent = data.spacecraft_id;
    
    // Calculate distance from Earth (origin)
    const distanceFromOrigin = Math.sqrt(
        Math.pow(data.position_x, 2) + 
        Math.pow(data.position_y, 2) + 
        Math.pow(data.position_z, 2)
    );
    
    // Constants for unit conversion
    const AU = 149597870700; // 1 AU in meters
    const LIGHT_YEAR = 9.461e15; // 1 light-year in meters
    const PARSEC = 3.086e16; // 1 parsec in meters
    
    // Format the distance in appropriate units based on scale
    let altitudeDisplay;
    if (distanceFromOrigin < AU) {
        // Less than 1 AU
        altitudeDisplay = `${(distanceFromOrigin / 1000).toFixed(0)} km`;
    } else if (distanceFromOrigin < 100 * AU) {
        // Between 1-100 AU
        altitudeDisplay = `${(distanceFromOrigin / AU).toFixed(2)} AU`;
    } else if (distanceFromOrigin < LIGHT_YEAR) {
        // Between 100 AU and 1 light-year
        altitudeDisplay = `${(distanceFromOrigin / AU).toFixed(0)} AU`;
    } else if (distanceFromOrigin < 10 * LIGHT_YEAR) {
        // Between 1-10 light-years
        altitudeDisplay = `${(distanceFromOrigin / LIGHT_YEAR).toFixed(2)} ly`;
    } else if (distanceFromOrigin < PARSEC) {
        // Between 10 light-years and 1 parsec
        altitudeDisplay = `${(distanceFromOrigin / LIGHT_YEAR).toFixed(1)} ly`;
    } else {
        // Greater than 1 parsec
        altitudeDisplay = `${(distanceFromOrigin / PARSEC).toFixed(2)} pc`;
    }
    
    // Update metric value
    document.getElementById('altitude').textContent = altitudeDisplay;
    
    const velocity = data.velocity || 
        Math.sqrt(Math.pow(data.velocity_x || 0, 2) + 
                 Math.pow(data.velocity_y || 0, 2) + 
                 Math.pow(data.velocity_z || 0, 2));
    
    // Update metric values
    document.getElementById('velocity').textContent = `${velocity.toFixed(2)} m/s`;
    document.getElementById('temperature').textContent = `${data.temperature.toFixed(2)} °C`;
    
    // Update new metrics if available
    if (data.radiation_level !== undefined) {
        document.getElementById('radiation').textContent = `${data.radiation_level.toFixed(2)}`;
    }
    
    if (data.energy_level !== undefined) {
        document.getElementById('energy').textContent = `${data.energy_level.toFixed(1)}%`;
        
        // Update energy progress bar
        const energyBar = document.getElementById('energy-bar');
        energyBar.style.width = `${data.energy_level}%`;
        
        // Color code energy level
        if (data.energy_level < 20) {
            energyBar.style.backgroundColor = '#ff4d4d';
        } else if (data.energy_level < 40) {
            energyBar.style.backgroundColor = '#ff9800';
        } else {
            energyBar.style.backgroundColor = '#4caf50';
        }
    }
    
    // Update mode if available
    if (data.mode) {
        const modeElement = document.getElementById('spacecraft-mode');
        modeElement.textContent = data.mode;
        
        // Remove all mode classes
        modeElement.className = 'mode-value';
        
        // Add specific mode class
        modeElement.classList.add(data.mode);
        
        // Add to log if mode changed
        if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1].mode !== data.mode) {
            addToLog(`Mode changed to ${data.mode}`, 'command');
        }
    }
    
    // Update alert level if available
    if (data.alert_level) {
        const alertElement = document.getElementById('alert-level');
        const indicatorElement = document.getElementById('status-indicator');
        
        alertElement.textContent = data.alert_level;
        
        // Remove all status classes
        alertElement.className = 'status-text';
        indicatorElement.className = 'status-indicator';
        
        // Add specific alert class
        alertElement.classList.add(data.alert_level);
        indicatorElement.classList.add(data.alert_level);
        
        // Add to log if alert changed
        const lastAlert = commandHistory.length > 0 ? 
            commandHistory[commandHistory.length - 1].alert : null;
        
        if (lastAlert !== data.alert_level && data.alert_level !== 'NOMINAL') {
            addToLog(`Alert level: ${data.alert_level}`, 'alert');
        }
    }
    
    // Update signal delay if available
    if (data.delay !== undefined) {
        document.getElementById('signal-delay').textContent = `${data.delay.toFixed(2)} s`;
    }
    
    // Update bandwidth mode if available
    if (data.bandwidth_mode) {
        document.getElementById('bandwidth-mode').textContent = data.bandwidth_mode.toUpperCase();
    }
    
    // Add data to charts
    addDataPoint({
        timestamp: data.timestamp,
        velocity: velocity,
        temperature: data.temperature,
        energy_level: data.energy_level,
        radiation_level: data.radiation_level
    });
    
    // Update charts
    velocityChart.update(velocityData);
    temperatureChart.update(temperatureData);
    energyChart.update(energyData);
    radiationChart.update(radiationData);
    
    // Update position visualization
    drawPosition(data.position_x, data.position_y, data.position_z);
    
    // Color-code temperature based on value
    const tempElement = document.getElementById('temperature');
    if (data.temperature > 40) {
        tempElement.style.color = '#ff4d4d';
    } else if (data.temperature < -10) {
        tempElement.style.color = '#4da6ff';
    } else {
        tempElement.style.color = '#ffffff';
    }
    
    // Color-code velocity based on value
    const velElement = document.getElementById('velocity');
    if (velocity > 10) {
        velElement.style.color = '#ff9800';
    } else if (velocity > 5) {
        velElement.style.color = '#4caf50';
    } else {
        velElement.style.color = '#ffffff';
    }
    
    // Store this update in history
    commandHistory.push({
        timestamp: data.timestamp,
        mode: data.mode,
        alert: data.alert_level
    });
}

// Function to add entry to command log
function addToLog(message, type = 'info') {
    // Create a temporary entry immediately (will be replaced when server responds)
    const logContainer = document.getElementById('command-log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    const timestamp = document.createElement('span');
    timestamp.className = 'timestamp';
    timestamp.textContent = new Date().toLocaleTimeString('en-US', {hour12: false});
    
    entry.appendChild(timestamp);
    entry.appendChild(document.createTextNode(' ' + message));
    
    logContainer.appendChild(entry);
    
    // Auto-scroll to bottom
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Handle received telemetry data
socket.on('telemetry_update', function(data) {
    updateDashboard(data);
});

// Handle history data on connect
socket.on('telemetry_history', function(history) {
    if (history.length > 0) {
        // Initialize charts with history data
        velocityData.labels = [];
        velocityData.series[0] = [];
        temperatureData.labels = [];
        temperatureData.series[0] = [];
        energyData.labels = [];
        energyData.series[0] = [];
        radiationData.labels = [];
        radiationData.series[0] = [];
        
        history.forEach(data => {
            addDataPoint(data);
        });
        
        velocityChart.update(velocityData);
        temperatureChart.update(temperatureData);
        energyChart.update(energyData);
        radiationChart.update(radiationData);
        
        // Update dashboard with latest values
        updateDashboard(history[history.length - 1]);
        
        addToLog('Connected to spacecraft telemetry', 'info');
    }
});

// Handle spacecraft commands
socket.on('command_sent', function(command) {
    addToLog(`Command sent: ${command.type} - ${JSON.stringify(command.params)}`, 'command');
});

// Handle a new log entry coming from the server
socket.on('log_entry', function(entry) {
    addServerLogEntry(entry);
});

// Handle full log history
socket.on('log_history', function(history) {
    const logContainer = document.getElementById('command-log');
    logContainer.innerHTML = ''; // Clear existing entries
    
    history.forEach(entry => {
        addServerLogEntry(entry);
    });
});

// Function to add a server log entry
function addServerLogEntry(entry) {
    const logContainer = document.getElementById('command-log');
    const entryDiv = document.createElement('div');
    entryDiv.className = `log-entry ${entry.type}`;
    
    const timestamp = document.createElement('span');
    timestamp.className = 'timestamp';
    timestamp.textContent = entry.timestamp;
    
    entryDiv.appendChild(timestamp);
    entryDiv.appendChild(document.createTextNode(' ' + entry.message));
    
    logContainer.appendChild(entryDiv);
    
    // Auto-scroll to bottom
    logContainer.scrollTop = logContainer.scrollHeight;
    
    // Limit log entries in DOM if needed
    if (logContainer.children.length > 500) {
        logContainer.removeChild(logContainer.children[0]);
    }
}

// Initial canvas setup
drawPosition(0, 0, 0);
addToLog('Telemetry dashboard initialized', 'info');

// Animation loop for continuous updates
let lastUpdateTime = Date.now();
let lastReceivedData = null;

function animationLoop() {
    const now = Date.now();
    
    // Force re-render charts every 5 seconds to keep them fresh
    if (lastReceivedData && now - lastUpdateTime > 5000) {
        console.log("Auto-refreshing dashboard...");
        updateDashboard(lastReceivedData);
        
        // Update charts without adding new data points
        velocityChart.update();
        temperatureChart.update();
        energyChart.update();
        radiationChart.update();
        
        lastUpdateTime = now;
    }
    
    requestAnimationFrame(animationLoop);
}

// Start animation loop
requestAnimationFrame(animationLoop);

// Update socket event handler to store last data
socket.on('telemetry_update', function(data) {
    lastReceivedData = data;
    updateDashboard(data);
    lastUpdateTime = Date.now();
});