import subprocess
if subprocess.check_output(["ps", "-e"]).decode("utf-8").count("python") > 1:
    raise Exception("There's probably another instance of this program already running")

#adc
import board
import time
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from ADS1219_lib import ADS1219


import RPi.GPIO as gpio

import cothread
from softioc import softioc, builder, asyncio_dispatcher, alarm
import asyncio
import serial
import re

#General settings
# Set the record prefix
builder.SetDeviceName("CCTVAL_DT_PMD301")
debug = False
PIANO_PIN = 23
LIMIT1_PIN = 24
LIMIT2_PIN = 25

# Create some records
## User input records
user_target_position = builder.aOut('USER-TARGET-POSITION', initial_value = 20, always_update = True,
                          on_update = lambda v: set_target_position(v))
user_stop = builder.boolOut('SHOULD-STOP', initial_value = False, always_update = True,
                          on_update = lambda v: stop(v))
user_command = builder.stringOut('USER-MOTOR-COMMAND', initial_value = "", always_update = True,
                          on_update = lambda v: send_command(v))
step_forward_command = builder.boolOut('STEP-FORWARD', initial_value = False, on_update = lambda v: move_to(500) if v else 0)
step_backward_command = builder.boolOut('STEP-BACKWARD', initial_value = False, on_update = lambda v: move_to(-500) if v else 0)
small_step_forward_command = builder.boolOut('SMALL-STEP-FORWARD', initial_value = False, on_update = lambda v: move_to(50) if v else 0)
small_step_backward_command = builder.boolOut('SMALL-STEP-BACKWARD', initial_value = False, on_update = lambda v: move_to(-50) if v else 0)

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
controller_response = builder.stringIn('CONTROLLER-RESPONSE', initial_value = "")

## Frequently updated records
centered = builder.mbbIn('CENTERED',
    'Wire',
    'C',
    'Al',
    'Cu',
    'Sn',
    'Pb',
    'Empty',
    ('Unknown', alarm.MAJOR_ALARM),
    initial_value = 7)
main_encoder_reading = builder.aIn('MAIN-ENCODER-READING', initial_value = -1)
piano_encoder_reading = builder.aIn('PIANO-ENCODER-READING', initial_value = -1)
piano_reading_pv = builder.boolIn('PIANO-READING', initial_value = False)
motor_steps_given = builder.aIn('MOTOR-STEPS-GIVEN', initial_value = -1)

## Connection records
piezomotor_connection = builder.boolIn('PIEZOMOTOR-CONNECTION', initial_value = False)
ioc_heartbeat = builder.boolIn('PIEZOMOTOR-IOC-HEARTBEAT', initial_value = False)
controller_port = builder.stringIn('CONTROLLER-SERIAL-PORT', initial_value = "/dev/ttyUSB0")
baud_rate = builder.aIn('CONTROLLER-BAUD-RATE', initial_value = 115200)

## Limits and configuration
forward_limit_switch_position = builder.aIn('FORWARD-LIMIT-SWITCH-POSITION', initial_value = -1)
forward_limit_switch = builder.boolIn('FORWARD-LIMIT-SWITCH', initial_value = False)
backward_limit_switch_position = builder.aIn('BACKWARD-LIMIT-SWITCH-POSITION', initial_value = -1)
backward_limit_switch = builder.boolIn('BACKWARD-LIMIT-SWITCH', initial_value = False)
#forward_software_limit = builder.aIn('FORWARD-SOFTWARE-LIMIT', initial_value = 5000000)
#forward_software_limit_is_reached = builder.boolIn('AT-FORWARD-SOFTWARE-LIMIT', initial_value = False)
#backward_software_limit = builder.aIn('BACKWARD-SOFTWARE-LIMIT', initial_value = -50000)
#backward_software_limit_is_reached = builder.boolIn('AT-BACKWARD-SOFTWARE-LIMIT', initial_value = False)
main_encoder = builder.stringOut('MAIN-ENCODER', initial_value = "analog")
motor_gain = builder.aOut('MOTOR-GAIN', initial_value = 0.00333)
noise_supression = builder.aOut('NOISE-SUPRESSION', initial_value = 25)
overstep = builder.aOut('OVERSTEP', initial_value = 30000)
motor_speed = builder.aOut('MOTOR-SPEED', initial_value = 500)

