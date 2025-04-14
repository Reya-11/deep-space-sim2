// dashboard/static/js/dashboard.js

// Initialize socket connection
const socket = io();

// Add this after socket initialization

// Track page refresh
function updateRefreshTime() {
    const refreshElement = document.getElementById('last-refresh');
    if (refreshElement) {
        const now = new Date();
        refreshElement.textContent = now.toLocaleTimeString();
    }
}

// Update refresh time when page loads
document.addEventListener('DOMContentLoaded', function() {
    updateRefreshTime();
    
    // Setup manual refresh button
    const refreshButton = document.getElementById('manual-refresh');
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            window.location.reload();
        });
    }
});

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
const MAX_TRAIL_POINTS = 100;  // Increased to show longer trails

// Function to draw spacecraft position
function drawPosition(x, y, z, data) {
    // Store position for trail
    positionHistory.push({x, y, z});
    if (positionHistory.length > MAX_TRAIL_POINTS) {
        positionHistory.shift();
    }

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw space background
    ctx.fillStyle = '#0a0d1c';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw stars (only generate once)
    if (!window.starsGenerated) {
        window.stars = [];
        for (let i = 0; i < 200; i++) {
            window.stars.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                size: Math.random() * 1.2 + 0.5
            });
        }
        window.starsGenerated = true;
    }
    
    // Draw stars
    ctx.fillStyle = '#ffffff';
    window.stars.forEach(star => {
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        ctx.fill();
    });
    
    // Constants for solar system
    const AU = 149597870.7; // km
    
    // Define celestial bodies relative to Mars (origin)
    const celestialBodies = [
        { 
            name: "Mars", 
            position: [0, 0, 0], 
            color: "#c1440e", 
            size: 6,
            glow: "#ff5722"
        },
        { 
            name: "Earth", 
            position: [-0.6 * AU, -1.2 * AU, 0], 
            color: "#0077be", 
            size: 7,
            glow: "#29b6f6"
        },
        { 
            name: "Sun", 
            position: [-1.5 * AU, 0, 0], 
            color: "#ffcc00", 
            size: 12,
            glow: "#ffeb3b"
        }
    ];
    
    // Determine scale based on AU for better visualization
    // Use a scale that ensures bodies are visible but not too large/small
    const maxDistanceFromOrigin = 2 * AU; // Cover at least 2 AU radius
    const scaleFactor = (canvas.width * 0.4) / maxDistanceFromOrigin;
    
    // Draw coordinate grid (fainter)
    ctx.strokeStyle = 'rgba(42, 58, 124, 0.3)';
    ctx.lineWidth = 0.5;
    
    // Grid lines (every 0.25 AU)
    const gridStep = 0.25 * AU * scaleFactor;
    const gridLines = 10;
    for (let i = -gridLines; i <= gridLines; i++) {
        const pos = centerX + i * gridStep;
        if (pos >= 0 && pos <= canvas.width) {
            ctx.beginPath();
            ctx.moveTo(pos, 0);
            ctx.lineTo(pos, canvas.height);
            ctx.stroke();
        }
    }
    
    for (let i = -gridLines; i <= gridLines; i++) {
        const pos = centerY + i * gridStep;
        if (pos >= 0 && pos <= canvas.height) {
            ctx.beginPath();
            ctx.moveTo(0, pos);
            ctx.lineTo(canvas.width, pos);
            ctx.stroke();
        }
    }
    
    // Draw main axes
    ctx.strokeStyle = 'rgba(42, 58, 124, 0.7)';
    ctx.lineWidth = 1;
    
    // X axis
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(canvas.width, centerY);
    ctx.stroke();
    
    // Y axis
    ctx.beginPath();
    ctx.moveTo(centerX, 0);
    ctx.lineTo(centerX, canvas.height);
    ctx.stroke();
    
    // Draw orbit paths
    ctx.strokeStyle = 'rgba(100, 100, 100, 0.3)';
    ctx.lineWidth = 1;
    
    // Sun-Earth orbit
    ctx.beginPath();
    ctx.arc(
        centerX + celestialBodies[2].position[0] * scaleFactor, 
        centerY - celestialBodies[2].position[2] * scaleFactor, 
        1.0 * AU * scaleFactor, 0, Math.PI * 2
    );
    ctx.stroke();
    
    // Sun-Mars orbit
    ctx.beginPath();
    ctx.arc(
        centerX + celestialBodies[2].position[0] * scaleFactor, 
        centerY - celestialBodies[2].position[2] * scaleFactor, 
        1.5 * AU * scaleFactor, 0, Math.PI * 2
    );
    ctx.stroke();
    
    // Draw celestial bodies
    celestialBodies.forEach(body => {
        const bodyX = centerX + body.position[0] * scaleFactor;
        const bodyY = centerY - body.position[2] * scaleFactor;
        
        // Draw glow around celestial body
        const glowRadius = body.size * 2;
        const glowGradient = ctx.createRadialGradient(bodyX, bodyY, 0, bodyX, bodyY, glowRadius);
        glowGradient.addColorStop(0, body.glow);
        glowGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        
        ctx.fillStyle = glowGradient;
        ctx.beginPath();
        ctx.arc(bodyX, bodyY, glowRadius, 0, Math.PI * 2);
        ctx.fill();
        
        // Draw body
        ctx.fillStyle = body.color;
        ctx.beginPath();
        ctx.arc(bodyX, bodyY, body.size, 0, Math.PI * 2);
        ctx.fill();
        
        // Draw label with background
        ctx.font = '12px Arial';
        const labelWidth = ctx.measureText(body.name).width;
        
        // Text background
        ctx.fillStyle = 'rgba(10, 13, 28, 0.7)';
        ctx.fillRect(bodyX - labelWidth/2 - 4, bodyY - 25, labelWidth + 8, 18);
        
        // Text
        ctx.fillStyle = body.color;
        ctx.textAlign = 'center';
        ctx.fillText(body.name, bodyX, bodyY - 12);
        ctx.textAlign = 'left';
    });
    
    // Draw spacecraft position
    const posX = centerX + x * scaleFactor;
    const posY = centerY - z * scaleFactor;
    
    // Draw full orbital path from history
    if (positionHistory.length > 1) {
        // Draw the fainter extended trail
        ctx.strokeStyle = 'rgba(125, 188, 255, 0.3)';
        ctx.lineWidth = 1.5;
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
        
        // Draw bright recent trail (last 15 points)
        if (positionHistory.length > 15) {
            ctx.strokeStyle = 'rgba(125, 188, 255, 0.8)';
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            
            const startIdx = positionHistory.length - 15;
            let startPos = positionHistory[startIdx];
            let startX = centerX + startPos.x * scaleFactor;
            let startY = centerY - startPos.z * scaleFactor;
            
            ctx.moveTo(startX, startY);
            
            for (let i = startIdx + 1; i < positionHistory.length; i++) {
                const pos = positionHistory[i];
                const px = centerX + pos.x * scaleFactor;
                const py = centerY - pos.z * scaleFactor;
                ctx.lineTo(px, py);
            }
            ctx.stroke();
        }
    }
    
    // Draw spacecraft with glow effect
    const craftGlow = ctx.createRadialGradient(posX, posY, 0, posX, posY, 10);
    craftGlow.addColorStop(0, 'rgba(255, 255, 255, 0.8)');
    craftGlow.addColorStop(1, 'rgba(125, 188, 255, 0)');
    
    ctx.fillStyle = craftGlow;
    ctx.beginPath();
    ctx.arc(posX, posY, 10, 0, Math.PI * 2);
    ctx.fill();
    
    // Spacecraft itself
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(posX, posY, 4, 0, Math.PI * 2);
    ctx.fill();
    
    // Add a label for spacecraft
    const craftLabel = "Spacecraft";
    ctx.font = '11px Arial';
    const craftLabelWidth = ctx.measureText(craftLabel).width;
    
    // Label background
    ctx.fillStyle = 'rgba(10, 13, 28, 0.7)';
    ctx.fillRect(posX + 10, posY - 6, craftLabelWidth + 8, 16);
    
    // Label text
    ctx.fillStyle = '#ffffff';
    ctx.fillText(craftLabel, posX + 14, posY + 5);
    
    // Show scale
    ctx.font = '12px Arial';
    const scaleText = `Scale: 1 pixel = ${(1/scaleFactor/1000).toFixed(0)} × 10³ km (${(0.25*AU/1000).toFixed(0)}k km per grid)`;
    const scaleWidth = ctx.measureText(scaleText).width;
    
    // Scale background
    ctx.fillStyle = 'rgba(10, 13, 28, 0.7)';
    ctx.fillRect(10, canvas.height - 25, scaleWidth + 10, 20);
    
    // Scale text
    ctx.fillStyle = '#7dbcff';
    ctx.fillText(scaleText, 15, canvas.height - 10);
    
    // Calculate distance to Mars (origin)
    const distanceToMars = Math.sqrt(x*x + y*y + z*z);
    
    // Calculate distance to Earth
    const earthPos = celestialBodies[1].position;
    const distanceToEarth = Math.sqrt(
        Math.pow(x - earthPos[0], 2) + 
        Math.pow(y - earthPos[1], 2) + 
        Math.pow(z - earthPos[2], 2)
    );
    
    // Calculate distance to Sun
    const sunPos = celestialBodies[2].position;
    const distanceToSun = Math.sqrt(
        Math.pow(x - sunPos[0], 2) + 
        Math.pow(y - sunPos[1], 2) + 
        Math.pow(z - sunPos[2], 2)
    );
    
    // Update coordinate display
    document.getElementById('pos-x').textContent = formatDistance(x);
    document.getElementById('pos-y').textContent = formatDistance(y);
    document.getElementById('pos-z').textContent = formatDistance(z);
    
    // Add distance information
    const distanceInfo = `Mars: ${formatDistance(distanceToMars)} | Earth: ${formatDistance(distanceToEarth)} | Sun: ${formatDistance(distanceToSun)}`;
    
    // Update or create distance element
    let distanceElement = document.getElementById('body-distances');
    if (!distanceElement) {
        distanceElement = document.createElement('div');
        distanceElement.id = 'body-distances';
        distanceElement.className = 'body-distances';
        
        // Insert after coordinates
        const coordElement = document.querySelector('.coordinates');
        coordElement.parentNode.insertBefore(distanceElement, coordElement.nextSibling);
        
        // Add some styles
        const style = document.createElement('style');
        style.textContent = `
            .body-distances {
                margin-top: 10px;
                font-family: monospace;
                font-size: 1.1em;
                text-align: center;
                color: #7dbcff;
                background-color: rgba(26, 38, 89, 0.4);
                border-radius: 5px;
                padding: 5px;
            }
            
            /* Orbit info display */
            .orbit-info {
                margin-top: 5px;
                font-family: monospace;
                font-size: 0.9em;
                text-align: center;
                color: #aaccff;
                background-color: rgba(26, 38, 89, 0.2);
                border-radius: 5px;
                padding: 3px;
            }
        `;
        document.head.appendChild(style);
    }
    
    distanceElement.textContent = distanceInfo;
    
    // Add orbit information if available
    if (data && data.orbit_angle !== undefined) {
        // Calculate orbit percentage (0-100%)
        const orbitPercentage = ((data.orbit_angle / (2 * Math.PI)) * 100).toFixed(1);
        
        let orbitElement = document.getElementById('orbit-info');
        if (!orbitElement) {
            orbitElement = document.createElement('div');
            orbitElement.id = 'orbit-info';
            orbitElement.className = 'orbit-info';
            distanceElement.parentNode.insertBefore(orbitElement, distanceElement.nextSibling);
        }
        orbitElement.textContent = `Orbit: ${orbitPercentage}% complete`;
    }
}

