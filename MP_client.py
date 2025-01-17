import random
import string
import json, pickle
import logging
from datetime import datetime
from threading import Thread, Event
from jsonschema import validate, exceptions as jsonschema_exceptions
from protocols.amqp.receive import Receiver
from protocols.amqp.send import Sender
from utils.message import Message
from utils.broker import Broker

class MeasurementPlaneClient:
    def __init__(self, broker_url) -> None:
        self.broker_url = broker_url
        self.sender = Sender()
        self.broker = Broker(self.broker_url)
        self.broker.start()

    def get_capabilities(self, capability_types: list = None) -> dict:
        capabilities_event = Event()
        capabilities = {}

        def capabilities_receiver_on_message_callback(event):
            nonlocal capabilities
            try:
                capabilities = json.loads(event.message.body)
                if capability_types:
                    keys_to_delete = [cp_id for cp_id in capabilities if capabilities[cp_id]['capability'] not in capability_types]
                    for cp_id in keys_to_delete:
                        del capabilities[cp_id]
            except KeyError as e:
                logging.error(f"KeyError: {e}. Missing required keys in capability_body.")
            finally:
                capabilities_event.set()
                event.container.stop()

        topic = 'topic:///get_capabilities'
        reply_to_topic = 'topic://' + ''.join(random.choices(string.ascii_letters + string.digits, k=10))

        capabilities_receiver = Receiver(on_message_callback=capabilities_receiver_on_message_callback)
        thread_capabilities_receiver = Thread(target=capabilities_receiver.receive_event, args=(self.broker_url, reply_to_topic))
        thread_capabilities_receiver.start()

        self.sender.send(self.broker_url, topic, "", reply_to_topic)

        capabilities_event.wait(timeout=2)
        capabilities_receiver.container.stop()
        thread_capabilities_receiver.join()
        # Create a list of the dictionary's keys
        keys = list(capabilities.keys())

        i = 0
        for id in keys:
            capabilities[i] = capabilities.pop(id)
            i += 1
        return capabilities if capabilities else {}

    def combine_to_string(self, attributes: list) -> str:
        return ''.join(str(att).replace(" ", "").replace("\n", "") for att in attributes)
    
    def calculate_capability_id(self, message):
        return Message.calculate_capability_id(message=message)

    def create_measurement(self, capability: dict) -> 'Measurement':
        return Measurement(capability, self)

    def send_measurement(self, measurement: 'Measurement'):
        specification_topic = "topic:///specifications"
        reply_to_topic = 'topic://' + ''.join(random.choices(string.ascii_letters + string.digits, k=10))

        measurement.receipt_receiver = Receiver(on_message_callback=measurement.receipt_receiver_on_message_callback)
        thread_receipt_receiver = Thread(target=measurement.receipt_receiver.receive_event, args=(self.broker_url, reply_to_topic))
        thread_receipt_receiver.start()

        self.sender.send(self.broker_url, specification_topic, measurement.specification_message, reply_to_topic)

        thread_receipt_receiver.join(timeout=2)
        measurement.receipt_receiver.container.stop()

    def interrupt_measurement(self, measurement: 'Measurement'):
        measurement.interrupt()

class Measurement:
    def __init__(self, capability: dict, measurement_plane_client: MeasurementPlaneClient):
        self.measurement_plane_client = measurement_plane_client
        self.broker_url = self.measurement_plane_client.broker_url
        self.capability = capability
        self.results_receiver = None
        self.results = []
        self.config = {}
        self.specification_message = capability.copy()
        self.specification_message['specification'] = self.specification_message.pop('capability')

    def configure(self, schedule: dict, parameters: dict, result_callback, stream_results: bool = False, redirect_to_storage: bool = False, completion_callback = None) -> bool:
        if self.validate_parameters(parameters):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
            self.specification_message.update({
                'parameters': parameters,
                'schedule': schedule,
                'timestamp': timestamp
            })
            self.config = {
                "stream_results": stream_results,
                "redirect_to_storage": redirect_to_storage,
                "result_callback": result_callback,
                "completion_callback": completion_callback
            }
            return True
        return False

    def receipt_receiver_on_message_callback(self, event):
        receipt_msg = json.loads(event.message.body)
        if 'receipt' in receipt_msg:
            event.container.stop()
            if 'interrupt' in receipt_msg:
                logging.info("Measurement interrupted.")
            else:
                if self.results_receiver is None:
                    measurement_id = Message.calculate_measurement_id(message = receipt_msg)
                    self.results_receiver = Receiver(on_message_callback=self.result_receiver_on_message_callback)
                    topic = f'topic://{measurement_id}/results'
                    self.results_receiver.receive_event(self.broker_url, topic)

    def result_receiver_on_message_callback(self, event):
        message_body = event.message.body

        # Convert memoryview to bytes if necessary
        if isinstance(message_body, memoryview):
            message_body = message_body.tobytes()

        # Try to decode as JSON or fall back to pickle
        result_msg = None
        if isinstance(message_body, bytes):
            # If it's bytes, assume it's pickled binary data
            try:
                result_msg = pickle.loads(message_body)
                logging.info("Successfully received and deserialized the message using pickle.")
            except pickle.UnpicklingError as e:
                logging.error(f"Failed to deserialize message with pickle: {e}")
                result_msg = None
        else:
            try:
                result_msg = json.loads(message_body)
                logging.info("Successfully received and decoded the message using JSON.")
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as e:
                logging.error(f"Failed to decode message as JSON: {e}")
                result_msg = None

        # Proceed if decoding was successful
        if result_msg and 'result' in result_msg:
            results = result_msg['resultValues']
            logging.info(f"Received results: {results}")
            if 'EOF_results' in results:
                print("EOF received will stop")
                self.config['result_callback'](results)
                self.stop()
                return
            self.config['result_callback'](results)
            self.results.append(results)
            
    def interrupt(self):
        interrupt_msg = self.specification_message
        interrupt_msg['capability'] = interrupt_msg['specification']
        interruption = Measurement(interrupt_msg, self.measurement_plane_client)
        interrupt_msg = interruption.specification_message
        interrupt_msg['interrupt'] = interrupt_msg['specification']
        del interrupt_msg['specification']
        interruption.message = interrupt_msg
        self.measurement_plane_client.send_measurement(interruption)
        self.stop()
        
    def stop(self):
        if self.results_receiver:
            self.results_receiver.container.stop()

    def validate_parameters(self, parameters: dict) -> bool:
        try:
            validate(instance=parameters, schema=self.capability['parameters_schema'])
            return True
        except jsonschema_exceptions.ValidationError as err:
            logging.error(f"Validation error: {err.message}")
            return False
