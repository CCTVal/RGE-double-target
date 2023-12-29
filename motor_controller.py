#adc
import board
import time
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from ADS1219_lib import ADS1219


import RPi.GPIO as gpio

import cothread
from softioc import softioc, builder, asyncio_dispatcher
import asyncio
import serial
import re

#General settings
# Set the record prefix
builder.SetDeviceName("CCTVAL_DT_PMD301")
motor_temperature_range = {"LOLO": 253, "LOW": 263, "HIGH": 350, "HIHI": 360}
debug = True
PIANO_PIN = 23
LIMIT1_PIN = 24

# Create some records
## User input records
user_target_position = builder.aOut('USER-TARGET-POSITION', initial_value = 20, always_update = True,
                          on_update = lambda v: set_target_position(v)) #dual_go_to(v)
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
motor_speed = builder.aOut('MOTOR-SPEED', initial_value = 500, on_update = lambda v: set_speed(v))
motor_slow_speed = builder.aIn('MOTOR-SLOW-SPEED', initial_value = 500)
motor_gain = builder.aIn('MOTOR-GAIN', initial_value = 0.00333)
noise_supression = builder.aIn('NOISE-SUPRESSION', initial_value = 50)
main_encoder = builder.stringOut('MAIN-ENCODER', initial_value = "analog")

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
overstep = 30000

## Positions for each target being centered on beamline.
target_positions = [builder.aOut('TARGET-POSITION0', initial_value = 5000),
                    builder.aOut('TARGET-POSITION1', initial_value = 6961),
                    builder.aOut('TARGET-POSITION2', initial_value = 587000),
                    builder.aOut('TARGET-POSITION3', initial_value = 1260500),
                    builder.aOut('TARGET-POSITION4', initial_value = 1932500),
                    builder.aOut('TARGET-POSITION5', initial_value = 2600300),
                    builder.aOut('TARGET-POSITION6', initial_value = 3000000)
                   ]

target_piano_positions = [builder.aOut('TARGET-PIANO-POSITION0', initial_value = 52.2),
                    builder.aOut('TARGET-PIANO-POSITION1', initial_value = 45.5),
                    builder.aOut('TARGET-PIANO-POSITION2', initial_value = 34.87),
                    builder.aOut('TARGET-PIANO-POSITION3', initial_value = 25.18),
                    builder.aOut('TARGET-PIANO-POSITION4', initial_value = 15.282),
                    builder.aOut('TARGET-PIANO-POSITION5', initial_value = 5.68),
                    builder.aOut('TARGET-PIANO-POSITION6', initial_value = 1.5)
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
#i2c = busio.I2C(board.SCL, board.SDA)
#ads = ADS.ADS1115(i2c)
#ads.gain=2  #ganancia (6v-gain=2/3,4v-gain=1, 2v-gain=2, 1v-gain=4)
#channel = AnalogIn(ads,ADS.P0) #Modo Single
#channel = AnalogIn(ads, ADS.P0,ADS.P1) #Modo diferencial
ads = ADS1219(1,0x40,4)
ads.setExternalReference(0)


gpio.setmode(gpio.BCM)
gpio.setup(23, gpio.IN)
gpio.setup(24, gpio.IN)

async def stop(should_stop = True):
    if not should_stop:
        return
    with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
        connection.write(("X1S\r").encode("ascii"))
        _ = connection.read_until(b"\r")
    user_stop.set(False)
    
async def set_speed(speed):
    if motor_slow_speed.get() > speed:
        motor_slow_speed.set(speed)

async def go_to(position_index, should_go = False):
    if not should_go:
        return
    user_stop.set(False)
    for i in range(len(go_tos)):
        if i != position_index:
            go_tos[i].set(False)
    if main_encoder.get() == "piano":
        await piano_go_to(position_index)
    else: # analog
        user_target_position.set(target_positions[position_index].get())
    go_tos[position_index].set(False)

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
        while abs(ads.readDifferential_0_1() - (value + overstep)) > 500 and not user_stop.get():
            calculated_steps = ((value + overstep) - ads.readDifferential_0_1()) * motor_gain.get()
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1J" + str(int(calculated_steps)) + ",0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip()
            await asyncio.sleep(0.001)
        
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        mean = ads.readDifferential_0_1()
        while (mean - value) > 1 and not user_stop.get():
            calculated_steps = ((value - mean)) * motor_gain.get()
            print("current position:",mean,"calculated raw steps:", calculated_steps)
            calculated_microsteps = int((calculated_steps - int(calculated_steps)) * 8192)
            calculated_steps = int(calculated_steps)
            print("calculated steps:", calculated_steps, "microsteps:", calculated_microsteps)
            if(calculated_steps > 0):
                break
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1J" + str(int(calculated_steps)) + "," + str(calculated_microsteps) + "," + str(int(motor_slow_speed.get())) + "\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip()
            is_moving = True
            while is_moving:
                with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                    connection.write(("X1U\r").encode("ascii"))
                    is_moving = int(re.match(".*\d\d\d(\d)", connection.read_until(b"\r").decode().strip().split(":")[1]).groups()[0]) % 2 == 1
                await asyncio.sleep(0.01)
            mean = 0
            for i in range(int(noise_supression.get())):
                mean += ads.readDifferential_0_1()
            mean /= noise_supression.get()
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        print("[Set target position]:: breaking at mean read value:", mean)
        motor_is_moving.set(False)
        
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False)

