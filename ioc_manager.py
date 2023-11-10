from screenutils import Screen
import yaml
from softioc import softioc, builder, asyncio_dispatcher
import asyncio
import re
import time
import os.path
import subprocess
from threading import Thread
import aioca
import datetime


async def main():
    """
    IOC to manage IOCS. Sets up PVs for each IOC in settings file to allow starting and stopping.
    Uses Unix Screen to run master_ioc for each device IOC.
    """

    with open('settings.yaml') as f:  # Load settings from YAML config file
        settings = yaml.load(f, Loader=yaml.FullLoader)

    os.environ['EPICS_CA_ADDR_LIST'] = settings['general']['epics_addr_list']
    #os.environ['EPICS_CAS_BEACON_ADDR_LIST'] = settings['general']['epics_beacon_addr_list']
    os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'NO'
    #os.environ['EPICS_CAS_AUTO_BEACON_ADDR_LIST'] = 'NO'

    dispatcher = asyncio_dispatcher.AsyncioDispatcher()
    device_name = settings['general']['prefix'] + ':MAN'
    builder.SetDeviceName(device_name)

    i = IOCManager(device_name, settings)
    builder.LoadDatabase()
    softioc.iocInit(dispatcher)

    async def loop():
        while True:
            await i.heartbeat()

    dispatcher(loop)  # put functions to loop in here
    softioc.interactive_ioc(globals())


class IOCManager:
    """
    Handles screens which run iocs. Makes PVs to control each ioc.
    """

    def __init__(self, device_name, settings):
        """
        Make control PVs for each IOC. "pvs" dict is keyed on name (e.g. flow), PV is labeled as name + 'control' (e.g. flow_control)
        """
        self.device_name = device_name
        self.settings = settings
        self.delay = settings['general']['delay']
        self.pvs = {}
        self.screens = {}     # Dict of all screens made for the iocs, keyed by screen name
        self.ioc_pvs = {}  # Dict of lists of all PVs in each screen instance, keyed by screen name


        for name in settings.keys():  # each IOC has controls to start, stop or reset
            if 'general' in name: continue
            self.pvs[name] = builder.mbbOut(name + '_control',
                                           ("Stop",'MINOR'),
                                           ("Run", 0),
                                           ("Reset",'MINOR'),
                                           on_update_name=self.screen_update
                                           )
            self.pvs[name+'_hb'] = builder.mbbOut(name+'_hb')
            #setattr(self.pvs[name+'_hb'], 'HIGH', 10)
            #setattr(self.pvs[name+'_hb'], 'LOW', 1)
            self.pvs[name].set(0)
        self.pv_all = builder.mbbOut('all',
                                       ("Stop",'MINOR'),
                                       ("Run", 0),
                                       ("Reset",'MINOR'),
                                       on_update=self.all_screen_update
                                       )
        self.pv_all.set(0)
        self.pv_pid = builder.mbbOut('pids_control',
                                       ("Stop",'MINOR'),
                                       ("Run", 0),
                                       ("Reset",'MINOR'),
                                       on_update=self.pid_update
                                       )
        self.pv_pid.set(0)
        self.ioc_regex = re.compile(f'{device_name}')

        self.pid_update(0)

    def screen_update(self, i, pv):
        """
        Multiple Choice PV has changed for the given control PV. Follow command. 0=Stop, 1=Start, 2=Reset
        """
        pv_name = pv.replace(self.device_name + ':', '')  # remove device name from PV to get bare pv_name
        if i==0:
            self.stop_ioc(pv_name)
        elif i==1:
            if Screen(pv_name).exists:
                self.reset_ioc(pv_name)   # if it already exists, restart it instead
                #pass        # if it already exists, do nothing
            else:
                self.start_ioc(pv_name)
        elif i==2:
            self.reset_ioc(pv_name)

    def all_screen_update(self, i):
        """
        Do update for all iocs in config file with autostart set to True.
        """
        for name in self.settings.keys():
            if 'general' in name: continue
            if self.settings[name]['autostart']:
                #self.screen_update(i, pv)
                self.pvs[name].set(i)

    def start_ioc(self, pv_name):
        """
        Start screen to run ioc, then run ioc. Get PV names from IOC after run.
        """
        name = pv_name.replace('_control', '')  # remove suffix from pv name to name screen
        self.st = StartThread(self, name, self.screens)
        self.st.daemon = True
        self.st.start()


    def stop_ioc(self, pv_name):
        """
        Kill screen and ioc running within it.
        """
        name = pv_name.replace('_control', '')  # remove suffix from pv name to name screen
        if Screen(name).exists:
            subprocess.run(["screen","-XS",name,"kill"])
            self.pvs[name].set(0)
        if name in self.screens:
            del self.screens[name]

    def reset_ioc(self, pv_name):
        """
        Kill screen and ioc running within it, then restart.
        """
        name = pv_name.replace('_control', '')  # remove suffix from pv name to name screen

        self.stop_ioc(pv_name)
        time.sleep(1)
        self.start_ioc(pv_name)

    def pid_update(self, i):
        '''Start and stop the PID IOC '''
        if i==0:
            if Screen('pids').exists:
                Screen('pids').send_commands(f'exit')
                subprocess.run(["screen","-XS",'pids',"kill"])
            self.pv_pid.set(0)
        elif i==1:
            screen = Screen('pids', True)
            Screen('pids').send_commands(f'python pid/pids.py')
            screen.enable_logs(f"{self.settings['general']['log_dir']}/pids")
        elif i==2:
            if Screen('pids').exists:
                Screen('pids').send_commands(f'exit')
                subprocess.run(["screen","-XS",'pids',"kill"])
            screen = Screen('pids', True)
            screen.send_commands(f'python pid/pids.py')
            screen.enable_logs(f"{self.settings['general']['log_dir']}/pids")

    async def heartbeat(self):
        """Check last time written versus current time for each IOC"""
        group = []
        await asyncio.sleep(self.delay)
        for name in self.screens:
            group.append(self.time_check(name))
        await asyncio.gather(*group)

    async def time_check(self, name):
        try:
            t = await aioca.caget(f"{self.device_name}:{name}_time")
            now = datetime.datetime.now().timestamp()
            self.pvs[name+'_hb'].set(int(now - float(t)))
        except aioca.CANothing as e:
            print("Get error:", e, f"{self.device_name}:{name}_time")

