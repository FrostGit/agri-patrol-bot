# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

# Outputs a 50% duty cycle PWM single on the 0th channel.
# Connect an LED and resistor in series to the pin
# to visualize duty cycle changes and its impact on brightness.

import board
from time import sleep

from adafruit_pca9685 import PCA9685

debug = True

# Create the I2C bus interface.
i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = busio.I2C(board.GP1, board.GP0)    # Pi Pico RP2040

# Create a simple PCA9685 class instance.
pca = PCA9685(i2c, address=0x41)

# Set the PWM frequency to 60hz.
pca.frequency = 60

# Set the PWM duty cycle for channel zero to 50%. duty_cycle is 16 bits to match other PWM objects
# but the PCA9685 will only actually give 12 bits of resolution.

print(f"Open fan")
pca.channels[10].duty_cycle = 0x2000
pca.channels[11].duty_cycle = 0x0000

print(f"Test Servo")
pca.channels[1].duty_cycle = 0x1300
sleep(1)
for i in range(0x1300,0x2000,0x5F):
	sleep(0.03)
	if debug:
		print(f"0x{i:02x}")
	pca.channels[1].duty_cycle = i


for i in range(0x2000,0x1000,-0x5F):
	sleep(0.03)
	if debug:
		print(f"0x{i:02x}")
	pca.channels[1].duty_cycle = i
	
for i in range(0x1000,0x1300,0x5F):
	sleep(0.03)
	if debug:
		print(f"0x{i:02x}")
	pca.channels[1].duty_cycle = i
	
