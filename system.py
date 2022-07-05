'''System-related functionality.'''

__author__ = "Arménio Pinto"
__email__ = "github.com/armeniopinto"
__copyright__ = "Copyright (C) 2022 by Arménio Pinto"
__license__ = "MIT License"

#import gc
#gc.enable()
import network, utime, ntptime, json
from network import WLAN

import logging
logger = logging.getLogger(__name__)


__CONFIG_FILE_PATH = "config.json"

class __Config:
	"""A wrapper to manage loading and CRUD of configuration."""

	def __init__(self) -> None:
		config_file = None
		try:
			config_file = open(__CONFIG_FILE_PATH, "r")
		except OSError as ose:
			logger.error(f"Unable to open configuration file '{__CONFIG_FILE_PATH}'.")
		if config_file:
			with config_file:
				self.__config = json.load(config_file)
			logger.info("Configuration loaded.")

	def has(self, name:str) -> None:
		"""Check if a given property is configured.
		:param name: the property's name.
		:returns: True if the property exists, otherwise False.
		"""
		return self.get(name) != None

	def get(self, name:str) -> any:
		'''Returns a property's value.
		:param: the property's name.
		:returns: the property's value or None, if it wasn't found.
		'''
		value = self.__config
		for token in name.split("."):
			if token in value:
				value = value[token]
			else:
				return None
		return value


class __Time:
	'''An agent for time functionality.'''

	# The number of retries to sync with the NTP server.
	__NTP_RETRIES = 5

	def __init__(self, config:__Config, online:bool=True):
		self.__NTP_SYNC_PERIOD = config.get("network.ntp.sync_period")
		self.__last_ntp_sync = None

	def sync(self) -> None:
		'''Sets the RTC with date/time from an NTP server.
		:returns: the time retrieved from the NTP server, or the current RTC time if it failed.
		'''
		for i in range(self.__NTP_RETRIES):
			try:
				ntptime.settime()
				logger.info(f"RTC time set to '{self.iso_time()}'.")
				return utime.time()
			except Exception as e:
				logger.info(f"Error retrieving NTP time: {str(e)}.")
				utime.sleep_ms(1000)
		logger.warning("Unable to get NTP time, RTC will have an arbitrary reference.")
		return utime.time()

	def time(self) -> int:
		'''Returns the number of seconds since the Epoch (2000-01-01 00:00:00 UTC).
		Syncs the time with the NTP server every refresh_period seconds (300 by default).
		'''
		current_time = utime.time()
		if not self.__last_ntp_sync or current_time - self.__last_ntp_sync > self.__NTP_SYNC_PERIOD:
			self.__last_ntp_sync = self.sync()
			return self.__last_ntp_sync
		else:
			return utime.time()

	def iso_time(self, datetime:int=None) -> str:
		'''Returns the time in ISO 8601 format. If no argument is passed, uses the RTC time.
		:param datetime: the number of seconds since the Epoch (2000-01-01 00:00:00 UTC).
		'''
		tokens = utime.localtime(datetime)
		return "%04d-%02d-%02d %02d:%02d:%02d+00:00"%(tokens[0:6])


class __WLAN:
	'''A wrapper for network.WLAN.'''

	def __init__(self, if_id:int, ssid:str, key:str) -> None:
		''':param wlan_type: see the 'network' module.'''
		self.__if_id = if_id
		self.__wlan_if = WLAN(if_id)
		self.__if_name = "AP" if if_id == network.AP_IF else "Station" if if_id == network.STA_IF else "Unknown"
		self.__ssid = ssid
		self.__key = key

	@property
	def ssid(self) -> str:
		return self.__ssid

	def start(self) -> None:
		'''Starts the WLAN interface, connecting to the AP if it's a station.'''
		if not self.__wlan_if.active():
			self.__wlan_if.active(True)
			logger.info(f"{self.__if_name} interface is now UP.")
		else:
			logger.debug(f"{self.__if_name} interface was already UP.")

		if self.__if_id == network.AP_IF:
			current_essid = self.__wlan_if.config("essid")
			if current_essid != self.__ssid:
				self.__wlan_if.config(essid = self.__ssid, password = self.__key)
				logger.info(f"AP ESSID changed from '{current_essid}' to '{self.__ssid}'.")
			logger.info(f"AP running with ESSID '{self.__ssid}'.")

		elif self.__if_id == network.STA_IF:
			connected = False
			self.__wlan_if.connect(self.__ssid, self.__key)
			while not connected:
				utime.sleep_ms(3000)
				if self.__wlan_if.isconnected():
					connected = True
				else:
					logger.info(f"Trying to connect to '{self.__ssid}'...")
			ifcfg = self.__wlan_if.ifconfig()
			logger.info(f"Connected to '{self.__ssid}': IP={ifcfg[0]} GW={ifcfg[2]} DNS={ifcfg[3]}")

	def stop(self) -> None:
		'''Stops the WLAN interface, disconnecting from the AP if it's a station.'''
		if self.__wlan_if.active():
			if self.__if_id == network.STA_IF:
				if self.__wlan_if.isconnected():
					self.__wlan_if.disconnect()
					logger.info(f"Disconnected from {self.__ssid}.")
			self.__wlan_if.active(False)
			self.info(f"{self.__if_name} interface is now DOWN.")
		else:
			self.debug(f"{self.__if_name} interface was already DOWN.")


class __Network:
	'''An agent for network functionality.'''

	def build_ap_essid() -> None:
		'''Builds a unique ESSID for the AP.'''
		ap_if = WLAN(network.AP_IF)
		mac = list(ap_if.config("mac"))
		return "VINDRIKTNING-" + "%0.2X%0.2X%0.2X" % (mac[3], mac[4], mac[5])

	def __init__(self, config:__Config) -> None:
		ap_essid = __Network.build_ap_essid()
		ap_config = config.get("network.ap")
		self.__ap = __WLAN(network.AP_IF, ap_essid, ap_config["key"]) if ap_config else None
		station_config = config.get("network.station")
		self.__station = __WLAN(network.STA_IF, station_config["ssid"], station_config["key"]) if station_config else None

	@property
	def ap(self):
		'''Returns the AP agent.'''
		return self.__ap

	@property
	def station(self):
		'''Returns the station agent.'''
		return self.__station

	def start(self) -> None:
		'''Starts the network functionality.'''
		if self.__ap:
			self.__ap.start()
		if self.__station:
			self.__station.start()

	def stop(self) -> None:
		'''Stops the network functionality.'''
		if self.__ap:
			self.__ap.stop()
		if self.__station:
			self.__station.stop()


class System:
	'''An agent for system-related functionality.'''

	def __init__(self) -> None:
		self.__config = __Config()
		self.__network = __Network(self.__config)
		self.__time = __Time(self.__config)

	@property
	def device_id(self) -> str:
		'''Returns the unique device identifier.'''
		return self.network.ap.ssid

	@property
	def config(self) -> __Config:
		'''Returns the configuration agent.'''
		return self.__config

	@property
	def time(self) -> __Time:
		'''Returns the data/time agent.'''
		return self.__time

	@property
	def network(self) -> __Network:
		'''Returns the network agent.'''
		return self.__network

	#def gc_collect() -> None:
	#	gc.collect()
	#	gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())	
	#	logger.debug("Heap memory garbage collected.")
	#	logger.debug(f"Using {gc.mem_alloc()} bytes of heap memory, with {gc.mem_free()} bytes free.")
