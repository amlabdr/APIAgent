import time
from MP_client import MeasurementPlaneClient

def on_result_callback(result):
    print(f"New Result Received: {result}")

def on_completion_callback(status):
    print(f"Measurement Completed with Status: {status}")

def main():
    BROKER_URL = "http://129.6.254.164:5672/"
    # Step 1: Get the capabilities published by agents
    mpClient = MeasurementPlaneClient(BROKER_URL)
    capabilities = mpClient.get_capabilities(capability_type="measure")
    print("Available Capabilities:", capabilities)

    # Step 2: Pick up one capability (by endpoint and name)
    endpoint = "/multiverse/qnet/tt/Alice"  # Replace with an actual agent endpoint
    capability_name = "TimetagsMeasurementAlice"  # Replace with an actual capability name

    capability_id = mpClient.calculate_capability_id({"endpoint":endpoint, "capabilityName": capability_name})
    if capability_id in capabilities:
        capability = capabilities[capability_id]
    else:
        capability = None
    
    if not capability:
        print(f"Capability not found.")
        return

    print(f"Selected Capability: {capability}")

    # Step 3: Instantiate a specification of a measurement from the capability
    measurement = mpClient.create_measurement(capability)
    print(f"Created Measurement: {measurement.specification_message}")

    # Step 4: Configure the measurement with parameters
    schedule = "now"  # Replace with your schedule: `now / period`, `start ... stop / period`, etc.
    parameters = {
        "channels": [1,2]
        # Add more parameters based on the capability.parameters JSON schema
    }
    measurement.configure(
        schedule=schedule,
        parameters=parameters,
        stream_results=True,  # Stream results
        redirect_to_storage=True,  # Redirect to storage
        result_callback=on_result_callback,  # Callback function for new results
        completion_callback=on_completion_callback  # Callback function for measurement completion
    )
    print(f"Configured Measurement Specification: {measurement.specification_message}")

    # Step 5: Send the Measurement
    mpClient.send_measurement(measurement)

    # Simulate some wait time for the measurement to finish
    time.sleep(5)  # Wait for 5 seconds (replace with appropriate wait time)

    # Step 6: Interrupt the measurement
    mpClient.interrupt_measurement(measurement)
    print(f"Measurement Interrupted")
    print(f"Measurement Results: ", measurement.results)

if __name__ == "__main__":
    main()