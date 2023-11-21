#adc
import board
import time
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

import cothread
from softioc import softioc, builder, asyncio_dispatcher
import asyncio
import serial
import re

#General settings
# Set the record prefix
builder.SetDeviceName("CCTVAL_DT_PMD301")
motor_temperature_range = {"LOLO": 253, "LOW": 263, "HIGH": 350, "HIHI": 360}
debug = False

# Create some records
## User input records
user_target_position = builder.aOut('USER-TARGET-POSITION', initial_value = 20, always_update = True,
                          on_update = lambda v: set_target_position(v))
user_stop = builder.boolOut('SHOULD-STOP', initial_value = False, always_update = True,
                          on_update = lambda v: stop(v))
user_command = builder.stringOut('USER-MOTOR-COMMAND', initial_value = "", always_update = True,
                          on_update = lambda v: send_command(v))

## General information and controller status
controller_model = builder.stringIn('PIEZOMOTOR-CONTROLLER-VERSION', initial_value = "PMD301X")
cs_com_error = builder.boolIn('PIEZOMOTOR-CONTROLLER-COMMUNICATION-ERROR', initial_value = False) # Wrong baud rate, data collision or buffer overflow
cs_enc_error = builder.boolIn('PIEZOMOTOR-CONTROLLER-ENCODER-ERROR', initial_value = False)
cs_voltage_error = builder.boolIn('PIEZOMOTOR-CONTROLLER-VOLTAGE-ERROR', initial_value = False)
cs_cmd_error = builder.boolIn('PIEZOMOTOR-CONTROLLER-COMMAND-ERROR', initial_value = False)
cs_reset = builder.boolIn('PIEZOMOTOR-CONTROLLER-RESET', initial_value = False) # Power on / reset has occurred
cs_x_limit = builder.boolIn('PIEZOMOTOR-CONTROLLER-X-LIMIT', initial_value = False) # If the last motor moevement was stopped by external limit switch
cs_script = builder.boolIn('PIEZOMOTOR-CONTROLLER-SCRIPT-IS-RUNNING', initial_value = False)
cs_index = builder.boolIn('PIEZOMOTOR-CONTROLLER-INDEX-DETECTED', initial_value = False)
cs_servo_mode = builder.boolIn('PIEZOMOTOR-CONTROLLER-IS-SERVO-MODE', initial_value = False)
cs_target_limit = builder.boolIn('PIEZOMOTOR-CONTROLLER-TARGET-LIMIT', initial_value = False) # If the position limit is reached
cs_target_mode = builder.boolIn('PIEZOMOTOR-CONTROLLER-TARGET-MODE', initial_value = False)
cs_target_reached = builder.boolIn('PIEZOMOTOR-CONTROLLER-TARGET-REACHED', initial_value = False)
cs_parked = builder.boolIn('PIEZOMOTOR-CONTROLLER-PARKED', initial_value = False) # If the motor is powered down
cs_overheat = builder.boolIn('PIEZOMOTOR-CONTROLLER-OVERHEAT', initial_value = False) # Controller board output stage is overheated
cs_reverse = builder.boolIn('PIEZOMOTOR-CONTROLLER-REVERSE', initial_value = False) # If the last movement was in reverse
cs_running = builder.boolIn('PIEZOMOTOR-CONTROLLER-RUNNING', initial_value = False)
motor_is_moving = builder.boolIn('IS-MOVING', initial_value = False)

## Frequently updated records
controller_response = builder.stringIn('CONTROLLER-RESPONSE', initial_value = "")
target_position = builder.aIn('TARGET-POSITION', initial_value = 250)
main_encoder_reading = builder.aIn('MAIN-ENCODER-READING', initial_value = -1)
secondary_encoder_reading = builder.aIn('SECONDARY-ENCODER-READING', initial_value = -1)
piano_encoder_reading = builder.aIn('PIANO-ENCODER-READING', initial_value = -1)
linear_potentiometer_reading = builder.aIn('LINEAR-POTENTIOMETER-READING', initial_value = -1)
motor_speed = builder.aIn('MOTOR-SPEED', initial_value = 500)
motor_slow_speed = builder.aIn('MOTOR-SLOW-SPEED', initial_value = 50)
motor_gain = builder.aIn('MOTOR-GAIN', initial_value = 1.54)

