'''A minimalistic Micropython implementation of the Homie convention (https://homieiot.github.io).'''

__author__ = "Arménio Pinto"
__email__ = "github.com/armeniopinto"
__copyright__ = "Copyright (C) 2022 by Arménio Pinto"
__license__ = "MIT License"

from umqtt.robust import MQTTClient

import logging
logger = logging.getLogger(__name__)


class HomieThing:
	'''A generic Homie entity.'''

	def __init__(self, parent:"HomieThing", thing_id:str, mqtt_broker:MQTTClient=None) -> None:
		self.__thing_id = thing_id
		self.parent = parent
		self.__mqtt_broker = mqtt_broker if mqtt_broker else parent.__mqtt_broker

	@property
	def thing_id(self) -> str:
		return self.__thing_id

	@property
	def parent(self) -> "HomieThing":
		return self.__parent

	@parent.setter
	def parent(self, parent:"HomieThing") -> None:
		self.__parent = parent
		self.__topic_name = f"{parent.__topic_name}/{self.__thing_id}" if parent else self.__thing_id

	def set_attribute(self, name:str, value:str) -> None:
		attribute_topic_name = f"{self.__topic_name}/{name}"
		logger.debug(f"{attribute_topic_name} = {value}")
		self.__mqtt_broker.publish(attribute_topic_name, value, retain=True, qos=1)

	def set_value(self, value:str) -> None:
		logger.debug(f"{self.__topic_name} = {value}")
		self.__mqtt_broker.publish(self.__topic_name, value, retain=True, qos=1)

	def __str__(self) -> str:
		return self.__thing_id


class NamedHomieThing(HomieThing):
	'''A Homie entity with a name.'''

	def __init__(self, parent:HomieThing, thing_id:str, name:str, mqtt_broker:MQTTClient=None) -> None:
		super().__init__(parent, thing_id, mqtt_broker)
		self.__name = name

	@property
	def name(self) -> str:
		return self.__name


class Property(NamedHomieThing):
	'''https://homieiot.github.io/specification/#properties'''

	def __init__(self, parent:HomieThing, thing_id:str, name:str, data_type:str, unit:str) -> None:
		super().__init__(parent, thing_id, name)
		self.__data_type = data_type
		self.__unit = unit

	def init(self) -> None:
		'''https://homieiot.github.io/specification/#device-lifecycle'''
		self.set_attribute("$name", self.__name)
		self.set_attribute("$datatype", self.__data_type)
		self.set_attribute("$unit", self.__unit)
		self.set_attribute("$retained", "true")
		self.set_attribute("$settable", "false")


class Node(NamedHomieThing):
	'''https://homieiot.github.io/specification/#nodes'''

	def __init__(self, parent:HomieThing, thing_id:str, name:str, thing_type:str) -> None:
		super().__init__(parent, thing_id, name)
		self.__thing_type = thing_type
		self.__properties = []

	@property
	def type(self) -> str:
		return self.__thing_id

	@property
	def properties(self) -> list[Property]:
		return self.__properties

	def add_property(self, property:Property) -> None:
		self.__properties.append(property)

	def init(self) -> None:
		'''https://homieiot.github.io/specification/#device-lifecycle'''
		self.set_attribute("$name", self.__name)
		self.set_attribute("$type", self.__thing_type)
		self.set_attribute("$properties", ",".join(map(str, self.__properties)))
		for property in self.__properties:
			property.init()


class DeviceState:
	'''https://homieiot.github.io/specification/#device-lifecycle'''

	INIT="init"
	READY="ready"
	DISCONNECTED="disconnected"
	SLEEPING="sleeping"
	LOST="lost"
	ALERT="alert"


class Device(NamedHomieThing):
	'''https://homieiot.github.io/specification/#devices'''

	def __init__(self, parent:HomieThing, thing_id:str, name:str, extensions:list[str]=[]) -> None:
		super().__init__(parent, thing_id, name)
		self.__nodes = []
		self.__extensions = extensions

	@property
	def nodes(self) -> list[Node]:
		return self.__nodes

	def add_node(self, node:Node) -> None:
		self.__nodes.append(node)

	@property
	def state(self) -> DeviceState:
		return self.__state

	@state.setter
	def state(self, new_state:str) -> None:
		if new_state == DeviceState.INIT:
			self.init()
		else:
			self.set_attribute("$state", DeviceState.READY)
		self.__state = new_state

	@property
	def extensions(self) -> list[str]:
		return self.__extensions

	def init(self) -> None:
		'''https://homieiot.github.io/specification/#device-lifecycle'''
		self.set_attribute("$state", DeviceState.INIT)
		self.set_attribute("$homie", "3.0.0")
		self.set_attribute("$name", self.__name)
		self.set_attribute("$nodes", ",".join(map(str, self.__nodes)))
		self.set_attribute("$extensions", ",".join(map(str, self.__extensions)))
		for node in self.__nodes:
			node.init()


class Network(HomieThing):

	def __init__(self, mqtt_client_id:str, mqtt_broker_address:str, mqtt_broker_port:int) -> None:
		mqtt_broker = MQTTClient(mqtt_client_id, mqtt_broker_address, mqtt_broker_port)
		logger.debug(f"Trying to connect to MQTT broker at '{mqtt_broker_address}:{mqtt_broker_port}'...")
		mqtt_broker.connect()
		logger.info(f"Connected to MQTT broker '{mqtt_broker_address}:{mqtt_broker_port}'.")
		super().__init__(None, "homie", mqtt_broker)
		self.__devices = []

	@property
	def devices(self) -> list[Device]:
		return self.__devices.copy()

	def add_device(self, device:Device) -> None:
		self.__devices.append(device)