function formatDistance(distance) {
    const AU = 149597870.7; // km
    
    const absDistance = Math.abs(distance);
    if (absDistance < 1000) {
        return `${distance.toFixed(0)} km`;
    } else if (absDistance < AU * 0.01) {
        return `${(distance/1000).toFixed(1)} × 10³ km`;
    } else if (absDistance < AU) {
        return `${(distance/1000).toFixed(0)}k km`;
    } else {
        return `${(distance/AU).toFixed(2)} AU`;
    }
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

// Enhance your existing updateDashboard function to update all aspects of the dashboard
function updateDashboard(data) {
    // Update spacecraft ID
    document.getElementById('spacecraft-id').textContent = data.spacecraft_id;
    
    // Calculate altitude and other distance metrics
    const distanceFromMars = Math.sqrt(
        Math.pow(data.position_x, 2) + 
        Math.pow(data.position_y, 2) + 
        Math.pow(data.position_z, 2)
    );
    
    let altitudeDisplay;
    const AU = 149597870.7; // km
    
    if (distanceFromMars < 1000) {
        altitudeDisplay = `${distanceFromMars.toFixed(0)} km`;
    } else if (distanceFromMars < AU * 0.01) {
        altitudeDisplay = `${(distanceFromMars/1000).toFixed(1)} × 10³ km`;
    } else if (distanceFromMars < AU) {
        altitudeDisplay = `${(distanceFromMars/1000).toFixed(0)}k km`;
    } else {
        altitudeDisplay = `${(distanceFromMars/AU).toFixed(2)} AU`;
    }
    
    // Update all metric values
    document.getElementById('altitude').textContent = altitudeDisplay;
    document.getElementById('velocity').textContent = data.velocity !== undefined ? 
        data.velocity.toFixed(2) + ' km/s' : 
        calculateVelocity(data).toFixed(2) + ' km/s';
    document.getElementById('temperature').textContent = data.temperature.toFixed(1) + ' °C';
    document.getElementById('energy').textContent = data.energy_level.toFixed(1) + '%';
    document.getElementById('radiation').textContent = data.radiation_level.toFixed(0);
    
    // Add data to charts
    addDataPoint(velocityChart, calculateVelocity(data));
    addDataPoint(temperatureChart, data.temperature);
    addDataPoint(energyChart, data.energy_level);
    addDataPoint(radiationChart, data.radiation_level);
    
    // Update system status indicators
    updateStatusIndicators(data);
    
    // Check for alerts or anomalies
    checkAlerts(data);
}

// Helper to check for alerts
function checkAlerts(data) {
    // Check if this is a new alert (compared to lastAlertLevel)
    if (data.alert_level && (!window.lastAlertLevel || window.lastAlertLevel !== data.alert_level)) {
        if (data.alert_level !== 'NOMINAL') {
            addToLog(`Alert level changed to: ${data.alert_level}`, 'alert');
        }
        window.lastAlertLevel = data.alert_level;
    }
    
    // Check for new anomalies
    if (data.anomalies && data.anomalies.length > 0) {
        data.anomalies.forEach(anomaly => {
            addToLog(`Anomaly detected: ${anomaly}`, 'alert');
        });
    }
}

// Update dashboard with new telemetry data
function calculateVelocity(data) {
    return Math.sqrt(
        Math.pow(data.velocity_x || 0, 2) + 
        Math.pow(data.velocity_y || 0, 2) + 
        Math.pow(data.velocity_z || 0, 2)
    );
}

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
    console.log("Received telemetry update:", data.spacecraft_id);
    lastReceivedData = data;
    
    // Update dashboard components
    updateDashboard(data);
    
    // Update position visualization
    if (data.position_x !== undefined) {
        drawPosition(data.position_x, data.position_y, data.position_z, data);
    }
    
    lastUpdateTime = Date.now();
    updateRefreshTime();
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

// Update the animationLoop function
function animationLoop() {
    const now = Date.now();
    
    // Update all components every 5 seconds if we have data
    if (lastReceivedData && now - lastUpdateTime > 5000) {
        console.log("Auto-refreshing dashboard components...");
        
        // Update main dashboard values
        updateDashboard(lastReceivedData);
        
        // Update position visualization
        if (lastReceivedData.position_x !== undefined) {
            drawPosition(
                lastReceivedData.position_x, 
                lastReceivedData.position_y, 
                lastReceivedData.position_z,
                lastReceivedData  // Pass full data for orbit info
            );
        }
        
        // Update charts without adding new data points
        velocityChart.update();
        temperatureChart.update();
        energyChart.update();
        radiationChart.update();
        
        // Update status indicators
        updateStatusIndicators(lastReceivedData);
        
        // Update "last refreshed" indicator
        updateRefreshTime();
        
        lastUpdateTime = now;
    }
    
    requestAnimationFrame(animationLoop);
}

// Add this helper function for status indicators
function updateStatusIndicators(data) {
    // Update spacecraft mode indicator
    if (data.mode) {
        const modeElement = document.getElementById('spacecraft-mode');
        if (modeElement) {
            modeElement.textContent = data.mode;
            
            // Update mode class for styling
            modeElement.className = 'mode-indicator';
            modeElement.classList.add(data.mode.toLowerCase());
        }
    }
    
    // Update alert level indicator
    if (data.alert_level) {
        const alertElement = document.getElementById('alert-level');
        if (alertElement) {
            alertElement.textContent = data.alert_level;
            
            // Update alert class for styling
            alertElement.className = 'alert-indicator';
            alertElement.classList.add(data.alert_level.toLowerCase());
        }
    }
    
    // Update signal strength based on bandwidth_mode
    if (data.bandwidth_mode) {
        const signalElement = document.getElementById('signal-strength');
        if (signalElement) {
            let signalStrength = "Strong";
            let signalClass = "strong";
            
            if (data.bandwidth_mode === 'low') {
                signalStrength = "Weak";
                signalClass = "weak";
            } else if (data.bandwidth_mode === 'critical') {
                signalStrength = "Critical";
                signalClass = "critical";
            }
            
            signalElement.textContent = signalStrength;
            signalElement.className = 'signal-indicator ' + signalClass;
        }
    }
}

// Start animation loop
requestAnimationFrame(animationLoop);

// Update socket event handler to store last data
socket.on('telemetry_update', function(data) {
    lastReceivedData = data;
    updateDashboard(data);
    lastUpdateTime = Date.now();
});

// Add this after your socket event handlers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize refresh time
    updateRefreshTime();
    
    // Set up manual refresh button
    const refreshButton = document.getElementById('manual-refresh');
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            if (lastReceivedData) {
                console.log("Manual refresh triggered");
                updateDashboard(lastReceivedData);
                drawPosition(lastReceivedData.position_x, lastReceivedData.position_y, lastReceivedData.position_z, lastReceivedData);
                
                // Update charts
                velocityChart.update();
                temperatureChart.update();
                energyChart.update();
                radiationChart.update();
                
                // Update status indicators
                updateStatusIndicators(lastReceivedData);
                
                // Update refresh time
                updateRefreshTime();
            } else {
                console.log("No data available for manual refresh");
            }
        });
    }
});