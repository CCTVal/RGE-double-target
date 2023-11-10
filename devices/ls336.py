import telnetlib
import re
from softioc import builder, alarm


class Device():
    """Makes library of PVs needed for LS336 and provides methods connect them to the device

    Attributes:
        pvs: dict of Process Variables keyed by name
        channels: channels of device
    """

    def __init__(self, device_name, settings):
        '''Make PVs needed for this device and put in pvs dict keyed by name
        '''
        self.device_name = device_name
        self.settings = settings
        self.channels = settings['channels']   # this is a list of channels in order
        self.out_channels = settings['out_channels']   # dcit keyed on channel name of output channel
        self.pvs = {}
        sevr = {'HHSV': 'MAJOR', 'HSV': 'MINOR', 'LSV': 'MINOR', 'LLSV': 'MAJOR', 'DISP': '0'}

        mode_list = ['Off', 'Closed Loop', 'Zone', 'Open Loop']
        range_list = ['Off', 'Low', 'Med', 'High']

        self.p_limit = [self.calc_heater_power_limit(1), self.calc_heater_power_limit(2)]  # LS336 power limits per channel

        for channel in settings['channels']:  # set up PVs for each channel
            if "_TI" in channel:
                self.pvs[channel] = builder.aIn(channel, **sevr)
            elif "None" in channel:
                pass
            else:
                print(channel)
                self.pvs[channel + "_TI"] = builder.aIn(channel + "_TI", **sevr)
                self.pvs[channel + "_Heater"] = builder.aIn(channel + "_Heater", **sevr)
                self.pvs[channel + "_Heater_W"] = builder.aIn(channel + "_Heater_W", **sevr)

                self.pvs[channel + "_Manual"] = builder.aOut(channel + "_Manual", on_update_name=self.do_sets, **sevr)
                self.pvs[channel + "_kP"] = builder.aOut(channel + "_kP", on_update_name=self.do_sets)
                self.pvs[channel + "_kI"] = builder.aOut(channel + "_kI", on_update_name=self.do_sets)
                self.pvs[channel + "_kD"] = builder.aOut(channel + "_kD", on_update_name=self.do_sets)
                self.pvs[channel + "_SP"] = builder.aOut(channel + "_SP", on_update_name=self.do_sets, **sevr)

                self.pvs[channel + "_Mode"] = builder.mbbOut(channel + "_Mode", *mode_list, on_update_name=self.do_sets)
                self.pvs[channel + "_Range"] = builder.mbbOut(channel + "_Range", *range_list,
                                                              on_update_name=self.do_sets)

    def calc_heater_power_limit(self, channel):
        """Calculate power limit for to LS336 heater channel. Needs the channel, and nominal (25 or 50 ohm) and
        real heater resistance from settings file. """
        nominal, real = self.settings['heater_resistance'][int(channel) - 1]
        voltage = 50
        if channel == 1:
            current = 2 if (nominal == 25) else 1
        else:
            current = 1.41 if (nominal == 25) else 1
        pc = current * current * real
        pv = voltage * voltage / real
        p_limit = pc if pc < pv else pv  # power limit from resistance and setting
        print(f"Channel {channel} power limit: {p_limit}")
        return p_limit

    async def connect(self):
        '''Open connection to device'''
        try:
            self.t = DeviceConnection(self.settings['ip'], self.settings['port'], self.settings['timeout'])
            await self.read_outs()
        except Exception as e:
            print(f"Failed connection on {self.settings['ip']}, {e}")

    async def read_outs(self):
        """Read and set OUT PVs at the start of the IOC"""
        for i, channel in enumerate(self.channels):
            if "None" in channel: continue
            if "_TI" in channel: continue
            out_channel = self.out_channels[channel]
            try:
                pids = self.t.read_pid(out_channel)
                self.pvs[channel + '_kP'].set(pids[0])
                self.pvs[channel + '_kI'].set(pids[1])
                self.pvs[channel + '_kD'].set(pids[2])
                self.pvs[channel + '_Mode'].set(int(self.t.read_outmode(out_channel)))
                self.pvs[channel + '_Range'].set(int(self.t.read_range(out_channel)))
                self.pvs[channel + '_SP'].set(self.t.read_setpoint(out_channel))
                self.pvs[channel + '_Manual'].set(self.t.read_man_heater(out_channel))
            except OSError as e:
                print("Error initializing outs.", e)
                await self.reconnect()

    async def reconnect(self):
        del self.t
        print("Connection failed. Attempting reconnect.")
        await self.connect()

    async def do_sets(self, new_value, pv):
        """If PV has changed, find the correct method to set it on the device"""
        pv_name = pv.replace(self.device_name + ':', '')  # remove device name from PV to get bare pv_name
        pv = pv_name.split("_")[0]  # pv_name root
        out_channel = self.out_channels[pv]
        in_channel = self.channels.index(pv) + 1
        # figure out what type of PV this is, and send it to the right method
        try:
            if 'kP' in pv_name or 'kI' in pv_name or 'kD' in pv_name:  # is this a PID control record?
                d = {}
                k_list = ['kP', 'kI', 'kD']
                for k in k_list:
                    d[k] = self.pvs[pv + "_" + k].get()  # read pvs to send to device
                values = self.t.set_pid(out_channel, d['kP'], d['kI'], d['kD'])
                [self.pvs[pv + "_" + k].set(values[i]) for i, k in enumerate(k_list)]  # set values read back
            elif 'SP' in pv_name:  # is this a setpoint?
                self.pvs[pv_name].set(self.t.set_setpoint(out_channel, new_value))  # set returned value
            elif 'Manual' in pv_name:  # is this a manual out?
                self.pvs[pv_name].set(self.t.set_man_heater(out_channel, new_value))  # set returned value
            elif 'Mode' in pv_name:
                self.pvs[pv_name].set(int(self.t.set_outmode(out_channel, new_value, in_channel, 0)))  # set returned value
            elif 'Range' in pv_name:
                self.pvs[pv_name].set(int(self.t.set_range(out_channel, new_value)))  # set returned value
            else:
                print('Error, control PV not categorized.')
        except OSError:
            await self.reconnect()
        return

    async def do_reads(self):
        '''Match variables to methods in device driver and get reads from device'''
        try:
            temps = self.t.read_temps()
            for i, channel in enumerate(self.channels):
                if "None" in channel: continue
                if "_TI" in channel:
                    self.pvs[channel].set(temps[i])
                    self.remove_alarm(channel)
                else:
                    self.pvs[channel + '_TI'].set(temps[i])
                    self.remove_alarm(channel+'_TI')
                    heat = self.t.read_heater(i + 1)
                    self.pvs[channel + '_Heater'].set(heat)
                    decade = self.pvs[channel + '_Range'].get() - 3
                    if decade == -3:  # "off" range
                        power = 0
                    else:
                        power = self.p_limit[self.out_channels[channel] - 1] * 10**decade * heat / 100
                    self.pvs[channel + '_Heater_W'].set(power)
        except OSError:
            for channel in self.channels:
                if "None" in channel: continue
                if "_TI" in channel:   # setting read error on TI only
                    self.set_alarm(channel)
                else:
                    self.set_alarm(channel + '_TI')
            self.reconnect()
        else:
            return True


    def set_alarm(self, channel):
        """Set alarm and severity for channel"""
        self.pvs[channel].set_alarm(severity=1, alarm=alarm.READ_ALARM)

    def remove_alarm(self, channel):
        """Remove alarm and severity for channel"""
        self.pvs[channel].set_alarm(severity=0, alarm=alarm.NO_ALARM)


