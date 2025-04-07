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

// Setup position canvas
const canvas = document.getElementById('position-canvas');
const ctx = canvas.getContext('2d');
const centerX = canvas.width / 2;
const centerY = canvas.height / 2;

// Function to draw spacecraft position
function drawPosition(x, y, z) {
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw coordinate system
    ctx.strokeStyle = '#2a3a7c';
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
    
    // Draw origin point
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(centerX, centerY, 3, 0, Math.PI * 2);
    ctx.fill();
    
    // Calculate position on canvas (simple 2D projection of x and z)
    // Scale factor to fit within canvas
    const scaleFactor = 0.00005;
    const posX = centerX + x * scaleFactor;
    const posY = centerY - z * scaleFactor;  // Y is inverted in canvas
    
    // Draw spacecraft
    ctx.fillStyle = '#7dbcff';
    ctx.beginPath();
    ctx.arc(posX, posY, 8, 0, Math.PI * 2);
    ctx.fill();
    
    // Draw trail line
    ctx.strokeStyle = '#304b8e';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(posX, posY);
    ctx.stroke();
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
        
        history.forEach(data => {
            addDataPoint(data);
        });
        
        velocityChart.update(velocityData);
        temperatureChart.update(temperatureData);
        
        // Update dashboard with latest values
        updateDashboard(history[history.length - 1]);
    }
});

// Function to add a data point to charts
function addDataPoint(data) {
    // Add timestamp to labels
    velocityData.labels.push(data.timestamp);
    temperatureData.labels.push(data.timestamp);
    
    // Add values to series
    velocityData.series[0].push(data.velocity);
    temperatureData.series[0].push(data.temperature);
    
    // Keep only MAX_DATA_POINTS in the charts
    if (velocityData.labels.length > MAX_DATA_POINTS) {
        velocityData.labels.shift();
        velocityData.series[0].shift();
        temperatureData.labels.shift();
        temperatureData.series[0].shift();
    }
}

// Update dashboard with new telemetry data
function updateDashboard(data) {
    // Update spacecraft ID
    document.getElementById('spacecraft-id').textContent = data.spacecraft_id;
    
    // Calculate altitude and velocity if not provided
    const altitude = data.altitude || 
                    Math.sqrt(Math.pow(data.position_x, 2) + 
                             Math.pow(data.position_y, 2) + 
                             Math.pow(data.position_z, 2)) / 1000;
                             
    const velocity = data.velocity || 
                    Math.sqrt(Math.pow(data.velocity_x, 2) + 
                             Math.pow(data.velocity_y, 2) + 
                             Math.pow(data.velocity_z, 2));
    
    // Update metric values
    document.getElementById('altitude').textContent = `${altitude.toFixed(2)} km`;
    document.getElementById('velocity').textContent = `${velocity.toFixed(2)} m/s`;
    document.getElementById('temperature').textContent = `${data.temperature.toFixed(2)} °C`;
    
    // Add data to charts
    addDataPoint({
        timestamp: data.timestamp,
        velocity: velocity,
        temperature: data.temperature
    });
    
    // Update charts
    velocityChart.update(velocityData);
    temperatureChart.update(temperatureData);
    
    // Update position visualization
    drawPosition(data.position_x, data.position_y, data.position_z);
    
    // Color-code temperature based on value
    const tempElement = document.getElementById('temperature');
    if (data.temperature > 100) {
        tempElement.style.color = '#ff4d4d';
    } else if (data.temperature < 0) {
        tempElement.style.color = '#4da6ff';
    } else {
        tempElement.style.color = '#ffffff';
    }
    
    // Color-code velocity based on value
    const velElement = document.getElementById('velocity');
    if (velocity > 10000) {
        velElement.style.color = '#ff9800';
    } else if (velocity > 5000) {
        velElement.style.color = '#4caf50';
    } else {
        velElement.style.color = '#ffffff';
    }
}

// Initial canvas setup
drawPosition(0, 0, 0);