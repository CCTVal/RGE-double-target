# Hall B Run Group-E solid target control system

This is the control system for the solid target system to be used at the double target experiment at Hall B of Thomas Jefferson National Accelerator Facilities (aka. J-Lab). The system holds five different solid targets and two empty slots in a ribbon which is moved by a motor. This repository contains the code used to measure the ribbon's position and move the ribbon.

To know how to use the Graphical User Interface, please refer to `gui/docs.md`

## Running

`motor_controller.py` is the main EPICS Input and Output Controller (IOC), and should be run at the Raspberry Pi inside the CCTVal control box, when properly connected to the rest of the system. It is programed to run on startup with this crontab instruction:
```@reboot /usr/bin/python /home/pi/RGE-double-target/motor_controller.py 2>&1 | tee -a /home/pi/test.log```
Which not only runs the IOC, but also redirects some logging to the `test.log` file. In case of any problem, you can read that log file for troubleshooting.
The only file that is actually needed in the Raspberry is `motor_controller.py`.

An additional IOC should be run in any device inside the local network to speak with the Lakeshore 336 temperature control device. For more information about this, contact James Maxwell, or anyone in JLab's target group.

`gui` directory contains the screens to be used from the counting room to interact with the system, and guidance on how to use it.

## Connecting to the Raspberry

When the Raspberry is in Hall B, it should be connected to the Hall's network, `129.57.160.0/22`, with the IP address `129.57.161.30`. This means it cannot be reached from outside the Hall network unless you log into some gateway like ``hallgw.jlab.org``. From counting room computers it can be reached directly.

In any case, the Wi-fi interface is configured to connect to the E-016 router with the IP address `192.168.1.121`, so in case of a network problem, you can always go down to the hall with the router and a laptop, plug the router to electric power anywhere in the hall and then with the laptop connect to ``E016_Target_CONDOR`` Wi-fi network (password is ``SiLabaLiS``) and then ssh into the Raspberry.

## About the code itself

The first lines are declaring the EPICS PVs and some hardware related-stuff. Since this is expected to be used through EPICS, from the gui you can see the PVs, in the first lines the functions that are triggered by each PV in their `on_update` argument and then route the program from there.

At the end there are two "update" functions that have an infinite loop, periodically updating relevant variables like potentiometer reading and piezomotor controller alarms.

## Contact

Any questions should be directed towards the in-charge solid target specialist, or to vicente.saona@usm.cl
