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
path = "C:\\Users\\Maxwell\\Desktop\\" # C:\Users\tacta\Desktop
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
port = "COM5" # COM3 hardcoded this as default value (on Maxwell's laptop) but can also prompt for the COM port

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

suffix = input("\nPlease enter the name/variant of this board: ")

# states can be "CAP_SENSOR", "CONT_ROW_TO_COL", "CONT_PZBIAS_TO_ROW", "CONT_PZBIAS_TO_COL", "CONT_SHIELD_TO_COL", or "RESET"
# Query user for the test mode to run, will loop until valid state given
states = ["CAP_SENSOR", "CONT_ROW_TO_COL", "CONT_PZBIAS_TO_ROW", "CONT_PZBIAS_TO_COL", 
          "CONT_SHIELD_TO_ROW", "CONT_SHIELD_TO_COL", "RESET_SWEEP"]
index = -1
while True:
    try:
        for i in range(0,len(states)):
            print("- " + str(i) + " for " + states[i])
        index = int(input("Please select a test: "))
    except ValueError:
        print("Sorry, please select a valid test between 0 and " + str(len(states)-1))
        continue
    if (index > len(states)-1 or index < 0):
        print("Sorry, please select a valid test between and " + str(len(states)-1))
        continue
    else:
        break
print("Running " + states[index] + " test\n")
date_time_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
part_name = date_time_now + '_meas_output_' + suffix + "_" + states[index].lower()
name = part_name + '.csv'
full_path = path + name
if (name in os.listdir(path)):
    print("Output file with this name already exists. Exiting in 5 seconds...")
    time.sleep(5)
    exit()

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

