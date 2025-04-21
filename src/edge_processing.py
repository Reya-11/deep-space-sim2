import time
import grpc
import random
import math
from concurrent import futures
import space_telemetry_pb2
import space_telemetry_pb2_grpc

# ========== POWER SYSTEM ==========
class PowerSystem:
    def __init__(self):
        self.power_level = 85
        self.max_capacity = 500
        self.current_capacity = self.power_level * self.max_capacity / 100
        self.solar_generation = 50
        self.last_update = time.time()
        self.power_rates = {
            'idle': 5,
            'telemetry_collection': 10,
            'data_transmission': 25,
            'course_correction': 40,
            'safe_mode': 8
        }
        self.current_mode = 'idle'

    def update(self):
        now = time.time()
        elapsed_hours = (now - self.last_update) / 3600
        generated = self.solar_generation * elapsed_hours
        consumed = self.power_rates[self.current_mode] * elapsed_hours
        self.current_capacity += generated - consumed
        self.current_capacity = min(max(self.current_capacity, 0), self.max_capacity)
        self.power_level = (self.current_capacity / self.max_capacity) * 100
        self.last_update = now
        return {
            'level': self.power_level,
            'capacity': self.current_capacity,
            'generation': generated,
            'consumption': consumed,
            'mode': self.current_mode
        }

    def set_mode(self, mode):
        if mode in self.power_rates:
            self.update()
            self.current_mode = mode
            return True
        return False

    def can_perform(self, operation, duration_seconds=60):
        self.update()
        needed = self.power_rates.get(operation, 0) * (duration_seconds / 3600)
        reserve = self.max_capacity * 0.1
        return self.current_capacity - needed > reserve

    def get_level(self):
        self.update()
        return self.power_level


# ========== SPACE WEATHER ==========
class SpaceWeather:
    def __init__(self):
        self.solar_activity = "normal"
        self.last_update = time.time()
        self.update_interval = 180

    def update(self):
        now = time.time()
        if now - self.last_update < self.update_interval:
            return self.solar_activity

        r = random.random()
        if r < 0.05:
            self.solar_activity = "storm"
            print("[SPACE WEATHER] ⚡ Solar storm detected!")
        elif r < 0.2:
            self.solar_activity = "active"
            print("[SPACE WEATHER] Solar activity elevated")
        else:
            self.solar_activity = "normal"

        self.last_update = now
        return self.solar_activity

    def get_communication_impact(self):
        if self.solar_activity == "storm":
            return {"snr_reduction": 15.0, "blackout_probability": 0.3, "radiation_alert": True}
        elif self.solar_activity == "active":
            return {"snr_reduction": 6.0, "blackout_probability": 0.05, "radiation_alert": False}
        return {"snr_reduction": 0.0, "blackout_probability": 0.0, "radiation_alert": False}


