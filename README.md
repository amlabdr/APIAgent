# MP_client Measurement Library

The MP_client Measurement Library (`MP_client.py`) provides a flexible framework for managing and executing measurements via an AMQP (Advanced Message Queuing Protocol) broker. It allows you to configure measurements based on capabilities retrieved from agents, send measurement specifications, receive results, and handle interruptions seamlessly.

## Features

- **Capability Management**: Retrieve capabilities published by agents and filter based on type.
- **Measurement Configuration**: Configure measurements with schedules, parameters, and callbacks.
- **Result Streaming**: Stream measurement results as they arrive.
- **Interrupt Handling**: Gracefully interrupt measurements and handle interruptions from the broker.

## Documentation for `MP_client.py`

- **MeasurementPlane Class**: Provides methods to interact with the AMQP broker, retrieve capabilities, and manage measurements.
- **Measurement Class**: Represents a specific measurement instance, allowing configuration, interruption, and result handling.


