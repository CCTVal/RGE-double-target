from softioc import softioc, builder, asyncio_dispatcher
import asyncio
from telnetlib import Telnet
import re

# Create an asyncio dispatcher, the event loop is now running
dispatcher = asyncio_dispatcher.AsyncioDispatcher()

# Set the record prefix
builder.SetDeviceName("RGE-TEMP")

# Create some records
user_setp1 = builder.aOut('USER-TEMP-SETP1', initial_value=20, always_update=True,
                          on_update = lambda v: set_setpoint(1, v))
user_setp2 = builder.aOut('USER-TEMP-SETP2', initial_value=20, always_update=True,
                          on_update = lambda v: set_setpoint(2, v))

reference_temp = builder.aIn('REF-TEMPERATURE', initial_value=0)
setp1 = builder.aIn('TEMP-SETP1', initial_value=250)
setp2 = builder.aIn('TEMP-SETP2', initial_value=250)
temp_a = builder.aIn('TEMP-READ-A', initial_value=0)
temp_b = builder.aIn('TEMP-READ-B', initial_value=0)
temp_c = builder.aIn('TEMP-READ-C', initial_value=0)
temp_d = builder.aIn('TEMP-READ-D', initial_value=0)

lakeshore_connection = builder.boolIn('LAKESHORE-CONNECTION', initial_value = True)
ioc_heartbeat = builder.boolIn('TEMPERATURE-IOC-HEARTBEAT', initial_value = True)

lakeshore_ip = builder.stringOut('LAKESHORE-IP', initial_value = "192.168.1.118")
lakeshore_port = builder.stringOut('LAKESHORE-PORT', initial_value = "7777")

# Boilerplate get the IOC started
builder.LoadDatabase()
softioc.iocInit(dispatcher)

# Connect to lakeshore equipment

async def set_setpoint(setpoint, value=-float("inf")):
    if value == -float("inf"):
        print("Not enough parameters for setpoint setting")
        return
    try:
        '''
        with Telnet(lakeshore_ip.get(), lakeshore_port.get()) as connection:
            connection.write(("SETP {sp}, {val}\n").format(sp = setpoint, val = value).encode("ascii"))
            connection.write(("SETP? {sp}\n").format(sp = setpoint).encode("ascii"))
            reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
            lakeshore_connection.set(True)
        
        if setpoint == 1:
            setp1.set(reading)
        elif setpoint == 2:
            setp2.set(reading)
        '''
    except OSError as e:
        print("Error connecting to Lakeshore temperature controller.")
        print(e)
        lakeshore_connection.set(False)

# Start processes required to be run after iocInit
async def update():
    while True:
        ioc_heartbeat.set(not ioc_heartbeat.get())
        try:
            '''
            with Telnet(lakeshore_ip.get(), lakeshore_port.get()) as connection:
                connection.write(("KRDG?A\n").encode("ascii"))
                reading = float(re.match('.*?(-?\d+\.?\d*)', str(connection.read_until(b"\n")))[1])
                temp_a.set(reading)
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
                lakeshore_connection.set(True)
            '''
        except OSError as e:
            print("Error connecting to Lakeshore temperature controller.")
            print(e)
            lakeshore_connection.set(False)
        await asyncio.sleep(1)

dispatcher(update)

# Finally leave the IOC running with an interactive shell.
softioc.interactive_ioc(globals())
