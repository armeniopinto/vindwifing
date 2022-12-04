'''Start-up things like WiFi and stuff.'''

__author__ = "Arménio Pinto"
__email__ = "github.com/armeniopinto"
__copyright__ = "Copyright (C) 2022 by Arménio Pinto"
__license__ = "MIT License"

import utime
from machine import SoftUART, Pin

import logging
logger = logging.getLogger(__name__)

from system import System
from homie import Network, Device, DeviceState, Node, Property


class Publisher:
	'''A publisher for the sensor values.'''

	def __init__(self, system:System) -> None:
		self.__device_id = system.device_id
		self.__broker_address = system.config.get("mqtt.broker.host_address")
		self.__broker_port = system.config.get("mqtt.broker.port")
		if not self.__broker_port:
			self.__broker_port = 1883
		try:
			self.__connect()
		except ConnectionError as ce:
			logger.warn(ce)


	def __connect(self) -> None:
		''':raises ConnectionError: if an error occurs while connecting to the message broker.'''
		self.__property = None
		try:
			network = Network(self.__device_id, self.__broker_address, self.__broker_port)
			device = Device(network, self.__device_id.lower(), self.__device_id)
			node = Node(device, "pm1006", "Cubic PM1006", "Air Quality Sensor")
			self.__property = Property(node, "pm2_5", "Particulate Matter Concentration (PM2.5)", "float", "ug/m3")
			node.add_property(self.__property)
			device.add_node(node)
			device.state = DeviceState.INIT
			device.state = DeviceState.READY
		except Exception as e:
			raise ConnectionError("Error connecting to message broker") from e


	def publish(self, message:str) -> None:
		''':raises ConnectionError: if an error occurs while connecting to the message broker.'''
		if not self.__property:
			try:
				self.__connect()
			except ConnectionError as ce:
				logger.warn(ce)
		if self.__property:
			try:
				self.__property.set_value(message)
			except Exception as e:
				raise ConnectionError("Error publishing the value") from e


class VindriktningReader:
	'''A client for the VINDRIKTNING sensor.'''

	# The number of samples in a sensor sampling cycle.
	__CYCLE_SAMPLES = 7

	# The amount of time after which a sampling cycle is considered finished.
	__CYCLE_TIMEOUT = 4


	def __init__(self, system:System, publisher:Publisher) -> None:
		self.__system = system
		self.__publisher = publisher

		# https://github.com/micropython/micropython/pull/7784
		tx_pin = system.config.get("uart.tx_pin")
		self.__rx_pin = system.config.get("uart.rx_pin")
		self.__uart = SoftUART(Pin(tx_pin), Pin(self.__rx_pin), baudrate=9600, timeout=0)

		self.__stop_requested = False
		self.__buffer = []


	def start(self) -> None:
		logger.info(f"Sensor reader started on pin {self.__rx_pin}.")
		while not self.__stop_requested:
			try:
				data = self.__uart.read()
				if data:
					self.__handle_sensor_data(data)
				self.__publish_if_cycle_ended()
			except Exception as e:
				logger.warning(f"Error handling sensor data: {str(e)}.")
			finally:
				utime.sleep_ms(500)
		logger.info("Sensor reader stopped.")


	def __handle_sensor_data(self, data:bytes) -> None:
		'''Handles data events from the sensor.'''
		timestamp = self.__system.time.time()
		try:
			value = self.__decode_sensor_data(data)
			if value >=0 and value <= 1000:
				sample = {
					"timestamp": timestamp,
					"pm2_5": value
				}
				self.__buffer.append(sample)
				logger.debug(f"Read data: {sample}.")
		except ValueError as ve:
			logger.info(f"Error decoding sensor data: {str(ve)}.")


	def __decode_sensor_data(self, data:bytes) -> int:
		'''Decodes a bunch of data from the sensor. Assumes 1 or more complete
		frames of data in the parameter. Returns the average of the values.
		:param data: the data received from the sensor.
		:returns: the decoded value.
		'''
		# From PM1006_LED_PARTICLE_SENSOR_MODULE_SPECIFICATIONS:
		# "Read measures result of particles:
		# Send: 11 02 0B 01 E1
		# Response: 16 11 0B DF1 DF4 DF5 DF8 DF9 DF12 DF13 DF14 DF15 DF16[CS]
		# Note: PM2.5(μg/m³)= DF3*256+DF4"
		# Additional comments: the second octet is the length of the data.
		# Other DFs are missing from the example above :), poor documentation.
		nframes = int(len(data) / 20)
		sum_values = 0
		for i in range(nframes):
			offset = i * 20
			frame_type = data[offset]
			if frame_type != 0x16:
				raise ValueError(f"Invalid data frame type, expecting 0x16, received {hex(frame_type)}")
			data_length = data[offset + 1]
			if data_length != 17:
				raise ValueError(f"Invalid data frame length, expecting 17 bytes, received {data_length} bytes")
			df3 = data[offset + 5]
			df4 = data[offset + 6]
			value = df3 * 256 + df4
			sum_values += value

		return int(sum_values / nframes)


	def __publish_if_cycle_ended(self) -> None:
		'''Publishes the sampled values if the sensor sampling cycled has ended. A cycle has ended when
		CYCLE_SAMPLES have been read or no more samples were read after CYCLE_TIMEOUT seconds.
		'''
		buffer = self.__buffer
		if buffer:
			nsamples = len(buffer)
			last_sample_time = buffer[-1]["timestamp"]
			current_time = self.__system.time.time()
			timedout = (current_time - last_sample_time) > self.__CYCLE_TIMEOUT
			if nsamples >= self.__CYCLE_SAMPLES or timedout:
				value_sum = 0
				for sample in buffer:
					value_sum += sample["pm2_5"]
				value = round(value_sum / nsamples, 1)
				datetime = self.__system.time.iso_time(last_sample_time)
				logger.info(f"Publishing {value} ug/m3 at {datetime}.")
				self.__publisher.publish(str(value))
				buffer.clear()


	def stop(self):
		'''Stops reading data from the sensor.'''
		self.__stop_requested = True
		self.__uart.deinit()


def main():
	system = System()
	publisher = Publisher(system)
	vind_reader = VindriktningReader(system, publisher)
	vind_reader.start()


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		logger.info("Exiting...")
