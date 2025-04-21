class SpacecraftVisualizer {
    constructor(containerId) {
        console.log('Initializing SpacecraftVisualizer in', containerId);
        this.container = document.getElementById(containerId);
        this.spacecrafts = {};
        this.orbits = {};
        this.activeTelemetrySubscription = false;
        
        if (!this.container) {
            console.error('Container not found:', containerId);
            return;
        }
        
        try {
            // Initialize Cesium viewer with solar system scale
            this.viewer = new Cesium.Viewer(containerId, {
                sceneMode: Cesium.SceneMode.SCENE3D,
                timeline: false,
                animation: false,
                baseLayerPicker: false,
                geocoder: false,
                homeButton: false,
                navigationHelpButton: false,
                fullscreenButton: false,
                shouldAnimate: true
            });
            
            // Configure for space environment
            this.viewer.scene.skyBox.show = true;
            this.viewer.scene.globe.show = false;
            this.viewer.scene.sun.show = true;
            
            // Add sun as central body
            this.viewer.entities.add({
                position: Cesium.Cartesian3.ZERO,
                name: 'Sun',
                ellipsoid: {
                    radii: new Cesium.Cartesian3(696340000, 696340000, 696340000), // Sun radius in meters
                    material: Cesium.Color.YELLOW.withAlpha(0.9)
                }
            });
            
            // Add Earth for reference
            const AU = 149597870700; // 1 AU in meters
            this.viewer.entities.add({
                position: new Cesium.Cartesian3(AU, 0, 0),
                name: 'Earth',
                ellipsoid: {
                    radii: new Cesium.Cartesian3(6371000, 6371000, 6371000), // Earth radius in meters
                    material: Cesium.Color.BLUE.withAlpha(0.9)
                }
            });
            
            console.log('Cesium viewer initialized successfully');
            
            // Start fetching telemetry
            this.startTelemetrySubscription();
            
        } catch (error) {
            console.error('Failed to initialize Cesium viewer:', error);
        }
    }
    
    startTelemetrySubscription() {
        if (this.activeTelemetrySubscription) return;
        this.activeTelemetrySubscription = true;
        
        console.log('Starting telemetry subscription for 3D visualization');
        
        // Initial fetch of spacecraft data
        this.fetchLatestTelemetry();
        
        // Set up polling for new telemetry
        this.telemetryPollInterval = setInterval(() => {
            this.fetchLatestTelemetry();
        }, 5000); // Poll every 5 seconds
        
        // Connect to socket for real-time updates if socket.io is available
        if (typeof io !== 'undefined') {
            try {
                this.socket = io();
                this.socket.on('connect', () => {
                    console.log('3D visualization socket connected');
                });
                
                this.socket.on('telemetry_update', (telemetry) => {
                    console.log('3D visualization received telemetry update via socket');
                    this.processSpacecraftTelemetry(telemetry);
                });
            } catch (e) {
                console.error('Error connecting to socket:', e);
            }
        }
    }
    
    async fetchLatestTelemetry() {
        try {
            console.log('Fetching latest telemetry data for 3D visualization');
            const response = await fetch('/api/telemetry/latest');
            
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Received telemetry data for visualization');
            
            // Process each spacecraft's telemetry
            if (Array.isArray(data)) {
                data.forEach(telemetry => this.processSpacecraftTelemetry(telemetry));
            } else if (typeof data === 'object') {
                // Handle single telemetry object or keyed object format
                if (data.spacecraft_id) {
                    this.processSpacecraftTelemetry(data);
                } else {
                    // Process as keyed object
                    Object.values(data).forEach(telemetry => {
                        this.processSpacecraftTelemetry(telemetry);
                    });
                }
            }
        } catch (error) {
            console.error('Error fetching telemetry for 3D visualization:', error);
        }
    }
    
    processSpacecraftTelemetry(telemetry) {
        if (!telemetry || !telemetry.spacecraft_id) {
            console.warn('Invalid telemetry data received');
            return;
        }
        
        // Update spacecraft visualization using telemetry
        this.updateSpacecraft(telemetry.spacecraft_id, telemetry);
    }
    
    updateSpacecraft(spacecraftId, telemetry) {
        console.log(`Updating spacecraft ${spacecraftId} visualization`);
        
        if (!this.viewer) {
            console.error('Viewer not initialized');
            return;
        }
        
        try {
            // Use telemetry position directly
            const position = {
                x: telemetry.position_x * 1000, // km to m
                y: telemetry.position_y * 1000,
                z: telemetry.position_z * 1000
            };
            
            // Create spacecraft entity if it doesn't exist
            if (!this.spacecrafts[spacecraftId]) {
                console.log(`Creating new spacecraft entity: ${spacecraftId}`);
                
                // Create spacecraft entity using a box since we don't have a model
                this.spacecrafts[spacecraftId] = this.viewer.entities.add({
                    id: spacecraftId,
                    name: `Spacecraft ${spacecraftId}`,
                    position: new Cesium.Cartesian3(position.x, position.y, position.z),
                    box: {
                        dimensions: new Cesium.Cartesian3(10000, 6000, 4000), // Make visible at solar system scale
                        material: Cesium.Color.SILVER,
                        outline: true,
                        outlineColor: Cesium.Color.WHITE,
                        outlineWidth: 1
                    },
                    path: {
                        resolution: 1,
                        material: new Cesium.PolylineGlowMaterialProperty({
                            glowPower: 0.2,
                            color: Cesium.Color.YELLOW.withAlpha(0.3)
                        }),
                        width: 2,
                        leadTime: 0,
                        trailTime: 86400 // Show 1 day of orbit trail
                    },
                    label: {
                        text: spacecraftId,
                        font: '12pt sans-serif',
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineWidth: 2,
                        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                        pixelOffset: new Cesium.Cartesian2(0, -10),
                        fillColor: Cesium.Color.WHITE,
                        outlineColor: Cesium.Color.BLACK
                    }
                });
            } else {
                // Update existing spacecraft position
                this.spacecrafts[spacecraftId].position = new Cesium.Cartesian3(
                    position.x, position.y, position.z
                );
            }
        } catch (error) {
            console.error(`Error updating spacecraft ${spacecraftId}:`, error);
        }
    }
    
    focusOnSpacecraft(spacecraftId) {
        if (!this.viewer || !this.spacecrafts[spacecraftId]) return;
        
        const spacecraft = this.spacecrafts[spacecraftId];
        
        // Fly the camera to the spacecraft
        this.viewer.flyTo(spacecraft, {
            duration: 1.5,
            offset: new Cesium.HeadingPitchRange(0, -Math.PI/4, 100000)
        });
    }
    
    stopTelemetrySubscription() {
        if (this.telemetryPollInterval) {
            clearInterval(this.telemetryPollInterval);
            this.telemetryPollInterval = null;
        }
        
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        
        this.activeTelemetrySubscription = false;
    }
}

// Initialize the visualizer when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing spacecraft visualization');
    window.spacecraftViz = new SpacecraftVisualizer('spacecraft-3d');
});