## Connection records
piezomotor_connection = builder.boolIn('PIEZOMOTOR-CONNECTION', initial_value = False)
ioc_heartbeat = builder.boolIn('PIEZOMOTOR-IOC-HEARTBEAT', initial_value = False)
controller_port = builder.stringIn('CONTROLLER-SERIAL-PORT', initial_value = "/dev/ttyUSB0")
baud_rate = builder.aIn('CONTROLLER-BAUD-RATE', initial_value = 115200)

## Limits and configuration
forward_limit_switch_position = builder.aIn('FORWARD-LIMIT-SWITCH-POSITION', initial_value = 0)
backward_limit_switch_position = builder.aIn('BACKWARD-LIMIT-SWITCH-POSITION', initial_value = 0)
forward_software_limit = builder.aIn('FORWARD-SOFTWARE-LIMIT', initial_value = 0)
backward_software_limit = builder.aIn('BACKWARD-SOFTWARE-LIMIT', initial_value = 0)
overstep = 300

## Positions for each target being centered on beamline.
target_positions = [builder.aIn('TARGET-POSITION0', initial_value = 1000),
                    builder.aIn('TARGET-POSITION1', initial_value = 1800),
                    builder.aIn('TARGET-POSITION2', initial_value = 2600),
                    builder.aIn('TARGET-POSITION3', initial_value = 3400),
                    builder.aIn('TARGET-POSITION4', initial_value = 4200),
                    builder.aIn('TARGET-POSITION5', initial_value = 5000),
                    builder.aIn('TARGET-POSITION6', initial_value = 5800)
                   ]

go_tos = [builder.boolOut('GO-TO-TARGET-POSITION0', initial_value = False, on_update = lambda v: go_to(0, v)),
          builder.boolOut('GO-TO-TARGET-POSITION1', initial_value = False, on_update = lambda v: go_to(1, v)),
          builder.boolOut('GO-TO-TARGET-POSITION2', initial_value = False, on_update = lambda v: go_to(2, v)),
          builder.boolOut('GO-TO-TARGET-POSITION3', initial_value = False, on_update = lambda v: go_to(3, v)),
          builder.boolOut('GO-TO-TARGET-POSITION4', initial_value = False, on_update = lambda v: go_to(4, v)),
          builder.boolOut('GO-TO-TARGET-POSITION5', initial_value = False, on_update = lambda v: go_to(5, v)),
          builder.boolOut('GO-TO-TARGET-POSITION6', initial_value = False, on_update = lambda v: go_to(6, v))
         ]

# Boilerplate get the IOC started
dispatcher = asyncio_dispatcher.AsyncioDispatcher() # Create an asyncio dispatcher, the event loop is now running
builder.LoadDatabase()
softioc.iocInit(dispatcher)

# Initialize the I2C interface
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain=2  #ganancia (6v-gain=2/3,4v-gain=1, 2v-gain=2, 1v-gain=4)
#channel = AnalogIn(ads,ADS.P0) #Modo Single
channel = AnalogIn(ads, ADS.P0,ADS.P1) #Modo diferencial

async def stop(should_stop):
    if not should_stop:
        return
    connection.write(("X1S\r").encode("ascii"))
    _ = connection.read_until(b"\r").decode().strip().split(":")[1]
    user_stop.set(False)
    
async def go_to(position_index, should_go = False):
    if not should_go:
        return
    user_stop.set(False)
    for i in range(len(go_tos)):
        if i != position_index:
            go_toS[i].set(False)
    user_target_position.set(target_positions[position_index])

