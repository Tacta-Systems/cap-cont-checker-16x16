'''
This program performs cap, continuity, or reset sweeps

Hardware requirements:
- Keithley DMM6500 benchtop multimeter (our current unit's S/N is 04611761)
- 16x16 Array, with or without flex attached
- For arrays without flex attached, probe station aligner that joins flex to sensor
- Assembled 00013+00014 tester boards
- Arduino MEGA 2560 R3
  * F - F ribbon cable from Arduino P36/37 to GND
  * Male header pins, double length (Amazon B077N29TP5)
- Short (6") BNC to SMA cable + BNC to banana plug

- Add more wires here as the test setup gets built

Software requirements
- Python 3.x
  * pyvisa library (INSTALL)
    - NI-VISA library downloaded from NI website
  * numpy library
  * serial library
  * csv library
  * datetime library
'''

import serial
import serial.tools.list_ports
import time
import sys
import csv
import datetime as dt
import numpy as np
import pyvisa
import tkinter
from tkinter import filedialog

VISA_SERIAL_NUMBER = "04611761"

ser = serial.Serial()
ser.port = "COM3" # COM3 on test computer, COM15 on Maxwell's ThinkPad laptop
ser.baudrate = 9600
ser.bytesize = serial.EIGHTBITS    #number of bits per bytes
ser.parity = serial.PARITY_NONE    #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE #number of stop bits
ser.timeout = 1                    #non-block read
ser.xonxoff = False                #disable software flow control
ser.rtscts = False                 #disable hardware (RTS/CTS) flow control
ser.dsrdtr = False                 #disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2               #timeout for write

delay_time = 0.1

tkinter.Tk().withdraw()
path = "C:\\Users\\Maxwell\\Desktop\\"
# print("Please select the directory to output data to:")
# path = filedialog.askdirectory()

# Connect to Keithley multimeter
rm = pyvisa.ResourceManager()
print("Listing available VISA resources below:")
print(rm.list_resources())
try:
    inst = rm.open_resource('USB0::0x05E6::0x6500::' + VISA_SERIAL_NUMBER + '::INSTR')
    print("Connected to VISA multimeter!")
except Exception as e:
    print(f"VISA connection error: {e}")
    sys.exit(0)

# List serial ports
print("\nListing available serial ports below:")
ports = serial.tools.list_ports.comports()
list_of_ports = []
for port, desc, hwid in sorted(ports):
    list_of_ports.append(str(port))
    print("{}: {} [{}]".format(port, desc, hwid))

# Query user for the Arduino COM port, will run until valid state given
# Can comment out this section if running on one computer
port = ""
while True:
    try:
        port = input("Please select the Arduino COM port COM[x]: ").upper()
    except ValueError:
        print("Sorry, please select a valid port COM[x]")
        continue
    if (port not in list_of_ports):
        print("Sorry, please select a valid port COM[x]")
        continue
    else:
        break
ser.port = port

try:
    ser.open()
    print("Connected to Arduino!")
except Exception as e:
    print(f"Error opening serial port: {e}")
    sys.exit(0);

suffix = input("\nPlease enter the name/variant of this board: ")

# states can be "CAP", "CONT", or "RESET"
# Query user for the test mode to run, will run until valid state given
states = ["CAP", "CONT", "RESET"]
while True:
    try:
        state = input("Please select a test: 'CAP', 'CONT', or 'RESET': ").upper()
    except ValueError:
        print("Sorry, please select a valid test")
        continue
    if (state not in states):
        print("Sorry, please select a valid test")
        continue
    else:
        break
delay_time = 0.1

'''
Arduino states are below:
States:
the reason we're using these names is because we're limited to one character + can't use the letters 'A' - 'F'.
- 'O' for continuity check mode
- 'P' for capacitance check mode
- 'S' for reset sweep mode
- 'R' for writing to the row muxes
- 'L' for writing to the column muxes
- 'T' for writing to the reset muxes
'''

full_path = path + 'meas_output_' + suffix + "_" + state.lower() + '.csv'
with open(full_path, 'w', newline = '') as file:
    if (state == "CAP"):
        writer = csv.writer(file)
        writer.writerow([suffix + " -- " + state, dt.datetime.now()])
        writer.writerow(["S/N", "Row Index", "Column Index", "Cap Off Measurement", "Cap On Measurement", "Calibrated Measurement"])                     
        inst.query('meas:cap?')                              # set Keithley mode to capacitance measurement
        time.sleep(delay_time)
        for row in range(0, 4): # CHANGE BACK TO 16, set to 4 for troubleshooting
            ser.write(b'R')                                  # set mode to row write mode
            time.sleep(delay_time)
            ser.write(bytes(hex(row)[2:], 'utf-8'))          # write row index
            time.sleep(delay_time)
            ser.write(b'L')                                  # set mode to column write mode
            time.sleep(delay_time)
            for col in range(0, 4):  # CHANGE BACK TO 16, set to 4 for troubleshooting
                ser.write(b'Z')                              # set all mux enables to OFF to get dark reading
                time.sleep(delay_time)
                off_meas = float(inst.query('read?')[:-1])   # read mux off measurement
                time.sleep(1)   # TODO: see how small we can make this delay
                ser.write(b'P')                              # set mode to capacitance check mode
                time.sleep(delay_time)
                ser.write(b'L')                              # set mode to column write mode
                time.sleep(delay_time)
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(delay_time)
                on_meas = float(inst.query('read?')[:-1])    # read mux on measurement
                time.sleep(1)   # TODO: see how small we can make this delay
                writer.writerow([suffix, str(row), str(col), off_meas, on_meas, on_meas - off_meas])
                time.sleep(delay_time)
    elif (state == "CONT"): # this works as of 2024-07-02
        inst.query('meas:res?')                              # set Keithley mode to resistance measurement
        ser.write(b'O')                                      # set mode to continuity check
        time.sleep(delay_time)
        out_array = np.zeros((18, 17), dtype='U64')          # create string-typed numpy array
        out_array[1] = ["R" + str(i) for i in range(-1, 16)] # set rows of output array to be "R0"..."R15"
        for i in range(len(out_array)):
            out_array[i][0] = "C" + str(i-2)                 # set cols of output array to be "C0"..."C15"
        out_array[0][0] = "Continuity Test"
        out_array[0][1] = suffix
        out_array[0][2] = dt.datetime.now()
        out_array[1][0] = "Resistance (ohm)"
        for row in range(0, 4): # CHANGE BACK TO 16, set to 4 for troubleshooting
            ser.write(b'R')                                  # set mode to row write mode
            time.sleep(delay_time)
            ser.write(bytes(hex(row)[2:], 'utf-8'))          # write row index
            time.sleep(delay_time)
            ser.write(b'L')                                  # set mode to column write mode
            time.sleep(delay_time)
            for col in range(0, 4): # CHANGE BACK TO 16, set to 4 for troubleshooting
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(delay_time);
                val = inst.query('read?')[:-1]               # read resistance measurement
                out_array[row+2][col+1] = val
                time.sleep(1)   # TODO: see how small we can make this delay
        np.savetxt(full_path, out_array, delimiter=",", fmt="%s")
    elif (state == "RESET"): # this only sweeps the reset lines; no measurements taken
        ser.write(b'S')
        time.sleep(delay_time)
        ser.write(b'T')
        time.sleep(delay_time)
        for i in range(0, 16):
            ser.write(bytes(hex(i)[2:], 'utf-8'))
            time.sleep(delay_time)

print("\nDone! Results saved to: " + full_path)
time.sleep(delay_time)
ser.write(b'Z')