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

ONE INDEXED OUTPUT!
'''

import serial
import serial.tools.list_ports
import time
import os
import sys
import csv
import datetime as dt
import numpy as np
import pyvisa
import tkinter
from tkinter import filedialog

VISA_SERIAL_NUMBER = "04611761"

ser = serial.Serial()
ser.port = "COM3"
ser.baudrate = 115200
ser.bytesize = serial.EIGHTBITS    # number of bits per bytes
ser.parity = serial.PARITY_NONE    # set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE # number of stop bits
ser.timeout = 1                    # non-block read
ser.xonxoff = False                # disable software flow control
ser.rtscts = False                 # disable hardware (RTS/CTS) flow control
ser.dsrdtr = False                 # disable hardware (DSR/DTR) flow control
ser.write_timeout = None           # timeout for write -- changed from writeTimeout

DELAY_TIME = 0.05
DELAY_TEST_EQUIPMENT_TIME = 0.1
RES_SHORT_THRESHOLD_ROWCOL = 100e6        # any value below this is considered a short
RES_SHORT_THRESHOLD_RC_TO_PZBIAS = 100e6  # any value below this is considered a short

tkinter.Tk().withdraw()
#path = "G:\\Shared drives\\Engineering\\Projects\\Testing\\16x16_Array_E_Test\\Phase_1EFG_Array\\" # hardcoded this as default value, below lines (commented) can prompt for the path
path = "C:\\Users\\tacta\\Desktop\\" # C:\Users\tacta\Desktop
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

if (len(list_of_ports)) == 0:
    print("ERROR: No serial ports/Arduinos detected. Exiting in 5 seconds...")
    time.sleep(5)
    exit()

# Query user for the Arduino COM port, will run until valid state given
# Can comment out this section if running on one computer
port = "COM3" # COM3 hardcoded this as default value (on Maxwell's laptop) but can also prompt for the COM port

'''
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

'''
ser.port = port

try:
    ser.open()
    print("Connected to Arduino!")
except Exception as e:
    print(f"Error opening serial port: {e}")
    sys.exit(0)

# suffix = input("\nPlease enter the name/variant of this board: ")

# states can be "CAP_SENSOR", "CONT_ROW_TO_COL", "CONT_PZBIAS_TO_ROW", "CONT_PZBIAS_TO_COL", "CONT_SHIELD_TO_COL", or "RESET"
# Query user for the test mode to run, will loop until valid state given


def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    Source: https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

'''
Arduino states are below:
States:
the reason we're using these names is because we're limited to one character + can't use the letters 'A' - 'F'.
- 'O' for continuity check mode
- 'P' for capacitance check mode
- 'S' for reset sweep mode
- 'Z' for all off
- 'I' for binary counter disable mode
- 'R' for writing to the row muxes
- 'L' for writing to the column muxes
- 'T' for writing to the reset muxes
'''
print("Connections:\n- Connect sensor to J2B ZIF conector" +
      "\n- If new flex, multimeter probe the LOOP1A/B and LOOP2A/B board testpoints for continuity" +
      "\n- Switch the PZBIAS <--> SHIELD switch to OFF" +
      "\n- Connect one SMA to DuPont cable to COL" + 
      "\n- Connect one DMM lead to COL center/red, one DMM lead to COL outside/black")
input("Press 'enter' when ready:\n")

states = ["CAP_SENSOR", "CONT_ROW_TO_COL", "CONT_PZBIAS_TO_ROW", "CONT_PZBIAS_TO_COL", 
          "CONT_PZBIAS_TO_COL_TFTS_ON", "CONT_SHIELD_TO_ROW", "CONT_SHIELD_TO_COL", "RESET_SWEEP"]
index = 6

num_cycs = 50
delay_btwn_tests = 5 # seconds

inst.query('meas:res?')
time.sleep(DELAY_TIME)
inst.write('sens:res:rang 10E6')                     # set resistance measurement range to 10 MOhm for 0.7uA test current, per
                                                     # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf
time.sleep(DELAY_TIME)
                                                             
for inc in range(1, num_cycs+1):
    suffix = "burnin_S38_" + str(inc)
    date_time_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    part_name = date_time_now + '_meas_output_' + suffix + "_" + states[index]
    name = part_name + '.csv'
    full_path = path + name
    print(date_time_now)
    with open(full_path, 'w', newline = '') as file:
        writer = csv.writer(file)
        writer.writerow([suffix, states[index], dt.datetime.now()])
        writer.writerow(["S/N", "Col Index", "Col. Res. to SHIELD (ohm)"])
        inst.query('meas:res?')                              # set Keithley mode to resistance measurement
        time.sleep(DELAY_TIME)
        inst.write('sens:res:rang 10E6')                     # set resistance measurement range to 10 MOhm for 0.7uA test current, per
                                                             # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf        
        time.sleep(DELAY_TIME)
        printProgressBar(0, 16, suffix = "Col 0/16", length = 16)
        num_shorts = 0
        for col in range(0, 16):
            ser.write(b'Z')                                      # set row switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'L')                                      # set mode to column write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(col)[2:], 'utf-8'))            # write the column address to the tester
            time.sleep(DELAY_TIME)
            ser.write(b'O')                                      # set mode to continuity check mode
            time.sleep(DELAY_TIME)
            val = float(inst.query('read?')[:-1])            # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([suffix, str(col+1), val])       # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
            printProgressBar(col+1, 16, suffix = "Col " + str(col+1) + "/16", length = 16)
        print("There were " + str(num_shorts) + " row/col short(s) in array " + suffix + " cycle " + str(inc) + "/" + str(num_cycs))
        
        #make sure to include below lines of code in this code block
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
        ser.write(b'Z')                                              # set all mux enables + mux channels to OFF
        print("Waiting " + str(delay_btwn_tests) + " seconds until next test...\n")
        time.sleep(delay_btwn_tests)
print("Done!")