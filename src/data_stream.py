import grpc
import time
import random
import space_telemetry_pb2 as space_telemetry_pb2, space_telemetry_pb2_grpc as space_telemetry_pb2_grpc

def generate_telemetry():
    return space_telemetry_pb2.TelemetryData(
        spacecraft_id="Voyager-1",
        timestamp=time.time(),
        position_x=random.uniform(-1000, 1000),
        position_y=random.uniform(-1000, 1000),
        position_z=random.uniform(-1000, 1000),
        velocity_x=random.uniform(-10, 10),
        velocity_y=random.uniform(-10, 10),
        velocity_z=random.uniform(-10, 10),
        temperature=random.uniform(-100, 100)
    )

def main():
    channel = grpc.insecure_channel("localhost:50052")
    stub = space_telemetry_pb2_grpc.TelemetryServiceStub(channel)

    while True:
        telemetry_data = generate_telemetry()
        try:
            response = stub.SendTelemetry(telemetry_data)
            print(f"Sent telemetry: {telemetry_data} | Response: {response.status}")
            time.sleep(60)
        except grpc.RpcError as e:
            print(f"[!] gRPC Error: {e.code()} - {e.details()}")
        
   


if __name__ == "__main__":
    main()
