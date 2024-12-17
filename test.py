from proton import Message
from proton.handlers import MessagingHandler
from proton.reactor import Container

class PersistentReceiver(MessagingHandler):
    def __init__(self, broker_url, topic):
        super().__init__()
        self.broker_url = broker_url
        self.topic = topic

    def on_start(self, event):
        # Establish connection and create receiver
        print(f"Connecting to {self.broker_url}...")
        connection = event.container.connect(self.broker_url)
        event.container.create_receiver(connection, self.topic)
        print(f"Listening for messages on topic: {self.topic}")

    def on_message(self, event):
        # Print the received message
        print(f"Received message: {event.message.body}")

    def on_transport_error(self, event):
        print(f"Transport error: {event.transport.condition.description}")
        event.connection.close()

# Create and run the receiver container
if __name__ == "__main__":
    broker_url = "amqp://localhost:5672"  # Update with your broker's address if needed
    topic = "topic:///skopa"
    Container(PersistentReceiver(broker_url, topic)).run()