## Calibration
reference_forward_limit_switch = builder.aIn('REFERENCE-FORWARD-LIMIT-SWITCH', initial_value = 3770414)
reference_backward_limit_switch = builder.aIn('REFERENCE-BACKWARD-LIMIT-SWITCH', initial_value = 6848)
reference_piano_limit_switch = builder.aIn('REFERENCE-PIANO-LIMIT-SWITCH', initial_value = 70)
reference_motor_limit_switch = builder.aIn('REFERENCE-MOTOR-LIMIT-SWITCH', initial_value = -29660)
calibrate_analog_pv = builder.boolOut('CALIBRATE-ANALOG', initial_value = False, on_update = lambda v: calibrate_analog(v))
calibrate_piano_pv = builder.boolOut('CALIBRATE-PIANO', initial_value = False, on_update = lambda v: calibrate_piano(v))
calibrate_motor_pv = builder.boolOut('CALIBRATE-MOTOR', initial_value = False, on_update = lambda v: calibrate_motor(v))
calibrate_all_pv = builder.boolOut('CALIBRATE-ALL', initial_value = False, on_update = lambda v: calibrate_all(v))
auto_calibration_pv = builder.boolOut('AUTO-CALIBRATION', initial_value = False, on_update = lambda v: print("auto_calibration changed!"))
search_motor_pos_pv = builder.boolOut('SEARCH-MOTOR-POSITIONS', initial_value = False, on_update = lambda v: search_motor_positions(v))
search_piano_pos_pv = builder.boolOut('SEARCH-PIANO-POSITIONS', initial_value = False, on_update = lambda v: search_piano_positions(v))

## Positions for each target being centered on beamline.
target_positions = [builder.aOut('TARGET-POSITION0', initial_value = -300000),
                    builder.aOut('TARGET-POSITION1', initial_value = 393120),
                    builder.aOut('TARGET-POSITION2', initial_value = 1068295),
                    builder.aOut('TARGET-POSITION3', initial_value = 1735760),
                    builder.aOut('TARGET-POSITION4', initial_value = 2424250),
                    builder.aOut('TARGET-POSITION5', initial_value = 3122115),
                    builder.aOut('TARGET-POSITION6', initial_value = 3879610)
                   ]

target_piano_positions = [builder.aOut('TARGET-PIANO-POSITION0', initial_value = 60.0),
                    builder.aOut('TARGET-PIANO-POSITION1', initial_value = 48.7),
                    builder.aOut('TARGET-PIANO-POSITION2', initial_value = 38.9),
                    builder.aOut('TARGET-PIANO-POSITION3', initial_value = 29.1),
                    builder.aOut('TARGET-PIANO-POSITION4', initial_value = 19.4),
                    builder.aOut('TARGET-PIANO-POSITION5', initial_value = 9.4),
                    builder.aOut('TARGET-PIANO-POSITION6', initial_value = 0.0)
                   ]

target_motor_positions = [builder.aOut('TARGET-MOTOR-POSITION0', initial_value = -35000),
                    builder.aOut('TARGET-MOTOR-POSITION1', initial_value = -22894),
                    builder.aOut('TARGET-MOTOR-POSITION2', initial_value = -18176),
                    builder.aOut('TARGET-MOTOR-POSITION3', initial_value = -13678),
                    builder.aOut('TARGET-MOTOR-POSITION4', initial_value = -7100),
                    builder.aOut('TARGET-MOTOR-POSITION5', initial_value = -3188),
                    builder.aOut('TARGET-MOTOR-POSITION6', initial_value = 0)
                   ]

