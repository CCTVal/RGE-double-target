# Process variables

This document list all process variables used for Jefferson Lab's hall B Solid Target movement system on Run Group E Double Target Experiment.

Every PV has the prefix ``CCTVAL_DT_PMD301:``, so a PV complete name would look, for example, like this: ``CCTVAL_DT_PMD301:SHOULD-STOP``.

## Movement commands

1. **GO-TO-TARGET-POSITION0** :: Bool :: Start movement protocol to put empty space (#0) in the center of the structure
1. **GO-TO-TARGET-POSITION1** :: Bool :: Start movement protocol to put space #1 in the center of the structure
1. **GO-TO-TARGET-POSITION2** :: Bool :: Start movement protocol to put space #2 in the center of the structure
1. **GO-TO-TARGET-POSITION3** :: Bool :: Start movement protocol to put space #3 in the center of the structure
1. **GO-TO-TARGET-POSITION4** :: Bool :: Start movement protocol to put space #4 in the center of the structure
1. **GO-TO-TARGET-POSITION5** :: Bool :: Start movement protocol to put space #5 in the center of the structure
1. **GO-TO-TARGET-POSITION6** :: Bool :: Start movement protocol to put empty space (#6) in the center of the structure

## Other commands

1. **USER-TARGET-POSITION** :: Analog :: An analog encoder - readable position that should be searched. When this is changed, the motor will start moving toward that position.
1. **SHOULD-STOP** :: Bool :: "Stop" button - related PV. When this gets to "True", all movement should stop during the next two seconds.
1. **USER-MOTOR-COMMAND** :: String :: A command sent directly to PMD301 motor driver. USE WITH CAUTION. Syntax is not checked for these commands, so a bad written command might break communication with the controller, making it necessary to restart the electric box.
1. **STEP-FORWARD** :: Bool :: "Step fwd." button - related PV. When this gets to "True", the motor should go 500 steps forward. Intended for calibration purposes.
1. **STEP-BACKWARD** :: Bool :: "Step fwd." button - related PV. When this gets to "True", the motor should go 500 steps backward. Intended for calibration purposes.
1. **SMALL-STEP-FORWARD** :: Bool :: "Step fwd." button - related PV. When this gets to "True", the motor should go 50 steps forward. Intended for calibration purposes.
1. **SMALL-STEP-BACKWARD** :: Bool :: "Step fwd." button - related PV. When this gets to "True", the motor should go 50 steps backward. Intended for calibration purposes.

## Configuration

1. **MAIN-ENCODER** :: String :: Which encoder system should be used as reference. Possible values are:
    1. "analog": Use the linear potentiometer as reference. This still counts the piano steps as it is moving toward its target position.
    2. "piano": Use the "piano" encoder as reference. This system has a stripped pattern so it is possible to read an intermittent signal while the system is moving. Each step corresponds to 1 [mm]. Using this as main encoder, it is still possible to see analog encoder reading as a reference value.
    3. "motor": Not using any encoder to guide the movement, just give the amount of motor steps registered in association to each target.
1. **MOTOR-GAIN** :: Analog :: How many motor steps should be given for each analog encoder step. Reference value: 0.0033
1. **NOISE-SUPRESSION** :: Analog :: The algorithm reads the analog encoder many times, and takes the mean value. This PV indicates how many times should it read the encoder.
1. **OVERSTEP** :: Analog :: The movement algorithm has two steps. One for coarse-grain positioning, near the target position, before the fine-grain tuning. This PV indicates the distance (in motor steps) between the first reference and the final target position. This value is necessary and must be positive. Reference value: 30000
1. **MOTOR-SPEED** :: Analog :: Movement speed informed directly to PMD301 motor controller. Reference value: 500

## Calibration commands

1. **CALIBRATE-ANALOG** :: Bool :: Start calibration protocol, going to both limit switches and use their positions as reference for a linear transformation for every target position.
1. **CALIBRATE-PIANO** :: Bool :: Start calibration protocol for piano encoder reference positions.
1. **CALIBRATE-MOTOR** :: Bool :: Start calibration protocol for motor steps reference positions.
1. **CALIBRATE-ALL** :: Bool :: Start calibration for all three systems.
1. **AUTO-CALIBRATION** :: Bool :: Calibrate every time a movement is ordered.
1. **SEARCH-PIANO-POSITIONS** :: Bool :: Using analog encoder positions as reference, redefine piano encoder reference positions for each target.
1. **SEARCH-MOTOR-POSITIONS** :: Bool :: Using analog encoder positions as reference, redefine motor steps reference to reach each target.

## Reference positions

1. **TARGET-POSITION0** :: Analog :: Reference analog encoder reading for the empty target (#0) centered position.
1. **TARGET-POSITION1** :: Analog :: Reference analog encoder reading for the target #1 centered position.
1. **TARGET-POSITION2** :: Analog :: Reference analog encoder reading for the target #2 centered position.
1. **TARGET-POSITION3** :: Analog :: Reference analog encoder reading for the target #3 centered position.
1. **TARGET-POSITION4** :: Analog :: Reference analog encoder reading for the target #4 centered position.
1. **TARGET-POSITION5** :: Analog :: Reference analog encoder reading for the target #5 centered position.
1. **TARGET-POSITION6** :: Analog :: Reference analog encoder reading for the empty target (#6) centered position.

1. **TARGET-PIANO-POSITION0** :: Analog :: Amount of piano encoder steps needed from backward limit switch to centre the empty target (#0).
1. **TARGET-PIANO-POSITION1** :: Analog :: Amount of piano encoder steps needed from backward limit switch to centre the target #1.
1. **TARGET-PIANO-POSITION2** :: Analog :: Amount of piano encoder steps needed from backward limit switch to centre the target #2.
1. **TARGET-PIANO-POSITION3** :: Analog :: Amount of piano encoder steps needed from backward limit switch to centre the target #3.
1. **TARGET-PIANO-POSITION4** :: Analog :: Amount of piano encoder steps needed from backward limit switch to centre the target #4.
1. **TARGET-PIANO-POSITION5** :: Analog :: Amount of piano encoder steps needed from backward limit switch to centre the target #5.
1. **TARGET-PIANO-POSITION6** :: Analog :: Amount of piano encoder steps needed from backward limit switch to centre the empty target (#6).

1. **TARGET-MOTOR-POSITION0** :: Analog :: Amount of motor steps needed from backward limit switch to centre the empty target (#0).
1. **TARGET-MOTOR-POSITION1** :: Analog :: Amount of motor steps needed from backward limit switch to centre the target #1.
1. **TARGET-MOTOR-POSITION2** :: Analog :: Amount of motor steps needed from backward limit switch to centre the target #2.
1. **TARGET-MOTOR-POSITION3** :: Analog :: Amount of motor steps needed from backward limit switch to centre the target #3.
1. **TARGET-MOTOR-POSITION4** :: Analog :: Amount of motor steps needed from backward limit switch to centre the target #4.
1. **TARGET-MOTOR-POSITION5** :: Analog :: Amount of motor steps needed from backward limit switch to centre the target #5.
1. **TARGET-MOTOR-POSITION6** :: Analog :: Amount of motor steps needed from backward limit switch to centre the empty target (#6).

1. **ANALOG-OFFSET** :: Analog :: In the process of modifying the analog encoder reference positions, an amount that should be added to each position. It always goes automatically back to zero after the modification.
1. **PIANO-OFFSET** :: Analog :: In the process of modifying the analog encoder reference positions, an amount that should be added to each position. It always goes automatically back to zero after the modification.
1. **MOTOR-OFFSET** :: Analog :: In the process of modifying the analog encoder reference positions, an amount that should be added to each position. It always goes automatically back to zero after the modification.

# Read-only PVs

## General information and controller status

1. **PIEZOMOTOR-IOC-HEARTBEAT** :: Bool :: Value changed every second.
1. **CENTERED** :: MBB :: What is centered. Possible values are `Wire`, `C`, `Al`, `Cu`, `Sn`, `Pb`, `Empty` and `Unknown`, corresponding to each target. Value is `Unknown` while moving.
1. **PIEZOMOTOR-CONTROLLER-VERSION** :: String :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-COMMUNICATION-ERROR** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-ENCODER-ERROR** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-VOLTAGE-ERROR** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-COMMAND-ERROR** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-RESET** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-X-LIMIT** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-SCRIPT-IS-RUNNING** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-INDEX-DETECTED** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-IS-SERVO-MODE** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-TARGET-LIMIT** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-TARGET-MODE** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-TARGET-REACHED** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-PARKED** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-OVERHEAT** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-REVERSE** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **PIEZOMOTOR-CONTROLLER-RUNNING** :: Bool :: Obtained directly from PMD301 controller (details in its own manual)
1. **IS-MOVING** :: Bool :: Assigned as `true` when starting a movement algorithm and turned back to `false` after the movement is complete or when an emergency stop is dictated.
1. **CONTROLLER-RESPONSE** :: String :: When sending a command to the PM301 motor controller, a response is expected. That response is recorded in this PV.
1. **PIEZOMOTOR-CONNECTION** :: Bool :: Set to `false` in case of any problem connecting to the motor controller.
1. **CONTROLLER-SERIAL-PORT** :: String :: Raspberry serial port used to connect to the motor controller.
1. **CONTROLLER-BAUD-RATE** :: Analog :: Connection baud rate.

## Encoder data

1. **MAIN-ENCODER-READING** :: Analog :: Reading of linear potentiometer, analog encoder.
1. **PIANO-ENCODER-READING** :: Analog :: Steps counted via piano encoder since last backward limit switch activation.
1. **PIANO-READING** :: Bool :: Current reading of piano encoder.
1. **MOTOR-STEPS-GIVEN** :: Analog :: Steps that the motor has been instructed to give since last backward limit switch activation.

## Limits and calibration

1. **FORWARD-LIMIT-SWITCH-POSITION** :: Analog :: last analog encoder reading got while forward limit switch was active.
1. **FORWARD-LIMIT-SWITCH** :: Bool :: Whether forward limit switch is active or not.
1. **BACKWARD-LIMIT-SWITCH-POSITION** :: Bool :: last analog encoder reading got while backward limit switch was active.
1. **BACKWARD-LIMIT-SWITCH** :: Bool :: Whether forward limit switch is active or not.
1. **REFERENCE-FORWARD-LIMIT-SWITCH** :: Bool :: Analog encoder reading used for last calibration. Will be used for next calibration process.
1. **REFERENCE-BACKWARD-LIMIT-SWITCH** :: Bool :: Analog encoder reading used for last calibration. Will be used for next calibration process.
1. **REFERENCE-PIANO-LIMIT-SWITCH** :: Bool :: Piano encoder reading used for last calibration. Will be used for next calibration process.
1. **REFERENCE-MOTOR-LIMIT-SWITCH** :: Bool :: Motor step count used for last calibration. Will be used for next calibration process.