with open(full_path, 'w', newline = '') as file:
    if (states[index] == "CAP_SENSOR"):
        print("Connections:\n- Connect sensor to J2B ZIF conector" +
              "\n- If new flex, multimeter probe the LOOP1A/B and LOOP2A/B board testpoints for continuity" +
              "\n- Run row/column, row/PZBIAS, col/PZBIAS continuity tests and ensure all open circuit" +
              "\n- Switch the PZBIAS <--> SHIELD switch to OFF" +
              "\n- Connect one SMA to DuPont cable to COL" + 
              "\n- Connect red DMM lead to COL center/red, black DMM lead to COL outside/black")
        input("Press 'enter' when ready:\n")
        writer = csv.writer(file)
        writer.writerow([suffix, states[index], dt.datetime.now()])
        writer.writerow(["S/N", "Row Index", "Column Index", "Cap Off Measurement (F)", "Cap On Measurement (F)", "Calibrated Measurement (F)"])
        inst.query('meas:cap?')                              # set Keithley mode to capacitance measurement
        time.sleep(DELAY_TIME)
        inst.write('sens:cap:rang 1E-9')                     # limits cap range to the smallest possible value
        time.sleep(DELAY_TIME)
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        out_array = np.zeros((18, 17), dtype='U64')          # create string-typed numpy array
        out_array[1] = ["C" + str(i) for i in range(0, 17)]  # set cols of output array to be "C1"..."C16"
        for i in range(len(out_array)):
            out_array[len(out_array)-1-i][0] = "R" + str(i+1)# set rows of output array to be "R1"..."R16"
        out_array[0][0] = "Capacitance Test Column to PZBIAS"
        out_array[0][1] = suffix
        out_array[0][2] = dt.datetime.now()
        out_array[1][0] = "Calibrated Cap (pF)"
        for row in range(0, 16):
            for col in range(0, 16):
                ser.write(b'I')                              # "OFF" measurement" - continuity check mode disconnects the +15/-8V switches
                time.sleep(DELAY_TIME)
                ser.write(b'R')                              # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))      # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                              # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(DELAY_TIME)
                tft_off_meas = float(inst.query('read?')[:-1])   # read mux off measurement
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)        # TODO: see how small we can make this delay
                ser.write(b'P')                              # "ON" measurement - cap. check mode puts row switches in +15/-8V mode
                time.sleep(DELAY_TIME)
                ser.write(b'R')                              # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))      # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                              # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(DELAY_TIME)
                tft_on_meas = float(inst.query('read?')[:-1])    # read mux on measurement
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)        # TODO: see how small we can make this delay
                tft_cal_meas = tft_on_meas - tft_off_meas
                out_array[(16-row)+1][col+1] = tft_cal_meas*1e12
                writer.writerow([suffix, str(row+1), str(col+1), tft_off_meas, tft_on_meas, tft_cal_meas]) # appends to CSV with 1 index
                time.sleep(DELAY_TIME)
            printProgressBar(row + 1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
        np.savetxt(path + part_name + "_alt.csv", out_array, delimiter=",", fmt="%s")
    elif (states[index] == "CONT_ROW_TO_COL"): # 16x16 works as of 2024-07-08
        print("Connections:\n- Connect sensor to J2B ZIF conector" +
              "\n- If new flex, multimeter probe the LOOP1A/B and LOOP2A/B board testpoints for continuity" +
              "\n- Switch the PZBIAS <--> SHIELD switch to OFF" +
              "\n- Connect two SMA to DuPont cables, one to ROW, one to COL" + 
              "\n- Connect one DMM lead to ROW center/red, one DMM lead to COL center/red")
        input("Press 'enter' when ready:\n")
        writer = csv.writer(file)
        writer.writerow([suffix, states[index], dt.datetime.now()])
        writer.writerow(["S/N", "Row Index", "Column Index", "Row Res. to Col. (ohm)"])                     
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        inst.query('meas:res?')
        time.sleep(DELAY_TIME)
        inst.write('sens:res:rang 10E6')                     # set resistance measurement range to 10 MOhm for 0.7uA test current, per
                                                             # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf
        ser.write(b'O')                                      # set mode to continuity check
        time.sleep(DELAY_TIME)
        out_array = np.zeros((18, 17), dtype='U64')          # create string-typed numpy array
        out_array[1] = ["C" + str(i) for i in range(0, 17)]  # set cols of output array to be "C1"..."C16"
        for i in range(len(out_array)):
            out_array[len(out_array)-1-i][0] = "R" + str(i+1)# set rows of output array to be "R1"..."R16"
        out_array[0][0] = "Continuity Test Row to Column"
        out_array[0][1] = suffix
        out_array[0][2] = dt.datetime.now()
        out_array[1][0] = "Resistance (ohm)"
        num_shorts = 0
        for row in range(0, 16):
            ser.write(b'R')                                  # set mode to row write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(row)[2:], 'utf-8'))          # write row index
            time.sleep(DELAY_TIME)
            ser.write(b'L')                                  # set mode to column write mode
            time.sleep(DELAY_TIME)
            for col in range(0, 16):
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(DELAY_TIME)
                val = float(inst.query('read?')[:-1])               # read resistance measurement
                out_array[(16-row)+1][col+1] = val
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)   # TODO: see how small we can make this delay
                if (val < RES_SHORT_THRESHOLD_ROWCOL):
                    num_shorts += 1
                writer.writerow([suffix, str(row+1), str(col+1), val])
            printProgressBar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
        np.savetxt(path + part_name + "_alt.csv", out_array, delimiter=",", fmt="%s")
        print("There were " + str(num_shorts) + " row/col short(s) in array " + suffix)
    elif (states[index] == "CONT_PZBIAS_TO_ROW"):
        print("Connections:\n- Connect sensor to J2B ZIF conector" +
              "\n- If new flex, multimeter probe the LOOP1A/B and LOOP2A/B board testpoints for continuity" +
              "\n- Switch the PZBIAS <--> SHIELD switch to OFF" +
              "\n- Connect two SMA to DuPont cables, one to ROW, one to COL" + 
              "\n- Connect one DMM lead to ROW center/red, one DMM lead to COL outside/black")
        input("Press 'enter' when ready:\n")
        writer = csv.writer(file)
        writer.writerow([suffix, states[index], dt.datetime.now()])
        writer.writerow(["S/N", "Row Index", "Row Res. to PZBIAS (ohm)"])
        inst.query('meas:res?')                              # set Keithley mode to resistance measurement
        time.sleep(DELAY_TIME)
        inst.write('sens:res:rang 10E6')                     # set resistance measurement range to 10 MOhm for 0.7uA test current, per
                                                             # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf        
        ser.write(b'O')                                      # set mode to continuity check mode
        time.sleep(DELAY_TIME)
        ser.write(b'R')                                      # set mode to row write mode
        time.sleep(DELAY_TIME)
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        num_shorts = 0
        for row in range(0, 16):
            ser.write(bytes(hex(row)[2:], 'utf-8'))            # write the row address to the tester
            time.sleep(DELAY_TIME)
            val = float(inst.query('read?')[:-1])            # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([suffix, str(row+1), val])       # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
            printProgressBar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
        print("There were " + str(num_shorts) + " row/PZBIAS short(s) in array " + suffix)
    elif (states[index] == "CONT_PZBIAS_TO_COL"):
        print("Connections:\n- Connect sensor to J2B ZIF conector" +
              "\n- If new flex, multimeter probe the LOOP1A/B and LOOP2A/B board testpoints for continuity" +
              "\n- Switch the PZBIAS <--> SHIELD switch to OFF" +
              "\n- Connect one SMA to DuPont cable to COL" + 
              "\n- Connect one DMM lead to COL center/red, one DMM lead to COL outside/black")
        input("Press 'enter' when ready:\n")
        writer = csv.writer(file)
        writer.writerow([suffix, states[index], dt.datetime.now()])
        writer.writerow(["S/N", "Col Index", "Col Res. to PZBIAS (ohm)"])
        inst.query('meas:res?')                              # set Keithley mode to resistance measurement
        time.sleep(DELAY_TIME)
        inst.write('sens:res:rang 10E6')                     # set resistance measurement range to 10 MOhm for 0.7uA test current, per
                                                             # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf        
        ser.write(b'O')                                      # set mode to continuity check mode
        time.sleep(DELAY_TIME)
        ser.write(b'L')                                      # set mode to column write mode
        time.sleep(DELAY_TIME)
        printProgressBar(0, 16, suffix = "Col 0/16", length = 16)
        num_shorts = 0
        for col in range(0, 16):
            ser.write(bytes(hex(col)[2:], 'utf-8'))            # write the column address to the tester
            time.sleep(DELAY_TIME)
            val = float(inst.query('read?')[:-1])            # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([suffix, str(col+1), val])       # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
            printProgressBar(col+1, 16, suffix = "Col " + str(col+1) + "/16", length = 16)
        print("There were " + str(num_shorts) + " col/PZBIAS short(s) in array " + suffix)
    elif (states[index] == "CONT_SHIELD_TO_ROW"):
        print("Connections:\n- Connect sensor to J2B ZIF conector" +
              "\n- Run CONT_PZBIAS_TO_ROW test, and note any columns shorted to PZBIAS if any" +
              "\n- Switch the PZBIAS <--> SHIELD switch to ON" +
              "\n- Connect two SMA to DuPont cables, one to ROW, one to COL" + 
              "\n- Connect one DMM lead to ROW center/red, one DMM lead to COL outside/black"
              "\n- After the test, switch the PZBIAS <--> SHIELD switch to OFF")
        input("Press 'enter' when ready:\n")
        writer = csv.writer(file)
        writer.writerow([suffix, states[index], dt.datetime.now()])
        writer.writerow(["S/N", "Col Index", "Row Res. to SHIELD (ohm)"])
        inst.query('meas:res?')                              # set Keithley mode to resistance measurement
        time.sleep(DELAY_TIME)
        inst.write('sens:res:rang 10E6')                     # set resistance measurement range to 10 MOhm for 0.7uA test current, per
                                                             # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf        
        ser.write(b'O')                                      # set mode to continuity check mode
        time.sleep(DELAY_TIME)
        ser.write(b'R')                                      # set mode to column write mode
        time.sleep(DELAY_TIME)
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        num_shorts = 0
        for row in range(0, 16):
            ser.write(bytes(hex(row)[2:], 'utf-8'))            # write the column address to the tester
            time.sleep(DELAY_TIME)
            val = float(inst.query('read?')[:-1])            # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([suffix, str(row+1), val])       # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
            printProgressBar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
        print("There were " + str(num_shorts) + " row/SHIELD short(s) in array " + suffix)
    elif (states[index] == "CONT_SHIELD_TO_COL"):
        print("Connections:\n- Connect sensor to J2B ZIF conector" +
              "\n- Run CONT_PZBIAS_TO_COL test, and note any columns shorted to PZBIAS if any" +
              "\n- Switch the PZBIAS <--> SHIELD switch to ON" +
              "\n- Connect one SMA to DuPont cable to COL" +
              "\n- Connect one DMM lead to COL center/red, one DMM lead to COL outside/black" +
              "\n- After the test, switch the PZBIAS <--> SHIELD switch to OFF")
        input("Press 'enter' when ready:\n")
        writer = csv.writer(file)
        writer.writerow([suffix, states[index], dt.datetime.now()])
        writer.writerow(["S/N", "Col Index", "Col Res. to SHIELD (ohm)"])
        inst.query('meas:res?')                              # set Keithley mode to resistance measurement
        time.sleep(DELAY_TIME)
        inst.write('sens:res:rang 10E6')                     # set resistance measurement range to 10 MOhm for 0.7uA test current, per
                                                             # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf        
        ser.write(b'O')                                      # set mode to continuity check mode
        time.sleep(DELAY_TIME)
        ser.write(b'L')                                      # set mode to column write mode
        time.sleep(DELAY_TIME)
        printProgressBar(0, 16, suffix = "Col 0/16", length = 16)
        num_shorts = 0
        for col in range(0, 16):
            ser.write(bytes(hex(col)[2:], 'utf-8'))            # write the column address to the tester
            time.sleep(DELAY_TIME)
            val = float(inst.query('read?')[:-1])            # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([suffix, str(col+1), val])       # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
            printProgressBar(col+1, 16, suffix = "Col " + str(col+1) + "/16", length = 16)
        print("There were " + str(num_shorts) + " col/SHIELD short(s) in array " + suffix)
    elif (states[index] == "RESET_SWEEP"): # this only sweeps the reset lines; no measurements taken. This writes an empty CSV.
        ser.write(b'S')
        time.sleep(DELAY_TIME)
        ser.write(b'T')
        time.sleep(DELAY_TIME)
        printProgressBar(0, 16, suffix = "Reset 0/16", length = 16)
        for i in range(0, 16):
            ser.write(bytes(hex(i)[2:], 'utf-8'))
            time.sleep(DELAY_TIME)
            printProgressBar(i+1, 16, suffix = "Reset " + str(i+1) + "/16", length = 16)

print("\nDone! Results saved to: " + full_path)
time.sleep(DELAY_TEST_EQUIPMENT_TIME)
ser.write(b'Z')                                              # set all mux enables + mux channels to OFF