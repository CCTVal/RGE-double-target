from softioc import softioc, builder, asyncio_dispatcher, alarm
import asyncio
import yaml
import argparse
import importlib
import os
import datetime


async def main():
    """
    Run an IOC: load settings, create dispatcher, set name, do boilerplate, loop on device coroutine and start interactive interface
    Device to be set up comes from command line argument choosing option from settings file
    """
    ioc, settings, records = load_settings()

    os.environ['EPICS_CA_ADDR_LIST'] = settings['general']['epics_addr_list']
    os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'NO'

    dispatcher = asyncio_dispatcher.AsyncioDispatcher()
    device_name = settings['general']['prefix']
    builder.SetDeviceName(device_name)

    d = DeviceIOC(device_name, ioc, settings, records)
    await d.connect()
    builder.LoadDatabase()
    softioc.iocInit(dispatcher)

    async def loop():
        while True:
            await d.loop()

    dispatcher(loop)  # put functions to loop in here
    softioc.interactive_ioc(globals())


class DeviceIOC():
    """Set up PVs for a given device IOC, run thread to interact with device
    """

    def __init__(self, device_name, ioc, settings, records):
        '''
        Arguments:
            device_name: name of device for PV prefix
            settings: dict of device settings
            records: dict of record settings
        '''

        self.module = importlib.import_module(settings[ioc]['module'])
        self.records = records
        self.delay = settings[ioc]['delay']
        self.now = datetime.datetime.now()

        self.device = self.module.Device(device_name, settings[ioc])
        self.pv_time = builder.aIn(f"MAN:{ioc}_time")
        self.pv_time.set(datetime.datetime.now().timestamp())

        for name, entry in self.device.pvs.items():  # set the attributes of the PV (optional)
            if name in self.records:
                for field, value in self.records[name].items():
                    setattr(self.device.pvs[name], field, value)

    async def loop(self):
        """Read indicator PVS from controller channels. Delay time between measurements is in seconds.
        If read is successful, set timestamp PV for IOC.
         """
        await asyncio.sleep(self.delay)
        if await self.device.do_reads():  # get new readings from device and set into PVs
            self.pv_time.set(datetime.datetime.now().timestamp())   # set time of last successful update

    async def connect(self):
        await self.device.connect()


def load_settings():
    """Load device settings and records from YAML settings files.
    Argument parser allows '-s' to give a different folder, '-i' tells which IOC to run"""

    parser = argparse.ArgumentParser()
    parser.add_argument("-s", help="Settings file folder, default is here.")
    parser.add_argument("-i", help="Name of IOC to start")
    args = parser.parse_args()
    folder = args.s if args.s else '.'

    with open(f'{folder}/settings.yaml') as f:  # Load settings from YAML files
        settings = yaml.load(f, Loader=yaml.FullLoader)
    print(f"Loaded device settings from {folder}/settings.yaml.")

    with open(f'{folder}/records.yaml') as f:  # Load settings from YAML files
        records = yaml.load(f, Loader=yaml.FullLoader)
    print(f"Loaded records from {folder}/records.yaml.")

    ioc_list = list(settings.keys())
    ioc_list.remove('general')

    if args.i:
        ioc = args.i
    else:
        print("Select IOC to run from these entries in settings file using -i flag:")
        [print(f"  {x}") for x in ioc_list]
        exit()
    if ioc not in ioc_list:
        print("Given IOC not in settings file. Select from these:")
        [print(f"  {x}") for x in ioc_list]
        exit()

    return ioc, settings, records


if __name__ == "__main__":
    asyncio.run(main())