class StartThread(Thread):
    '''Thread to interact with IOCs in screens. Each thread starts one ioc.'''

    def __init__(self, parent, name, screens):
        Thread.__init__(self)
        self.parent = parent
        self.name = name
        self.screens = screens

    def run(self):
        '''
        Start screen to run ioc, then run ioc. Wait until started, then get PV names from IOC after run.
        '''
        screen = Screen(self.name, True)

        screen.send_commands('bash')
        screen.send_commands(f'python master_ioc.py -i {self.name}')
        screen.enable_logs(f"{self.parent.settings['general']['log_dir']}/{self.name}")
        screen.send_commands('softioc.dbl()')

        elapsed = 0
        pvs = []
        while True:           # wait until ioc starts to get response
            #print("Waiting for logfile for", self.name)
            if os.path.getsize(f"{self.parent.settings['general']['log_dir']}/{self.name}") > 10:
                with open(f"{self.parent.settings['general']['log_dir']}/{self.name}") as f:
                    for line in f:
                        match = re.search(f"({self.parent.settings['general']['prefix']}.+)\s", line)
                        if match:
                            pvs.append(match.group(1))
                self.parent.ioc_pvs[self.name] = pvs   # send the list of pvs back to manager
                self.parent.pvs[self.name].set(1)
                break
            time.sleep(1)
            elapsed += 1
            if elapsed > 20:
                print(f"Failed to start {self.name} ioc, died waiting on log file after {elapsed} seconds.")
                break

        self.screens[self.name] = screen



if __name__ == "__main__":
    asyncio.run(main())