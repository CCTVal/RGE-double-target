# Alarms

This is a list of every alarm that could be risen by Jefferson Lab's Hall B, Run Group E Double Target, Solid target control system.

1. ``PIEZOMOTOR-CONNECTION`` Communication alarm. The PV is set to false and a major alarm is risen. This means there is a problem connecting the Raspberry Pi with the Piezomotor controller PMD301. Suggested course of action: Call someone from chilean target group and try rebooting the electric box. Check the controller is on (there should be a LED indicator). If rebooting doesn't fix it, open the box and check the electrical supply of the controller and the USB connection between the controller and the Raspberry. Fastest way to solve is to change the box altogether.

1. ``PIANO-ENCODER-READING`` State alarm. A minor alarm is risen when the system uses analog linear encoder as reference and the piano encoder count is too different from the corresponding reference. If this alarm is risen, call someone from chilean target group and check the system temperature. if the difference from reference is little and temperature is considerably different from the calibration temperature, might be better to use piano encoder as main reference for movement. If the difference is large, then one of the encoders stopped working. Investigate which one using limit switches and motor steps. If you are sure one of them is working well, use that one as main reference. If you cannot ensure the proper working of either of the encoder systems, replace solid target system with a copy as soon as possible. If not possible, motor step count can be used as a temporary solution.

1. ``PIEZOMOTOR-CONTROLLER-OVERHEAT`` State alarm. A major alarm is risen when the PMD301 piezomotor controller informs that it is overheated. In this case, call someone from chilean target group, turn off the electric box if possible (though it should still work well, at least for a while), and then replace the electric box so the situation can be inspected further.

1. ``PIEZOMOTOR-CONTROLLER-COMMUNICATION-ERROR`` State alarm. A major alarm is risen when the PMD301 piezomotor controller informs of a communication error. In this case, call someone from chilean target group, and reboot the electric box. Report all detail available so the situation can be inspected further.

1. ``PIEZOMOTOR-CONTROLLER-VOLTAGE-ERROR`` State alarm. A major alarm is risen when the PMD301 piezomotor controller informs a voltage error. In this case, call someone from chilean target group. If the system is not working (and you need to use it), replace the electric box.

1. ``PIEZOMOTOR-CONTROLLER-COMMAND-ERROR`` State alarm. A major alarm is risen when the PMD301 piezomotor controller informs a command error. In this case, call someone from chilean target group and reboot the electric box.

1. ``CENTERED`` State alarm. A major alarm is risen each time the solid target switching system is activated. This is just in case the system is activated by accident. In that case, finish data acquisition run immediatly, go back to desired target and start a new run.