class DeviceConnection():
    '''Handle connection to Lakeshore Model 336 via Telnet. 
    '''

    def __init__(self, host, port, timeout):
        '''Open connection to Lakeshore 218
        Arguments:
            host: IP address
        port: Port of device
        '''
        self.host = host
        self.port = port
        self.timeout = timeout

        try:
            self.tn = telnetlib.Telnet(self.host, port=self.port, timeout=self.timeout)
        except Exception as e:
            print(f"LS336 connection failed on {self.host}: {e}")

        self.read_regex = re.compile('([+-]\d+.\d+),([+-]\d+.\d+),([+-]\d+.\d+),([+-]\d+.\d+)')
        self.pid_regex = re.compile('([+-]\d+.\d+),([+-]\d+.\d+),([+-]\d+.\d+)')
        self.out_regex = re.compile('(\d),(\d),(\d)')
        self.range_regex = re.compile('(\d)')
        self.setp_regex = re.compile('([+-]\d+.\d+)')
        # self.set_regex = re.compile('SP(\d) VALUE: (\d+.\d+)')
        # self.ok_response_regex = re.compile(b'!a!o!\s\s')

    def read_temps(self):
        '''Read temperatures for all channels.'''
        try:
            self.tn.write(bytes(f"KRDG? 0\n", 'ascii'))  # Kelvin reading
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.read_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values

        except Exception as e:
            print(f"LS336 pid read failed on {self.host}: {e}")
            raise OSError('LS336 read')

    def set_pid(self, channel, P, I, D):
        '''Setup PID for given channel (1 or 2).'''
        try:
            self.tn.write(bytes(f"PID {channel},{P},{I},{D}\n", 'ascii'))
            return self.read_pid(channel)

        except Exception as e:
            print(f"LS336 pid set failed on {self.host}: {e}")
            raise OSError('LS336 pid set')

    def read_pid(self, channel):
        '''Read PID values for given channel (1 or 2).'''
        try:
            self.tn.write(bytes(f"PID? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.pid_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values

        except Exception as e:
            print(f"LS336 pid read failed on {self.host}: {e}")
            raise OSError('LS336 heater pid read')

    def read_heater(self, channel):
        '''Read Heater output (%) for given channel (1 or 2).'''
        try:
            self.tn.write(bytes(f"HTR? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.setp_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 heater read failed on {self.host}: {e}")
            raise OSError('LS336 heater read')

    def read_man_heater(self, channel):
        '''Read Manual Heater output (%) for given channel (1 or 2).'''
        try:
            self.tn.write(bytes(f"MOUT? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.setp_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 heater manual read failed on {self.host}: {e}")
            raise OSError('LS336 heater manual read')

    def set_man_heater(self, channel, value):
        '''Read Manual Heater output (%) for given channel (1 or 2).'''
        try:
            self.tn.write(bytes(f"MOUT {channel},{value}\n", 'ascii'))
            self.tn.write(bytes(f"MOUT? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.setp_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 heater manual set  failed on {self.host}: {e}")
            raise OSError('LS336 heater manual set')

    def set_outmode(self, channel, mode, in_channel, powerup_on):
        '''Setup output and readback.
        Arguments:
            channel: out put channel (1 to 4)
            mode: 0=Off, 1=Closed Loop
            in_channel: input channel for control 0=None, 1=A to 4=D
            powerup_on: Output should remain on after power cycle? 1 is yes, 0 no.
        '''
        try:
            self.tn.write(bytes(f"OUTMODE {channel},{mode},{in_channel},{powerup_on}\n", 'ascii'))
            self.tn.write(bytes(f"OUTMODE? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.out_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 outmode set  failed on {self.host}: {e}")
            raise OSError('LS336 outmode set')

    def read_outmode(self, channel):
        '''Read output.
        Arguments:
            channel: out put channel (1 to 4)
        '''
        try:
            self.tn.write(bytes(f"OUTMODE? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.out_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 outmode read failed on {self.host}: {e}")
            raise OSError('LS336 outmode read')

    def set_range(self, channel, hrange):
        '''Setup output and readback. Has no effect if outmode is off.
        Arguments:
            channel: output channel (1 to 4)
            hrange: 0=off, 1=Low, 2=Med, 3=High
        '''
        try:
            self.tn.write(bytes(f"RANGE {channel},{hrange}\n", 'ascii'))
            self.tn.write(bytes(f"RANGE? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.range_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 range set failed on {self.host}: {e}")
            raise OSError('LS336 range set')

    def read_range(self, channel):
        '''Read range. Has no effect if outmode is off.
        Arguments:
            channel: output channel (1 to 4)
        '''
        try:
            self.tn.write(bytes(f"RANGE? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.range_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 range read failed on {self.host}: {e}")
            raise OSError('LS336 range read')

    def set_setpoint(self, channel, value):
        '''Setup setpoint and read back.
        Arguments:
            channel: output channel (1 to 4)
            value: setpoint in units of loop sensor
        '''
        try:
            self.tn.write(bytes(f"SETP {channel},{value}\n", 'ascii'))
            self.tn.write(bytes(f"SETP? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.setp_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 range set failed on {self.host}: {e}")
            raise OSError('LS336 range set')

    def read_setpoint(self, channel):
        '''Setup setpoint and read back.
        Arguments:
            channel: output channel (1 to 4)
        '''
        try:
            self.tn.write(bytes(f"SETP? {channel}\n", 'ascii'))
            data = self.tn.read_until(b'\n', timeout=2).decode('ascii')  # read until carriage return
            m = self.setp_regex.search(data)
            values = [float(x) for x in m.groups()]
            return values[0]

        except Exception as e:
            print(f"LS336 setpoint set failed on {self.host}: {e}")
            raise OSError('LS336 setpoint set')
