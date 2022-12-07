'''Boots the device, setting-up things like network and configuration.'''

__author__ = "Arménio Pinto"
__email__ = "github.com/armeniopinto"
__copyright__ = "Copyright (C) 2022 by Arménio Pinto"
__license__ = "MIT License"

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from machine import Pin

from system import System


def main():
	'''The application's entry point.'''

	system = System()
	system.network.start()
	if system.config.has("network.station"):
		system.time.sync()
	else:
		logger.warning("Running offline, RTC will have an arbitrary time reference.")

	# Flags that everything is mostly okay :).
	Pin(2, Pin.OUT).off()
	logger.info("Boot process successfully completed.")


if __name__ == "__main__":
	main()
