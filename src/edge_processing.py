import grpc
from concurrent import futures
import time
import space_telemetry_pb2 as space_telemetry_pb2, space_telemetry_pb2_grpc as space_telemetry_pb2_grpc

class TelemetryProcessor(space_telemetry_pb2_grpc.TelemetryServiceServicer):
    def SendTelemetry(self, request, context):
        print(f"[EDGE] Received telemetry: {request.spacecraft_id} @ {request.timestamp}")
        
        processed_telemetry = space_telemetry_pb2.TelemetryData(
            spacecraft_id=request.spacecraft_id,
            timestamp=request.timestamp,
            position_x=request.position_x + 1,  # Simulated processing
            position_y=request.position_y + 1,
            position_z=request.position_z + 1,
            velocity_x=request.velocity_x,
            velocity_y=request.velocity_y,
            velocity_z=request.velocity_z,
            temperature=request.temperature
        )

        if processed_telemetry.temperature < -50 or processed_telemetry.temperature > 50:
            print("[EDGE] Anomaly detected: Temperature out of range!")

        # ✅ Forward to Receiver
        try:
            with grpc.insecure_channel("localhost:50053") as channel:
                stub = space_telemetry_pb2_grpc.TelemetryServiceStub(channel)
                response = stub.SendTelemetry(processed_telemetry)
                print(f"[EDGE] Forwarded to receiver | Response: {response}")
        except Exception as e:
            print(f"[EDGE] Failed to send to receiver: {e}")

        return processed_telemetry  # Or return response, depending on what you want


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    space_telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(TelemetryProcessor(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    print(" Edge Processing gRPC Server Running on Port 50052...")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