analog_offset = builder.aOut('ANALOG-OFFSET', initial_value = 0, on_update = lambda v: apply_offset(v, target_positions))
piano_offset = builder.aOut('PIANO-OFFSET', initial_value = 0, on_update = lambda v: apply_offset(v, target_piano_positions))
motor_offset = builder.aOut('MOTOR-OFFSET', initial_value = 0, on_update = lambda v: apply_offset(v, target_motor_positions))

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
gpio.setup(PIANO_PIN, gpio.IN)
gpio.setup(LIMIT1_PIN, gpio.IN)
gpio.setup(LIMIT2_PIN, gpio.IN)

# Sending a movement command to the motor controler
def move_to(value):
    calculated_microsteps = int((value - int(value)) * 8192)
    calculated_steps = int(value)
    expected_final_position = main_encoder_reading.get() #+ (value / motor_gain.get())
    '''
    if expected_final_position > forward_software_limit.get() and value > 0:
        print("Reached forward software limit!")
        motor_is_moving.set(False)
        cs_target_limit.set(True, severity = alarm.MAJOR_ALARM, alarm = alarm.HIHI_ALARM)
        forward_software_limit_is_reached.set(True)
        return False
    if expected_final_position < backward_software_limit.get() and value < 0:
        print("Reached forward software limit!")
        motor_is_moving.set(False)
        cs_target_limit.set(True, severity = alarm.MAJOR_ALARM, alarm = alarm.HIHI_ALARM)
        backward_software_limit_is_reached.set(True)
        return False
    '''
    if value < 0:
        forward_limit_switch.set(False)
    else:
        backward_limit_switch.set(False)
    cs_target_limit.set(False, severity = alarm.NO_ALARM, alarm = alarm.READ_ALARM)
    #backward_software_limit_is_reached.set(False, severity = alarm.NO_ALARM)
    #forward_software_limit_is_reached.set(False, severity = alarm.NO_ALARM)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1J" + str(int(calculated_steps)) + "," + str(int(calculated_microsteps)) + "," + str(int(motor_speed.get())) + "\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        piezomotor_connection.set(True, severity = alarm.NO_ALARM)
        motor_steps_given.set(motor_steps_given.get() + value)
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
    step_forward_command.set(False)
    step_backward_command.set(False)
    small_step_forward_command.set(False)
    small_step_backward_command.set(False)
    return True

async def stop(should_stop = True):
    if not should_stop:
        return
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            _ = connection.read_until(b"\r")
        piezomotor_connection.set(True, severity = alarm.NO_ALARM)
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
    await asyncio.sleep(2)
    user_stop.set(False)

# returns only when movement has ended (must be awaited).
async def sync_move(steps = 0):
    if not move_to(steps):
        return False;
    is_moving = True
    #print("sync move, moving", steps)
    while is_moving:
        try:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1U\r").encode("ascii"))
                is_moving = int(re.match(".*\d\d\d(\d)", connection.read_until(b"\r").decode().strip().split(":")[1]).groups()[0]) % 2 == 1
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
            return False;
        await asyncio.sleep(0.001)
    return True;

# Common movement logic, encoder independent
async def go_to(position_index, should_go = False):
    if not should_go:
        return
    user_stop.set(True)
    await stop() # Comment for high-frequency testing purposes
    user_stop.set(False)
    centered.set(7, severity = alarm.MAJOR_ALARM, alarm = alarm.STATE_ALARM)
    for i in range(len(go_tos)):
        if i != position_index:
            go_tos[i].set(False)
    if main_encoder.get() == "piano":
        await piano_go_to(position_index)
    elif main_encoder.get() == "motor":
        await motor_go_to(position_index)
    elif main_encoder.get() == "analog":
        await set_target_position(target_positions[position_index].get())
    else: # dual
        await dual_go_to(position_index)
        #user_target_position.set(target_positions[position_index].get())
    centered.set(position_index, severity = alarm.NO_ALARM)
    go_tos[position_index].set(False)

