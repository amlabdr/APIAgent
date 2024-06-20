import time
import random
import string
import json
import hashlib
import logging
from datetime import datetime
from threading import Thread, Event
from jsonschema import validate, exceptions as jsonschema_exceptions
from protocols.amqp.receive import Receiver
from protocols.amqp.send import Sender

#logging.basicConfig(level=logging.INFO)

class MeasurementPlane:
    @staticmethod
    def get_capabilities(capability_type: str = None, broker_url: str = "") -> dict:
        capabilities_event = Event()
        capabilities = {}

        def capabilities_receiver_on_message_callback(event):
            nonlocal capabilities
            try:
                capabilities = json.loads(event.message.body)
                keys_to_delete = [cp_id for cp_id in capabilities if capabilities[cp_id]['capability'] != capability_type]
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
        thread_capabilities_receiver = Thread(target=capabilities_receiver.receive_event, args=(broker_url, reply_to_topic))
        thread_capabilities_receiver.start()

        sender = Sender()
        sender.send(broker_url, topic, "", reply_to_topic)

        capabilities_event.wait(timeout=2)
        capabilities_receiver.container.stop()
        thread_capabilities_receiver.join()

        return capabilities if capabilities else {}

    @staticmethod
    def calculate_capability_id(capability_body: dict) -> str:
        try:
            endpoint = capability_body["endpoint"]
            capability_name = capability_body["capabilityName"]
            combined_string = MeasurementPlane.combine_to_string([endpoint, capability_name])
            capability_id = hashlib.sha256(combined_string.encode()).hexdigest()
            return capability_id
        except KeyError as e:
            logging.error(f"KeyError: {e}. Missing required keys in capability_body.")
            return None

    @staticmethod
    def combine_to_string(attributes: list) -> str:
        return ''.join(str(att).replace(" ", "").replace("\n", "") for att in attributes)

    @staticmethod
    def create_measurement(capability: dict) -> 'Measurement':
        return Measurement(capability)

    @staticmethod
    def send_measurement(measurement: 'Measurement', broker_url: str = ""):
        specification_topic = "topic:///specifications"
        measurement.broker_url = broker_url
        reply_to_topic = 'topic://' + ''.join(random.choices(string.ascii_letters + string.digits, k=10))

        measurement.receipt_receiver = Receiver(on_message_callback=measurement.receipt_receiver_on_message_callback)
        thread_receipt_receiver = Thread(target=measurement.receipt_receiver.receive_event, args=(measurement.broker_url, reply_to_topic))
        thread_receipt_receiver.start()

        sender = Sender()
        sender.send(measurement.broker_url, specification_topic, measurement.specification_message, reply_to_topic)

        thread_receipt_receiver.join(timeout=2)
        measurement.receipt_receiver.container.stop()

    @staticmethod
    def interrupt_measurement(measurement: 'Measurement'):
        measurement.interrupt()

class Measurement:
    def __init__(self, capability: dict):
        self.broker_url = ''
        self.capability = capability
        self.results_receiver = None
        self.results = []
        self.config = {}
        self.specification_message = capability.copy()
        self.specification_message['specification'] = self.specification_message.pop('capability')

    def configure(self, schedule: dict, parameters: dict, stream_results: bool, redirect_to_storage: bool, result_callback, completion_callback) -> bool:
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
                    measurement_id = Measurement.calculate_measurement_id(receipt_msg)
                    self.results_receiver = Receiver(on_message_callback=self.result_receiver_on_message_callback)
                    topic = f'topic://{measurement_id}/results'
                    self.results_receiver.receive_event(self.broker_url, topic)

    def result_receiver_on_message_callback(self, event):
        result_msg = json.loads(event.message.body)
        if 'result' in result_msg:
            results = result_msg['resultValues']
            logging.info(f"Received results: {results}")
            self.config['result_callback'](results)
            if results == 'EOF':
                event.container.stop()
            self.results.append(results)

    def interrupt(self):
        interrupt_msg = self.specification_message
        interrupt_msg['capability'] = interrupt_msg['specification']
        interruption = Measurement(interrupt_msg)
        interrupt_msg = interruption.specification_message
        interrupt_msg['interrupt'] = interrupt_msg['specification']
        del interrupt_msg['specification']
        interruption.message = interrupt_msg
        MeasurementPlane.send_measurement(interruption, self.broker_url)
        if self.results_receiver:
            self.results_receiver.container.stop()

    @staticmethod
    def calculate_measurement_id(message_body: dict) -> str:
        capability_id = MeasurementPlane.calculate_capability_id(message_body)
        parameters = message_body["parameters"]
        schedule = message_body["schedule"]
        combined_string = MeasurementPlane.combine_to_string([capability_id, parameters, schedule])
        return hashlib.sha256(combined_string.encode()).hexdigest()

    def validate_parameters(self, parameters: dict) -> bool:
        try:
            validate(instance=parameters, schema=self.capability['parameters'])
            return True
        except jsonschema_exceptions.ValidationError as err:
            logging.error(f"Validation error: {err.message}")
            return False
