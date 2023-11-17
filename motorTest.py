#adc
import board
import time
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

#serial
import serial

# configuration parameters
motorPerEncoder = 2

# Initialize the I2C interface
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
channel = AnalogIn(ads, ADS.P0)

def go_to_position(desiredPosition):
    while abs(channel.value - desiredPosition) > 0:
        calculatedSteps = (desiredPosition - channel.value) * motorPerEncoder
        with serial.Serial("/dev/ttyUSB0", 115200) as connection:
            connection.write(("X1J" + str(int(calculatedSteps)) + ",0,500\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode()
            print("controller response: ", reading)
            print("encoder reading: ", channel.value)
'''
while True:
    print("Analog Value: ", channel.value, "Voltage: ", channel.voltage)
    with serial.Serial("/dev/ttyUSB0", 115200) as connection:
        print("conectado")
        connection.write(("X1?\r").encode("ascii"))
        reading = connection.read_until(b"\r").decode()
        print(reading)
    time.sleep(2)
'''
