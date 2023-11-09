from softioc import softioc, builder, asyncio_dispatcher
import asyncio
import serial
import re

# Create an asyncio dispatcher, the event loop is now running
dispatcher = asyncio_dispatcher.AsyncioDispatcher()

# Set the record prefix
builder.SetDeviceName("DMC01:A_")

# Create some records
user_target_position = builder.aOut('USER-TARGET-PSOTION', initial_value=20, always_update=True,
                          on_update = lambda v: set_target_position(v))

controller_model = builder.stringIn('PIEZOMOTOR-CONTROLLER-VERSION', initial_value = "PMD301")

target_position = builder.aIn('TARGET-POSITION', initial_value=250)
main_encoder_reading = builder.aIn('MAIN-ENCODER-READING', initial_value=-1)
secondary_encoder_reading = builder.aIn('SECONDARY-ENCODER-READING', initial_value=-1)
piano_encoder_reading = builder.aIn('PIANO-ENCODER-READING', initial_value=-1)
linear_potentiometer_reading = builder.aIn('LINEAR_POTENTIOMETER-READING', initial_value=-1)

piezomotor_connection = builder.boolIn('PIEZOMOTOR-CONNECTION', initial_value = False)
ioc_heartbeat = builder.boolIn('PIEZOMOTOR-IOC-HEARTBEAT', initial_value = False)

controller_port = builder.stringIn('CONTROLLER-SERIAL-PORT', initial_value = "COM4")
baud_rate = builder.boolIn('CONTROLLER-BAUD-RATE', initial_value = 115200)

# Boilerplate get the IOC started
builder.LoadDatabase()
softioc.iocInit(dispatcher)

async def set_target_position(value=-float("inf")):
    if value == -float("inf"):
        print("Not enough parameters for target position setting")
        return
    try:
        '''
            connection.write(("SETP {sp}, {val}\n").format(sp = setpoint, val = value).encode("ascii"))
            connection.write(("SETP? {sp}\n").format(sp = setpoint).encode("ascii"))
            reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
        '''
        piezomotor_connection.set(True)
        
        if setpoint == 1:
            setp1.set(reading)
        elif setpoint == 2:
            setp2.set(reading)
        
    except OSError as e:
        print("Error connecting to PiezoMotor controller.")
        print(e)
        piezomotor_connection.set(False)

# Start processes required to be run after iocInit
async def update():
    while True:
        ioc_heartbeat.set(not ioc_heartbeat.get())
        try:
            with serial.Serial(controller_port.get, baud_rate) as connection:
                connection.write(("X1?\r").encode("ascii"))
                reading = connection.readline().decode()
                controller_model.set(reading)
                '''
                connection.write(("KRDG?B\n").encode("ascii"))
                reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
                temp_b.set(reading)
                connection.write(("KRDG?C\n").encode("ascii"))
                reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
                temp_c.set(reading)
                connection.write(("KRDG?D\n").encode("ascii"))
                reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
                temp_d.set(reading)
                connection.write(("TEMP?\n").encode("ascii"))
                reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
                reference_temp.set(reading)
                connection.write(("SETP?1\n").encode("ascii"))
                reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
                setp1.set(reading)
                connection.write(("SETP?2\n").encode("ascii"))
                reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
                setp2.set(reading)
                piezomotor_connection.set(True)
                '''
            
        except OSError as e:
            print("Error connecting to PiezoMotor controller.")
            print(e)
            piezomotor_connection.set(False)
        await asyncio.sleep(1)

dispatcher(update)

# Finally leave the IOC running with an interactive shell.
softioc.interactive_ioc(globals())