# Send an arbitrary command to the motor controller and get a response.
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
        piezomotor_connection.set(True, severity = alarm.NO_ALARM)
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)

# Move the motor to a specified position using only the analog linear encoder
async def set_target_position(value=-float("inf")):
    if value == -float("inf"):
        print("Not enough parameters for target position setting")
        return
    user_stop.set(False)
    if auto_calibration_pv.get():
        await calibrate_analog()
    try:
        motor_is_moving.set(True)
        while abs(ads.readDifferential_0_1() - (value + overstep.get())) > 500 and not user_stop.get():
            calculated_steps = ((value + overstep.get()) - ads.readDifferential_0_1()) * motor_gain.get()
            if not move_to(calculated_steps):
                return
            if forward_limit_switch.get() or backward_limit_switch.get():
                break
            await asyncio.sleep(0.001)
        
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        mean = ads.readDifferential_0_1()
        while (mean - value) > 1 and not user_stop.get() and not backward_limit_switch.get(): 
            calculated_steps = ((value - mean)) * motor_gain.get()
            if(calculated_steps > 0):
                break
            if not move_to(calculated_steps):
                return
            is_moving = True
            while is_moving:
                with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                    connection.write(("X1U\r").encode("ascii"))
                    is_moving = int(re.match(".*\d\d\d(\d)", connection.read_until(b"\r").decode().strip().split(":")[1]).groups()[0]) % 2 == 1
                await asyncio.sleep(0.01)
            mean = 0
            noisy = noise_supression.get()
            for i in range(int(noisy)):
                mean += ads.readDifferential_0_1()
            mean /= noisy
            main_encoder_reading.set(mean)
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        # print("[Set target position]:: breaking at mean read value:", mean)
        motor_is_moving.set(False)
        
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)


# Move the motor using only the piano encoder as reference.
async def piano_go_to(position_index = -float("inf")):
    if position_index == -float("inf"):
        print("Not enough parameters for target position setting")
        return
    user_stop.set(False)
    motor_is_moving.set(True)
    while not (forward_limit_switch.get() or user_stop.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    motor_steps_given.set(0)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)

    print("\nStarting piano movement. We will move ", target_piano_positions[position_index].get(), "piano steps.")
    suma = gpio.input(PIANO_PIN)
    for present in range(int(target_piano_positions[position_index].get())):
        if user_stop.get() or backward_limit_switch.get():
            return
        last_piano = suma
        j = 0
        while suma == last_piano and (not user_stop.get()) and (not backward_limit_switch.get()):
            j += 1
            if not await sync_move(-10):
                return
            suma = 0
            for i in range(10):
                suma += gpio.input(PIANO_PIN)
            suma /= 10.0
            suma = round(suma)
        print(str(j), end = ",")
        if j < 18 and present != 0:
            print("\nERROR: Piano encoder error!\nLooks like there's been some mis-reading. We'll repeat the movement from the beggining.\n")
            await piano_go_to(position_index)
            return
        try:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1S\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip()
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
        await asyncio.sleep(0.1)
        piano_encoder_reading.set(piano_encoder_reading.get() + 1)
    remaining_steps = (target_piano_positions[position_index].get() - int(target_piano_positions[position_index].get())) * (-256) # That's the amount of motor steps that correspond to one piano encoder step. Must be callibrated as best as possible.
    print("remaining steps:" , remaining_steps)
    if not move_to(remaining_steps):
        return
    await asyncio.sleep(0.1)

    motor_is_moving.set(False)

