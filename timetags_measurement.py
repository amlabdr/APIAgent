import time
from MP_client import MeasurementPlaneClient

def on_result_callback(result):
    print(f"New Result Received: {result}")

def on_completion_callback(status):
    print(f"Measurement Completed with Status: {status}")

BROKER_URL = "http://129.6.254.164:5672/"
# Step 1: Get the capabilities published by agents
mpClient = MeasurementPlaneClient(BROKER_URL)

capabilities = mpClient.get_capabilities(capability_type="measure")
print("Available Capabilities:", capabilities)

capability_id = 0  # Ensure this corresponds to the correct capability for timetags
capability = capabilities[capability_id]
# Step 3: Instantiate a specification of a measurement from the capability
measurement = mpClient.create_measurement(capability)
print(f"Created Measurement: {measurement.specification_message}")

# Step 4: Configure the measurement with parameters
schedule = "now | 2024-08-15 22:50:00 | 2s "  # Replace with your schedule: `now / period`, `start ... stop / period`, etc.
parameters = {
    "channels": [1, 2, 3]  # Replace with appropriate channel numbers
    # Add more parameters based on the capability.parameters_schema YAML schema
}
measurement.configure(
    schedule=schedule,
    parameters=parameters,
    stream_results=False,  # Stream results
    redirect_to_storage=True,  # Redirect to storage
    result_callback=on_result_callback,  # Callback function for new results
    completion_callback=on_completion_callback  # Callback function for measurement completion
)
print(f"Configured Measurement Specification: {measurement.specification_message}")

# Step 5: Send the Measurement
mpClient.send_measurement(measurement)

# Step 6: Interrupt the measurement
mpClient.interrupt_measurement(measurement)
print(f"Measurement Interrupted")