# ========== TELEMETRY PROCESSOR ==========
class TelemetryProcessor(space_telemetry_pb2_grpc.TelemetryServiceServicer):
    def __init__(self):
        self.power = PowerSystem()
        self.weather = SpaceWeather()
        self.active_sos = {}
        self.sos_cleanup_interval = 3600
        self.last_cleanup = time.time()

    def SendTelemetry(self, request, context):
        # Update power and check if we can proceed
        self._maybe_cleanup_sos()
        if not self.power.can_perform('telemetry_collection'):
            return space_telemetry_pb2.TelemetryData(spacecraft_id=request.spacecraft_id, timestamp=request.timestamp)

        self.power.set_mode('telemetry_collection')
        telemetry = self._process_telemetry(request)
        anomalies = self._detect_anomalies(telemetry)

        if anomalies:
            self._trigger_alerts(telemetry, anomalies)

        telemetry = self._handle_post_anomaly_metadata(telemetry, anomalies)
        self._calculate_doppler(telemetry)

        compressed = self._compress_telemetry(telemetry, anomalies)
        noisy = self._simulate_signal_noise(compressed)

        if not noisy:
            return space_telemetry_pb2.TelemetryData(spacecraft_id=request.spacecraft_id, timestamp=request.timestamp)

        corrected = self._apply_error_correction(noisy)

        if not self.power.can_perform('data_transmission'):
            print("[EDGE] Queuing for later transmission due to low power")
            return corrected

        self.power.set_mode('data_transmission')
        self._transmit(corrected, anomalies)
        self.power.set_mode('idle')
        return corrected

    # ========== HELPERS ==========

    def _maybe_cleanup_sos(self):
        now = time.time()
        if now - self.last_cleanup < self.sos_cleanup_interval:
            return
        self.last_cleanup = now
        for sc_id in list(self.active_sos.keys()):
            self.active_sos[sc_id] = {k: v for k, v in self.active_sos[sc_id].items() if now - v < 86400}
            if not self.active_sos[sc_id]:
                del self.active_sos[sc_id]

    def _process_telemetry(self, request):
        return space_telemetry_pb2.TelemetryData(
            spacecraft_id=request.spacecraft_id,
            timestamp=request.timestamp,
            position_x=request.position_x + 1,
            position_y=request.position_y + 1,
            position_z=request.position_z + 1,
            velocity_x=request.velocity_x,
            velocity_y=request.velocity_y,
            velocity_z=request.velocity_z,
            temperature=request.temperature
        )

    def _detect_anomalies(self, telemetry):
        anomalies = []
        
        # More realistic temperature thresholds (-150°C to 100°C is typical range)
        if telemetry.temperature < -100:
            anomalies.append(f"CRITICAL: Extreme low temperature: {telemetry.temperature:.1f}°C")
        elif telemetry.temperature < -80:
            anomalies.append(f"WARNING: Low temperature: {telemetry.temperature:.1f}°C")
        elif telemetry.temperature > 80:
            anomalies.append(f"CRITICAL: Extreme high temperature: {telemetry.temperature:.1f}°C")
        elif telemetry.temperature > 50:
            anomalies.append(f"WARNING: High temperature: {telemetry.temperature:.1f}°C")
        
        # Velocity anomalies (based on mission type)
        v_mag = math.sqrt(telemetry.velocity_x**2 + telemetry.velocity_y**2 + telemetry.velocity_z**2)
        if v_mag > 50:  # 50 km/s is very high
            anomalies.append(f"CRITICAL: Excessive velocity: {v_mag:.2f} km/s")
        
        # Distance anomalies (based on mission type)
        pos_mag = math.sqrt(telemetry.position_x**2 + telemetry.position_y**2 + telemetry.position_z**2)
        if pos_mag > 5 * 149597870.7:  # Beyond 5 AU
            anomalies.append(f"WARNING: Beyond expected operational range: {pos_mag/149597870.7:.2f} AU")
            
        return anomalies

    def _trigger_alerts(self, telemetry, anomalies):
        print(f"[EDGE] ALERT for {telemetry.spacecraft_id}: {anomalies}")

    def _handle_post_anomaly_metadata(self, telemetry, anomalies):
        telemetry.anomaly_detected = bool(anomalies)
        telemetry.anomaly_count = len(anomalies)
        telemetry.anomaly_descriptions = ";".join(anomalies)
        telemetry.anomaly_severity = "critical" if len(anomalies) > 2 else "warning"
        return telemetry

    def _calculate_doppler(self, telemetry):
        c = 299_792_458
        freq = 8.4e9
        shift = freq * (telemetry.velocity_x / c)
        telemetry.doppler_shift_hz = shift
        telemetry.carrier_freq_hz = freq
        print(f"[COMM] Doppler shift: {shift/1e3:.1f} kHz")

    def _compress_telemetry(self, telemetry, anomalies):
        # Placeholder compression (simulate delay)
        priority = 2 if "CRITICAL" in telemetry.anomaly_severity else 1 if anomalies else 0
        ratio = [0.4, 0.7, 0.9][priority]
        delay = (1024 * ratio) / 2048
        time.sleep(min(delay, 0.5))
        return telemetry

    def _simulate_signal_noise(self, telemetry):
        self.weather.update()
        impact = self.weather.get_communication_impact()
        distance = math.sqrt(telemetry.position_x**2 + telemetry.position_y**2 + telemetry.position_z**2)
        snr = max(1, 30 * (1_000_000 / distance)**2 - impact["snr_reduction"])
        loss_prob = min(0.95, 1 - min(0.99, 30 / max(snr, 1)) + impact["blackout_probability"])
        time.sleep(min(distance / 299_792_458 / 60, 2.0))
        if random.random() < loss_prob:
            print("[SIGNAL] ❌ Packet lost")
            return None
        return telemetry

    def _apply_error_correction(self, telemetry):
        size = 64  # assume 64 bytes
        parity = int(size * 0.15)
        telemetry.error_correction_type = "RS(255,223)"
        telemetry.data_bytes = size
        telemetry.parity_bytes = parity
        telemetry.error_correction_capability = parity // 2
        print(f"[COMM] ECC applied: can fix {parity // 2} bytes")
        return telemetry

    def _transmit(self, telemetry, anomalies):
        checksum = self._checksum(telemetry)
        for i in range(3):
            try:
                stub = space_telemetry_pb2_grpc.TelemetryServiceStub(
                    grpc.insecure_channel("localhost:50053"))
                response = stub.SendTelemetry(telemetry)
                if self._verify(response, checksum):
                    print(f"[EDGE] ✅ Transmitted on attempt {i+1}")
                    return
                raise ValueError("Checksum mismatch")
            except Exception as e:
                print(f"[EDGE] ❌ Attempt {i+1} failed: {e}")
                time.sleep(1.5 ** i)
        print("[EDGE] 🔁 Trying backup channel")
        self._backup_channel(telemetry)

    def _checksum(self, telemetry):
        values = [
            telemetry.position_x, telemetry.position_y, telemetry.position_z,
            telemetry.velocity_x, telemetry.velocity_y, telemetry.velocity_z,
            telemetry.temperature
        ]
        return sum(math.isnan(v) and 0 or v for v in values)

    def _verify(self, response, expected):
        return abs(response.temperature - expected) < 0.1  # Reused temp field for checksum

    def _backup_channel(self, telemetry):
        try:
            stub = space_telemetry_pb2_grpc.TelemetryServiceStub(
                grpc.insecure_channel("localhost:50054"))
            stub.SendTelemetry(telemetry)
            print("[EDGE] ✅ Backup successful")
        except Exception as e:
            print(f"[EDGE] 🔴 Backup failed: {e}")


# ========== SERVER ==========
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    space_telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(
        TelemetryProcessor(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    print("Edge Processing Server started on port 50052")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)
        print("Server stopped")


if __name__ == "__main__":
    serve()