async def send_command(value = ""):
    if value[:2] == "X1":
        value = value.strip() + "\r"
        
    elif value[0] == "X":
        value = "X1" + value[1:].strip() + "\r"
    else:
        value = "X1" + value.strip() + "\r"
    if value[2] == "T" or value[2] == "R" or value[2] == "C":
        pass # Check motor temperature
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(value.encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
            controller_response.set(reading)
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False)

async def set_target_position(value=-float("inf")):
    if value == -float("inf"):
        print("Not enough parameters for target position setting")
        return
    user_stop.set(False)
    try:
        piezomotor_connection.set(True)
        motor_is_moving.set(True)
        while abs(channel.value - (value + overstep)) > 5 and not user_stop.get():
            calculated_steps = ((value + overstep) - channel.value) * motor_gain.get()
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1J" + str(int(calculated_steps)) + ",0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip()
            await asyncio.sleep(0.001)
        
        mean = channel.value
        while abs(mean - value) > 1 and not user_stop.get():
            calculated_steps = int(((value - mean) / 2.0) * motor_gain.get())
            if(calculated_steps > 0):
                print("breaking at:", channel.value)
                break
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1J" + str(int(calculated_steps)) + ",0," + str(int(motor_slow_speed.get())) + "\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip()
            is_moving = True
            while is_moving:
                with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                    connection.write(("X1U\r").encode("ascii"))
                    is_moving = int(re.match(".*\d\d\d(\d)", connection.read_until(b"\r").decode().strip().split(":")[1]).groups()[0]) % 2 == 1
                await asyncio.sleep(0.01)
            mean = 0
            for i in range(1000):
                mean += channel.value
            mean /= 1000
        motor_is_moving.set(False)
        
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False)

# Update global settings parameters
async def slow_update():
    while True:
        try:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1?\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip().split(":")[1]
                controller_model.set(reading)
            piezomotor_connection.set(True)
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False)
        await asyncio.sleep(60)

async def update():
    while True:
        ioc_heartbeat.set(not ioc_heartbeat.get())
        try:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                main_encoder_reading.set(channel.value)
                connection.write(("X1T\r").encode("ascii"))
                reading = int(connection.read_until(b"\r").decode().strip().split(":")[1])
                target_position.set(reading)
                connection.write(("X1H\r").encode("ascii"))
                reading = int(connection.read_until(b"\r").decode().strip().split(":")[1])
                connection.write(("X1U0\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip().split(":")[1]
                cs_com_error.set(int(reading[0]) // 8 == 1)
                cs_enc_error.set(int(reading[0]) // 4 == 1)
                cs_voltage_error.set(int(reading[0]) // 2 == 1)
                cs_cmd_error.set(int(reading[0]) // 1 == 1)
                cs_reset.set(int(reading[1]) // 8 == 1)
                cs_x_limit.set(int(reading[1]) // 4 == 1)
                cs_script.set(int(reading[1]) // 2 == 1)
                cs_index.set(int(reading[1]) // 1 == 1)
                cs_servo_mode.set(int(reading[2]) // 8 == 1)
                cs_target_limit.set(int(reading[2]) // 4 == 1)
                cs_target_mode.set(int(reading[2]) // 2 == 1)
                cs_target_reached.set(int(reading[2]) // 1 == 1)
                cs_parked.set(int(reading[3]) // 8 == 1)
                cs_reverse.set(int(reading[3]) // 4 == 1)
                cs_overheat.set(int(reading[3]) // 2 == 1)
                cs_running.set(int(reading[3]) // 1 == 1)

            piezomotor_connection.set(True)
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False)
        await asyncio.sleep(0.1)

dispatcher(update)
dispatcher(slow_update)

# Finally leave the IOC running with an interactive shell.
if debug:
    softioc.interactive_ioc(globals())
else:
    cothread.WaitForQuit()