async def measure():
    mean = 0
    for i in range(300):
        mean += ads.readDifferential_0_1()
    mean /= 300.0
    print(mean)

async def measure_piano(step= -1):
    suma = 0
    last_piano = gpio.input(PIANO_PIN)
    print("last piano,", last_piano)
    while True:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1J-10,0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        await asyncio.sleep(0.1)
        suma += 1
        for i in range(10):
            if gpio.input(PIANO_PIN) == last_piano:
                break
        else:
            break
    print("suma, ", suma)
    print("piano input", gpio.input(PIANO_PIN))


async def piano_go_to(position_index = -float("inf")):
    if position_index == -float("inf"):
        print("Not enough parameters for target position setting")
        return
    user_stop.set(False)
    motor_is_moving.set(True)
    while not cs_x_limit.get():
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1J100,0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
        connection.write(("X1S\r").encode("ascii"))
        reading = connection.read_until(b"\r").decode().strip()

    print("\nStarting piano movement. We will move ", target_piano_positions[position_index].get(), "piano steps.")
    suma = gpio.input(PIANO_PIN)
    print("The current piano reading is:", suma, "\nThe step lengths are:", end = " ")
    for present in range(int(target_piano_positions[position_index].get())):
        last_piano = suma
        j = 0
        while suma == last_piano:
            j += 1
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1J-10,0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip()
            await asyncio.sleep(0.1)
            suma = 0
            for i in range(10):
                suma += gpio.input(PIANO_PIN)
            suma /= 10.0
            suma = round(suma)
        print(str(j), end = ",")
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        await asyncio.sleep(0.1)
        piano_encoder_reading.set(piano_encoder_reading.get() + 1)
    remaining_steps = target_piano_positions[position_index].get() - int(target_piano_positions[position_index].get()) * (-256) # That's the amount of motor steps that correspond to one piano encoder step. Must be callibrated as best as possible.
    with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
        connection.write(("X1J" + str(remaining_steps) + ",0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
        reading = connection.read_until(b"\r").decode().strip()
        await asyncio.sleep(0.1)

    motor_is_moving.set(False)

async def dual_go_to(position_index = -float("inf")):
    if position_index == -float("inf"):
        print("Not enough parameters for target position setting")
        return
    user_stop.set(False)
    piezomotor_connection.set(True)
    motor_is_moving.set(True)
    while not cs_x_limit.get():
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1J100,0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
        connection.write(("X1S\r").encode("ascii"))
        reading = connection.read_until(b"\r").decode().strip()

    print("\nStarting piano movement. We will move ", target_piano_positions[position_index].get(), "piano steps.")
    suma = gpio.input(PIANO_PIN)
    last_piano = suma
    piano_position = 0
    piano_encoder_reading.set(0)
    print("The current piano reading is:", suma, "\nThe step lengths are:", end = " ")
    while ads.readDifferential_0_1() - (value + overstep) > 500 and not user_stop.get():
        calculated_steps = ((value + overstep) - ads.readDifferential_0_1()) * motor_gain.get()
        steps = max([-100, calculated_steps])
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1J" + str(int(steps)) + ",0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        suma = 0
        for i in range(10):
            suma += gpio.input(PIANO_PIN)
        suma = round(suma/10.0, -1)
        if suma != last_piano:
            last_piano = suma
            piano_position += 1
            piano_encoder_reading.set(piano_encoder_reading.get() + 1)
    with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
        connection.write(("X1S\r").encode("ascii"))
        reading = connection.read_until(b"\r").decode().strip()

    while (mean - value) > 1 and not user_stop.get():
        calculated_steps = ((value - mean)) * motor_gain.get()
        print("current position:",mean,"calculated raw steps:", calculated_steps)
        calculated_microsteps = int((calculated_steps - int(calculated_steps)) * 8192)
        calculated_steps = int(calculated_steps)
        print("calculated steps:", calculated_steps, "microsteps:", calculated_microsteps)
        if(calculated_steps > 0):
            break
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1J" + str(int(calculated_steps)) + "," + str(calculated_microsteps) + "," + str(int(motor_slow_speed.get())) + "\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        is_moving = True
        while is_moving:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1U\r").encode("ascii"))
                is_moving = int(re.match(".*\d\d\d(\d)", connection.read_until(b"\r").decode().strip().split(":")[1]).groups()[0]) % 2 == 1
            await asyncio.sleep(0.01)
        mean = 0
        for i in range(int(noise_supression.get())):
            mean += ads.readDifferential_0_1()
        mean /= noise_supression.get()
    with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
        connection.write(("X1S\r").encode("ascii"))
        reading = connection.read_until(b"\r").decode().strip()
    print("[Set target position]:: breaking at mean read value:", mean)
    motor_is_moving.set(False)


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
                adc_reading = ads.readDifferential_0_1()
                main_encoder_reading.set(adc_reading)
                connection.write(("X1T\r").encode("ascii"))
                reading = int(connection.read_until(b"\r").decode().strip().split(":")[1])
                target_position.set(reading)
                connection.write(("X1H\r").encode("ascii"))
                reading = int(connection.read_until(b"\r").decode().strip().split(":")[1])
                connection.write(("X1U0\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip().split(":")[1]
                cs_com_error.set(int(reading[0], 16) // 8 == 1)
                cs_enc_error.set(int(reading[0], 16) // 4 == 1)
                cs_voltage_error.set(int(reading[0], 16) // 2 == 1)
                cs_cmd_error.set(int(reading[0], 16) // 1 == 1)
                cs_reset.set(int(reading[1], 16) // 8 == 1)
                limit_reached = int(reading[1], 16) // 4 == 1
                cs_x_limit.set(limit_reached)
                if limit_reached:
                    print("limit reached!")
                    dispatcher(stop)
                    if adc_reading > target_positions[3].get():
                        print("it's the forward limit!")
                        forward_limit_switch_position.set(adc_reading)
                    else:
                        print("it's the backward limit!")
                        backward_limit_switch_position.set(adc_reading)
                cs_script.set(int(reading[1], 16) // 2 == 1)
                cs_index.set(int(reading[1], 16) // 1 == 1)
                cs_servo_mode.set(int(reading[2], 16) // 8 == 1)
                cs_target_limit.set(int(reading[2], 16) // 4 == 1)
                cs_target_mode.set(int(reading[2], 16) // 2 == 1)
                cs_target_reached.set(int(reading[2], 16) // 1 == 1)
                cs_parked.set(int(reading[3], 16) // 8 == 1)
                cs_overheat.set(int(reading[3], 16) // 4 == 1)
                cs_reverse.set(int(reading[3], 16) // 2 == 1)
                cs_running.set(int(reading[3], 16) // 1 == 1)

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