# Move the motor to a specified position using only the motor steps count as reference, using a limit switch as physical reference.
async def motor_go_to(position_index):
    user_stop.set(False)
    motor_is_moving.set(True)
    if auto_calibration_pv.get():
        await calibrate_motor()
    while not (cs_x_limit.get() or user_stop.get() or forward_limit_switch.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    await asyncio.sleep(1)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
    for step in range(0,int(target_motor_positions[position_index].get()),-1):
        if user_stop.get() or backward_limit_switch.get():
            return
        if not await sync_move(-1):
            print("There's been a fatal error! Call the programmer!")
    await asyncio.sleep(1)
    motor_is_moving.set(False)

# Move the motor to the specified position using the analog encoder as reference, but still counting piano steps so they can be cross-checked.
async def dual_go_to(position_index = -float("inf")):
    if position_index == -float("inf"):
        print("Not enough parameters for target position setting")
        return
    user_stop.set(False)
    motor_is_moving.set(True)
    if auto_calibration_pv.get():
        await calibrate_all()
    while not (cs_x_limit.get() or user_stop.get() or forward_limit_switch.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    motor_steps_given.set(0)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)

    print(position_index)
    print("\nStarting piano movement. We will move ", target_piano_positions[int(position_index)].get(), "piano steps.")
    suma = gpio.input(PIANO_PIN)
    last_piano = suma
    piano_position = 0
    piano_encoder_reading.set(0)
    value = target_positions[position_index].get()
    while ads.readDifferential_0_1() - (value + overstep.get()) > 500 and (not user_stop.get()) and (not backward_limit_switch.get()):
        calculated_steps = ((value + overstep.get()) - ads.readDifferential_0_1()) * motor_gain.get()
        steps = max([-100, calculated_steps])
        if not move_to(steps):
            return
        await asyncio.sleep(0)
        suma = 0
        for i in range(10):
            temp_piano = gpio.input(PIANO_PIN)
            suma += temp_piano # gpio.input(PIANO_PIN)
        if abs(suma - last_piano) > 5:
            last_piano = round(suma, -1)
            piano_position += 1
            piano_encoder_reading.set(piano_encoder_reading.get() + 1)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)

    mean = ads.readDifferential_0_1()
    while (mean - value) > 1 and (not user_stop.get()) and (not backward_limit_switch.get()):
        calculated_steps = ((value - mean)) * motor_gain.get()
        if(calculated_steps > 0):
            break
        if not await sync_move(calculated_steps):
            return
        mean = 0
        suma = 0
        noise_sup = noise_supression.get()
        for i in range(int(noise_sup)):
            mean += ads.readDifferential_0_1()
            suma += gpio.input(PIANO_PIN)
        mean /= noise_sup
        suma = round(suma/noise_sup)
        main_encoder_reading.set(mean)
        if suma != last_piano:
            last_piano = suma
            piano_position += 1
            piano_encoder_reading.set(piano_encoder_reading.get() + 1)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
    print("[Set target position]:: breaking at mean read value:", mean)

    piano_encoder_reading.set_alarm(severity = alarm.MINOR_ALARM if abs(piano_encoder_reading.get() - target_piano_positions[int(position_index)].get()) >= 2 else alarm.NO_ALARM, alarm = alarm.STATE_ALARM)
    motor_is_moving.set(False)

# Calibration functions

