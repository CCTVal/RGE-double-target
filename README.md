# Hall B Run Group-E solid target control system

This is the control system for the solid target system to be used at the double target experiment at Hall B of Thomas Jefferson National Accelerator Facilities (aka. J-Lab). The system holds five different solid targets and two empty slots in a ribbon which is moved by a motor. This repository contains the code used to measure the ribbon's position and move the ribbon.

## Running

`motor_controller.py` is the main IOC, and should be run at the Raspberry Pi inside the CCTVal control box, when properly connected to the rest of the system.

An additional IOC should be run in any device inside the local network to speak with the Lakeshore 336 temperature control device.

`gui` directory contains the screens to be used from the control room to interact with the system.

## Contact

Any questions should be directed towards the in-charge CCTVal target specialist, or to vicente.saona@usm.cl