# Using linear potentiometer registered positions as reference, find the amount of piano steps needed in order to center each target.
async def search_piano_positions(should_search):
    if not should_search:
        return
    user_stop.set(False)
    motor_is_moving.set(True)
    while not (forward_limit_switch.get() or user_stop.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    motor_steps_given.set(0)
    await asyncio.sleep(1)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
    for i in range(-1, -(len(target_piano_positions)+1), -1):
        suma = gpio.input(PIANO_PIN)
        d = target_positions[i].get()
        encoder_reading = main_encoder_reading.get()
        print("distance:", d)
        while encoder_reading > d and not user_stop.get():
            last_piano = suma
            j = 0
            while suma == last_piano and not user_stop.get(): # One piano step
                j += 1
                if not await sync_move(-10):
                    return
                suma = 0
                for i in range(10):
                    suma += gpio.input(PIANO_PIN)
                suma /= 10.0
                suma = round(suma)
            print(str(j), end = ",")
            if j < 18 and present != 0:
                print("\nERROR: Piano encoder error!\nLooks like there's been some mis-reading. We'll repeat the movement from the beggining.\n")
                await search_piano_positions(True)
                return
            await asyncio.sleep(0.1)
            piano_encoder_reading.set(piano_encoder_reading.get() + 1)
            mean = 0
            noisy = noise_supression.get()
            for i in range(int(noisy)):
                mean += ads.readDifferential_0_1()
            mean /= noisy
            old_encoder_reading = encoder_reading
            encoder_reading = mean
        target_piano_positions[i].set(piano_encoder_reading.get() - 1 + (d - old_encoder_reading) / (encoder_reading - old_encoder_reading))
        print("Found "+str(i)+" position!")
    await asyncio.sleep(1)
    motor_is_moving.set(False)
    search_piano_pos_pv.set(False)

# Using linear potentiometer registered positions as reference, find the amount of motor steps needed in order to center each target.
async def search_motor_positions(should_search):
    if not should_search:
        return
    user_stop.set(False)
    motor_is_moving.set(True)
    while not (forward_limit_switch.get() or user_stop.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    motor_steps_given.set(0)
    await asyncio.sleep(1)
    try:
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1S\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
    for i in range(-1, -(len(target_motor_positions)+1), -1):
        print("i:", i)
        print(target_motor_positions)
        distance = target_positions[i]
        encoder_reading = main_encoder_reading.get()
        d = distance.get()
        print("distance:", d)
        while encoder_reading > (d + overstep.get()) and not user_stop.get():
            if not await sync_move(-1):
                print("There's been a fatal error! Call the programmer!")
                return
            if backward_limit_switch.get():
                print("Limit switch! Ending motor positions search!")
                return
            encoder_reading = ads.readDifferential_0_1()
        mean = ads.readDifferential_0_1()
        print("[search motor positions]::gets to overstep")
        while (mean - d) > 1 and not user_stop.get():
            if not await sync_move(-1):
                print("There's been a fatal error! Call the programmer!")
                return
            is_moving = True
            mean = 0
            noisy = noise_supression.get()
            for _ in range(int(noisy)):
                mean += ads.readDifferential_0_1()
            mean /= noisy
            main_encoder_reading.set(mean)
            if backward_limit_switch.get():
                print("Limit switch! Ending motor positions search!")
                return

        print("print")
        print(target_motor_positions)
        print(i)
        print(motor_steps_given.get())
        target_motor_positions[int(i)].set(motor_steps_given.get())
        print("Found "+str(i)+" position!")
    await asyncio.sleep(1)
    motor_is_moving.set(False)
    search_motor_pos_pv.set(False)


async def calibrate_analog(should_go = True):
    if not should_go:
        return
    await stop(True)
    motor_is_moving.set(True)
    while not (user_stop.get() or forward_limit_switch.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    motor_steps_given.set(0)
    found_forward_limit = 0
    mean = 0
    noisy = int(noise_supression.get())
    for _ in range(noisy):
        mean += ads.readDifferential_0_1()
    mean /= noisy
    found_forward_limit = mean
    print("[Calibrate_analog]::found forward limit:", found_forward_limit)
    if not await sync_move(-6000):
        return
    while not (user_stop.get() or backward_limit_switch.get()):
        if not await sync_move(-100):
            return
    found_backward_limit = 0
    mean = 0
    noisy = int(noise_supression.get())
    for _ in range(noisy):
        mean += ads.readDifferential_0_1()
    mean /= noisy
    found_backward_limit = mean
    print("[Calibrate_analog]::found backward limit:", found_backward_limit)
    
    alpha_0 = reference_backward_limit_switch.get()
    omega_0 = reference_forward_limit_switch.get()
    for i in range(len(target_positions)):
        target_positions[i].set( found_backward_limit + (found_forward_limit - found_backward_limit) * (target_positions[i].get() - alpha_0) / (omega_0 - alpha_0) )
    reference_backward_limit_switch.set(found_backward_limit)
    reference_forward_limit_switch.set(found_forward_limit)
    motor_is_moving.set(False)
    calibrate_analog_pv.set(False)
    return;

async def calibrate_piano(should_go = True):
    if not should_go:
        return
    await stop(True)
    motor_is_moving.set(True)
    while not (user_stop.get() or forward_limit_switch.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    piano_encoder_reading.set(0)
    motor_steps_given.set(0)
    
    suma = gpio.input(PIANO_PIN)
    while not (backward_limit_switch.get() or user_stop.get()):
        last_piano = suma
        j = 0
        while suma == last_piano and not user_stop.get():
            j += 1
            if not await sync_move(-10):
                return
            suma = 0
            for i in range(10):
                suma += gpio.input(PIANO_PIN)
            suma /= 10.0
            suma = round(suma)
        print(str(j), end = ",")
        if j < 18 and present != 0:
            print("\nERROR: Piano encoder error!\nLooks like there's been some mis-reading. We'll repeat the movement from the beggining.\n")
            await calibrate_piano()
            return
        try:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1S\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip()
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
        await asyncio.sleep(0.1)
        piano_encoder_reading.set(piano_encoder_reading.get() + 1)

    
    for i in range(len(target_piano_positions)):
        target_piano_positions[i].set( count * piano_encoder_reading.get() / reference_piano_limit_switch.get() )
    reference_piano_limit_switch.set(piano_encoder_reading.get())
    motor_is_moving.set(False)
    calibrate_piano_pv.set(False)
    return;
    
async def calibrate_motor(should_go = True, skip = -10_000):
    motor_is_moving.set(True)
    if not should_go:
        return
    await stop(True)
#    if skip == -10_000:
#        skip = target_motor_positions[0].get()
    print("[calibrate_motor]::will move")
    while not (user_stop.get() or forward_limit_switch.get()):
        if not move_to(100):
            return
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.5)
    piano_encoder_reading.set(0)
    motor_steps_given.set(0)

    count = 0
    print("[calibrate_motor]::will count steps")
    while not (user_stop.get() or backward_limit_switch.get()):
        steps = -1
        if not move_to(steps):
            return
        print("step", end = ", ")
        count += steps
        is_moving = True
        while is_moving:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1U\r").encode("ascii"))
                is_moving = int(re.match(".*\d\d\d(\d)", connection.read_until(b"\r").decode().strip().split(":")[1]).groups()[0]) % 2 == 1
            await asyncio.sleep(0.001)
    print("[calibrate_motor]::will correct registered positions")

    for i in range(len(target_motor_positions)):
        target_motor_positions[i].set( count * target_motor_positions[i].get() / reference_motor_limit_switch.get() )
    reference_motor_limit_switch.set(count)
    calibrate_motor_pv.set(False)
    motor_is_moving.set(False)
    await asyncio.sleep(2)
    print("\nmotor is moving = False")
    motor_is_moving.set(False)
    return;

async def calibrate_all(should_go = True):
    await calibrate_analog(should_go)
    return;

async def apply_offset(value, lista):
    for pv in lista:
        pv.set(pv.get() + value)
    analog_offset.set(0)
    piano_offset.set(0)
    motor_offset.set(0)
    return;

# Diagnostic funtions
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
    while not user_stop.get():
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

async def caracterize_potentiometer():
    while not user_stop.get():
        with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
            connection.write(("X1J-100,0," + str(int(motor_speed.get())) + "\r").encode("ascii"))
            reading = connection.read_until(b"\r").decode().strip()
        is_moving = True
        while is_moving:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1U\r").encode("ascii"))
                is_moving = int(re.match(".*\d\d\d(\d)", connection.read_until(b"\r").decode().strip().split(":")[1]).groups()[0]) % 2 == 1
            await asyncio.sleep(0.01)
        print(ads.readDifferential_0_1())
        if cs_x_limit.get():
            break


# Update global settings parameters
async def slow_update():
    while True:
        try:
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                connection.write(("X1?\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip().split(":")[1]
            controller_model.set(reading)
            piezomotor_connection.set(True, severity = alarm.NO_ALARM)
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
        await asyncio.sleep(60)

async def update():
    while True:
        ioc_heartbeat.set(not ioc_heartbeat.get())
        try:
            mean = 0
            # noise_sup = noise_supression.get()
            for i in range(8):
                mean += ads.readDifferential_0_1()
            mean /= 8
            adc_reading = mean
            main_encoder_reading.set(mean, severity = alarm.NO_ALARM)
            if centered.get() > 0 and centered.get() < 6:
                if(mean < target_positions[centered.get()].get() - 100_000 or mean > target_positions[centered.get()].get() + 100_000):
                    main_encoder_reading.set(mean, severity = alarm.MAJOR_ALARM, alarm = alarm.STATE_ALARM)
            with serial.Serial(controller_port.get(), baud_rate.get()) as connection:
                piano_reading_pv.set(gpio.input(PIANO_PIN))
                connection.write(("X1U0\r").encode("ascii"))
                reading = connection.read_until(b"\r").decode().strip().split(":")[1]
                communication_error = int(reading[0], 16) // 8
                cs_com_error.set(communication_error == 1, severity = communication_error, alarm = alarm.STATE_ALARM)
                cs_enc_error.set(int(reading[0], 16) // 4 == 1)
                voltage_error = int(reading[0], 16) // 2
                cs_voltage_error.set(voltage_error == 1, severity = voltage_error, alarm = alarm.STATE_ALARM)
                cmd_error = int(reading[0], 16) // 1
                cs_cmd_error.set(cmd_error == 1, severity = cmd_error, alarm = alarm.STATE_ALARM)
                cs_reset.set(int(reading[1], 16) // 8 == 1)
                limit_reached = int(reading[1], 16) // 4 == 1
                cs_x_limit.set(limit_reached)
                if limit_reached:
                    print("limit reached!")
                    if not gpio.input(LIMIT1_PIN):
                        print("it's the forward limit!")
                    if not gpio.input(LIMIT2_PIN):
                        print("it's the backward limit!")
                if not gpio.input(LIMIT1_PIN):
                    forward_limit_switch.set(True)
                    forward_limit_switch_position.set(adc_reading)
                else:
                    forward_limit_switch.set(False)
                if not gpio.input(LIMIT2_PIN):
                    backward_limit_switch.set(True)
                    backward_limit_switch_position.set(adc_reading)
                else:
                    backward_limit_switch.set(False)
                #cs_script.set(int(reading[1], 16) // 2 == 1)
                #cs_index.set(int(reading[1], 16) // 1 == 1)
                cs_servo_mode.set(int(reading[2], 16) // 8 == 1)
                #cs_target_limit.set(int(reading[2], 16) // 4 == 1)
                cs_target_mode.set(int(reading[2], 16) // 2 == 1)
                #cs_target_reached.set(int(reading[2], 16) // 1 == 1)
                cs_parked.set(int(reading[3], 16) // 8 == 1)
                overheat = int(reading[3], 16) // 4 == 1
                cs_overheat.set(overheat, severity = overheat, alarm = alarm.STATE_ALARM)
                cs_reverse.set(int(reading[3], 16) // 2 == 1)
                cs_running.set(int(reading[3], 16) // 1 == 1)

            piezomotor_connection.set(True, severity = alarm.NO_ALARM)
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False, severity = alarm.MAJOR_ALARM, alarm = alarm.COMM_ALARM)
        await asyncio.sleep(0.1)

dispatcher(update)
dispatcher(slow_update)

# Finally leave the IOC running with an interactive shell.
if debug:
    softioc.interactive_ioc(globals())
else:
    cothread.WaitForQuit()
