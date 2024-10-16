'''
This program performs cap, continuity, or reset sweeps

Hardware requirements:
- Keithley DMM6500 benchtop multimeter (our current unit's S/N is 04611761)
- BK Precision 9141-GPIB benchtop power supply
- 16x16 Array, with or without flex attached
  * For arrays without flex attached, probe station aligner that joins flex to sensor
- Assembled 00013+00014 tester boards
- 00013 secondary board with SMA cables + jumper wires soldered to it
- Arduino MEGA 2560 R3
  * 10x2pin socket - socket ribbon cable from Arduino P36/37 to GND
  * Male header pins, double length (Amazon B077N29TP5)
  * 14x plug to socket ribbon cable to secondary board
  
  *******************************************************************************************************
  *** RUNNING THE AUTOMATED_ARDUINO_CAP_CONT_CHECKER_16X16_NO_ACK CODE THAT DOES NOT REPLY VIA SERIAL ***
  *******************************************************************************************************

- 2x SMA to DuPont loose plug cable
- 1x BNC to minigrabber cable
- 1x BNC to dual banana plug

Software requirements
- Python 3.x
  * pyvisa library (INSTALL)
    - NI-VISA library downloaded from NI website
  * numpy library
  * serial library
  * csv library
  * datetime

ONE INDEXED OUTPUT!
'''

import serial
import serial.tools.list_ports
import csv
import glob
import keyboard
import os
import os.path
import pyvisa
import sys
import time
import tkinter
import datetime as dt
import numpy as np
from collections import defaultdict
from pygame import mixer
from tkinter import filedialog

# To install Google Python libraries, run this command:
# pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http

# Root path where test results are saved.
# Inside has the following folders: "Sensor Modules", "Sensor Arrays", and "Backplanes"
PATH_BASE = "G:\\Shared drives\\Sensing\\Testing\\"

USING_USB_PSU = True

# TODO: load COM port, DMM serial number, and PSU serial number from config file, for scalability
COM_PORT_DEFAULT = "COM3" # default hardcoded value, ok to change from setup to setup
DMM_SERIAL_STRING  = "USB0::0x05E6::0x6500::04611761::INSTR"
PSU_SERIAL_STRING  = "USB0::0x3121::0x0002::583H23104::INSTR"
PSU_DELAY_TIME = 3 # seconds

DELAY_TIME_SERIAL = 0.02 # 0.05
DELAY_TIME_INST = 0 # 0.1

# default multimeter ranges
RES_RANGE_DEFAULT = '100E6'
RES_RANGE_LOOPBACKS = '10E3'
CAP_RANGE_DEFAULT = '1E-9'

# Arrays can be 1T or 3T,
# and they can be "backplanes", "sensor arrays", or "sensor modules".
ARRAY_TFT_TYPES = [1, 3]
ARRAY_ASSY_TYPES = {
    1: "Backplanes",
    2: "Sensor Arrays",
    3: "Sensor Modules"
}

RES_SHORT_THRESHOLD_ROWCOL = 100e6        # any value below this is considered a short
RES_SHORT_THRESHOLD_RC_TO_PZBIAS = 100e6  # any value below this is considered a short

# Define dictionary linking sensor types to their acceptable capacitance range
# Sensor type (key) is a string (e.g. "T1")
# Acceptable capacitance range (value) is a tuple of (low, high) in pF
CAP_THRESHOLD_MIN_DEFAULT = 5 # pF
CAP_THRESHOLD_MAX_DEFAULT = 50
CAP_THRESHOLD_VALS = defaultdict(lambda: (CAP_THRESHOLD_MIN_DEFAULT, CAP_THRESHOLD_MAX_DEFAULT))
CAP_THRESHOLD_VALS["backplane"] = (-2, 2) # bare backplane without sensors

# Define max number of shorts are permitted acceptable for an array
MAX_PASS_CONT_COUNT_TWO_DIM = 0
MAX_PASS_CONT_COUNT_ONE_DIM = 0
MIN_PASS_CAP_COUNT  = 255

# Define max number of out-of-range capacitance sensors are permitted acceptable for an array

# Google Sheets integration
# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1U0fXZTtxtd9mQf37cgzLy9CH4UH5T_lKMpFjCBX9qVs"
ID_SHEET_NAME = "Sensor Modules"
OUT_SHEET_NAME = "Tester Output"

'''
Dictionary with 1-character commands to set secondary mux board into the correct mode for the measurement
'''
CAP_FN_DICT = {
    "CAP_COL_TO_PZBIAS": b'W',
    "CAP_COL_TO_SHIELD": b'Y'
}

'''
For two dimensional continuity checks (e.g. row to column, rst to column),
dictionary with 1-character commands to set board into appropriate state, using tuples
First element of tuple sets the secondary mux into the appropriate state
Second element of tuple sets the primary mux into the first dimension (e.g. row) writing mode
Third element of tuple sets the primary mux into the second dimension (e.g. col) writing mode
'''
CONT_DICT_TWO_DIM = {
    "CONT_ROW_TO_COL": (b'U', b'R', b'L'),
    "CONT_RST_TO_COL": (b'Q', b'T', b'L')
}

'''
For one dimensional continuity checks (e.g. row to shield, col to PZBIAS, etc.),
dictionary with 1-character commands to set board into appropriate state, using tuples
First element of tuple is command for secondary mux,
second element of tuple is command for row/col/reset write mode
'''
CONT_DICT_ONE_DIM = {
    "CONT_ROW_TO_PZBIAS": (b'V', b'R'),
    "CONT_ROW_TO_SHIELD": (b'X', b'R'),
    "CONT_COL_TO_PZBIAS": (b'W', b'L'),
    "CONT_COL_TO_SHIELD": (b'Y', b'L'),
    "CONT_COL_TO_VDD"   : (b'!', b'L'),
    "CONT_COL_TO_VRST"  : (b'$', b'L'),
    "CONT_RST_TO_PZBIAS": (b'M', b'T'),
    "CONT_RST_TO_SHIELD": (b'N', b'T')
}

'''
For node continuity checks (e.g. vdd to shield),
dictionary with 1-character commands to set secondary mux board into appropriate state
'''
CONT_DICT_NODE = {
    "CONT_VDD_TO_SHIELD":    b'@',
    "CONT_VRST_TO_SHIELD":   b'%',
    "CONT_VDD_TO_PZBIAS":    b'#',
    "CONT_VRST_TO_PZBIAS":   b'^',
    "CONT_SHIELD_TO_PZBIAS": b'('
}

'''
Dictionary used to store results from tests
Results are uploaded to Google Sheets in this order
Tests that were not run will be uploaded to GSheets as blank.
'''
output_payload_gsheets_dict = {
    "Timestamp"           : "",
    "Serial Number"       : "",
    "Array Type"          : "",
    "Array Module Stage"  : "",
    "TFT Type"            : "",
    "Loopback One (ohm)"  : "",
    "Loopback Two (ohm)"  : "",
    "Cap Col to PZBIAS"   : "",
    "Col to PZBIAS with TFT's ON" : "",
    "Row to Col"    : "",
    "Rst to Col"    : "",
    "Row to PZBIAS" : "",
    "Row to SHIELD" : "",
    "Col to PZBIAS" : "",
    "Col to SHIELD" : "",
    "Col to Vdd"    : "",
    "Col to Vrst"   : "",
    "Rst to SHIELD" : "",
    "Rst to PZBIAS" : "",
    "SHIELD to PZBIAS"  : "",
    "Vdd to SHIELD" : "",
    "Vdd to PZBIAS" : "",
    "Vrst to SHIELD": "",
    "Vrst to PZBIAS": ""
}

'''
Helper function that checks if a newly initialized hardware object (e.g. serial, multimeter, PSU) is null
If object is null, exit program. If not, return the object.
Parameter:
    object: A function call (e.g. init_serial())
Return:
    the created object, or exits program if function returns null
'''
def init_helper(object):
    if (object == None):
        print("ERROR: COULD NOT INITIALIZE OBJECT! Exiting...")
        time.sleep(5)
        sys.exit(0)
    return object

'''
Initializes the Arduino serial port
Parameters:
    com_port: COM port (Windows) as a string, 'COM[x]'
Returns:
    PySerial object (if properly initialized), null object if not initialized
'''
def init_serial(com_port=""):
    ser = serial.Serial()
    ser.port = com_port
    ser.baudrate = 115200
    ser.bytesize = serial.EIGHTBITS #number of bits per bytes
    ser.parity = serial.PARITY_NONE #set parity check: no parity
    ser.stopbits = serial.STOPBITS_ONE #number of stop bits
    ser.timeout = 1            #non-block read
    ser.xonxoff = False     #disable software flow control
    ser.rtscts = False     #disable hardware (RTS/CTS) flow control
    ser.dsrdtr = False       #disable hardware (DSR/DTR) flow control
    ser.writeTimeout = 2     #timeout for write
    if (com_port == ""):
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
        while True:
            try:
                port_in = input("Please select the Arduino COM port COM[x]: ").upper()
            except ValueError:
                print("Sorry, please select a valid port COM[x]")
                continue
            if (port_in not in list_of_ports):
                print("Sorry, please select a valid port COM[x]")
                continue
            else:
                break
        ser.port = port_in
    try:
        ser.open()
        print("Connected to Arduino on " + ser.port.upper() + "!")
        return ser
    except Exception as e:
        print("ERROR: couldn't open serial port...")
        return None

'''
Initializes the Keithley DMM6500 multimeter
Parameters: 
    rm: A PyVISA resource manager object (rm),
    dmm_id: String serial name, default: USB0::0x05E6::0x6500::04611761::INSTR
    res_range: Default resistance range '100e6'
    cap_range: Default capacitance range '10e-3
Returns:
    An initialized PyVISA object, or a null object if not initialized
TODO: implement equipment type check that quits if this address is not actually the right equipment
NOTE: remember to run 'dmm.close()' when done with the DMM
'''
def init_multimeter(rm, dmm_id=DMM_SERIAL_STRING, res_range=RES_RANGE_DEFAULT, cap_range=CAP_RANGE_DEFAULT):
    try:
        dmm = rm.open_resource(dmm_id)
        print("Connected to VISA multimeter!")
    except Exception as e:
        print("ERROR: couldn't connect to VISA multimeter...")
        return None
    # Have pyvisa handle line termination
    dmm.read_termination = '\n'
    # Clear buffer and status
    dmm.write('*CLS')
    # Set measurement ranges
    dmm.write('sens:res:rang ' + res_range) # sets resistance range to the default specified value
    dmm.write('sens:cap:rang ' + cap_range) # limits cap range to the smallest possible value
    dmm.write('sens:cap:aver:tcon rep') # sets cap averaging to repeating (vs. moving) -- see Keithley 2000 user manual
    dmm.write('sens:cap:aver:coun 10')  # sets averaging to 10 measurements per output
    dmm.write('sens:cap:aver on')       # enables cap averaging
    return dmm

'''
Initializes the BK power supply
Parameters: 
    rm: A PyVISA resource manager object (rm),
    psu_id: String serial name, default: USB0::0x05E6::0x6500::04611761::INSTR
Returns:
    An initialized PyVISA object, or a null object if not initialized
TODO: implement equipment type check that quits if this address is not actually the right equipment
NOTE: remember to run 'psu.close()' when done with the PSU
'''
def init_psu(rm, psu_id=PSU_SERIAL_STRING):
    try:
        psu = rm.open_resource(psu_id)
        print("Connected to VISA PSU!")
    except Exception as e:
        print("ERROR: couldn't connect to VISA power supply...")
        return None
    # Have pyvisa handle line termination
    psu.read_termination = '\n'
    # Clear buffer and status
    psu.write('*CLS')
    return psu

'''
Turns on the BK power supply
Parameters: 
    psu: A PyVISA object containing the initialized power supply
    psu:wait: The time to wait for the power supply to turn on
Returns:
    True if successfully turned PSU on, None if PSU not successfully turned on
'''
def set_psu_on(psu, psu_wait=PSU_DELAY_TIME):
    print("PSU turning on...")
    try:
        # set PSU voltage to 18V, current limits to 0.05A on (-) and 0.075A on (+)
        psu.write('INST:SEL 0')
        psu.write('APPL 18,0.05')
        psu.write('OUTP:STAT 1')
        psu.write('INST:SEL 1')
        psu.write('APPL 18,0.075')
        psu.write('OUTP:STAT 1')
        time.sleep(psu_wait)
        print("PSU on!")
        return True
    except Exception as e:
        print("ERROR: couldn't turn on VISA power supply...")
        return None

'''
Turns off the BK power supply
Parameters:
    psu: A PyVISA object containing the initialized power supply
    psu_wait: The time to wait for the power supply to turn off
Returns:
    True if successfully turned PSU off, False if PSU not successfully turned off
NOTE: remember to run 'psu.close()' when done with the PSU
'''
def set_psu_off(psu, psu_wait=PSU_DELAY_TIME):
    print("\nTurning PSU off...")
    try:
        psu.write('OUTP:ALL 0')
        time.sleep(psu_wait)
        print("PSU off!")
        return True
    except Exception as e:
        print("ERROR: couldn't turn off VISA power supply...")
        return None

'''
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
'''
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

'''
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
- 'U' for writing secondary board to "row/col" output
- 'V' for writing secondary board to "row/PZBIAS" output
- 'W' for writing secondary board to "col/PZBIAS" output
- 'X' for writing secondary board to "row/SHIELD" output
- 'Y' for writing secondary board to "col/SHIELD" output
- 'M' for writing secondary board to "rst/PZBIAS" output
- 'N' for writing secondary board to "rst/SHIELD" output
- 'Q' for writing secondary board to "rst/col" output
- '!' for writing secondary board to "vdd/col" output
- '@' for writing secondary board to "vdd/SHIELD" output
- '#' for writing secondary board to "vdd/PZBIAS" output
- '$' for writing secondary board to "vrst/col" output
- '%' for writing secondary board to "vrst/SHIELD" output
- '^' for writing secondary board to "vrst/PZBIAS" output
- '(' for writing secondary board to "SHIELD/PZBIAS" output
'''

'''
Writes (or tries) specified data to the serial port.
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    byte: Data payload to send over serial
    delay: Amount of time to wait after writing serial command
Returns: None
'''
def serialWriteWithDelay(ser, byte, delay=DELAY_TIME_SERIAL):
    ser.write(byte)
    time.sleep(delay)

'''
Writes (or tries) specified data to the PyVISA instrument.
Parameters:
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    writeString: Data payload to send over VISA
    delay: Amount of time to wait after writing VISA command
Returns: None
'''
def instWriteWithDelay(inst, writeString, delay=DELAY_TIME_INST):
    inst.write(writeString)
    time.sleep(delay)

'''
Queries (or tries) the PyVISA instrument for data.
Parameters:
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    writeString: Data payload to send over 
    delay: Amount of time to wait after writing VISA command
Returns: None
'''
def instQueryWithDelay(inst, queryString, delay=DELAY_TIME_INST):
    val = inst.query(queryString)
    time.sleep(delay)
    return val

'''
Two-dimensional test measures capacitance between column and one other node 
specified in the 'test_mode_in' parameter (linked to the CAP_FN_DICT dictionary).
Test measures the difference between (row TFT on cap) - (row TFT off cap)
by first iterating through row TFT's and toggling them to +15V (on) or -8V (off).
Inside, it iterates through all the columns and measures capacitance between column[x]
and the specified node (e.g. PZBIAS)
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    path: Path to save output files to
    dut_name_raw: Raw name of the DUT (e.g. E2412-001-007-D2_T1)
    dut_stage_raw: Stage of assembly in plaintext (e.g. Post_Flex_Bond_ETest)
    test_mode_in: Test mode to use, one of the options in CAP_FN_DICT
    dut_type: If the device is a backplane, sensor array, or sensor module
    meas_range: Multimeter capacitance measurement range
    start_row: Row # to start iterating through (typically 0)
    start_col: Col # to start iterating through (typically 0)
    end_row: Row # to end iterating through (typically 16)
    end_col: Col # to end iterating through (typically 16)
Returns:
    Tuple, with following parameters:
        0 for success, -1 for failure or wrong parameter specified
        Output text (to be appended to summary file)
'''
def test_cap(ser, inst, path, dut_name_raw, dut_stage_raw, test_mode_in, dut_type,
             meas_range='1e-9', start_row=0, start_col=0, end_row=16, end_col=16):
    if (test_mode_in not in CAP_FN_DICT):
        print("ERROR: test mode not defined...")
        return (-1, "CAP TEST ERROR")
    test_name = test_mode_in
    dut_name_full = dut_name_raw + dut_stage_raw
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    dut_name_segmented = dut_name_raw.split("_")
    cap_bound_vals = CAP_THRESHOLD_VALS[""] # default cap range value
    if (len(dut_name_segmented) > 2):
        cap_bound_vals = CAP_THRESHOLD_VALS[dut_name_segmented[1]] # if this sensor type isn't in the array, uses default value
    if (dut_type == "Backplanes"):
        cap_bound_vals = CAP_THRESHOLD_VALS["backplane"]
    num_below_threshold = 0
    num_in_threshold = 0
    num_above_threshold = 0

    with open(path + datetime_now + "_" + dut_name_full + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Row Index", "Column Index", "Cap Off Measurement (F)", "Cap On Measurement (F)", "Calibrated Measurement (F)"])
        instWriteWithDelay(inst, 'sens:cap:rang ' + meas_range)
        instQueryWithDelay(inst, 'meas:cap?')
        print("Sensor " + test_name + " Check Running...")
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        out_array_delta = np.zeros((18, 17), dtype='U64')          # create string-typed numpy array
        out_array_delta[1] = ["C" + str(i) for i in range(0, 17)]  # set cols of output array to be "C1"..."C16"
        for i in range(len(out_array_delta)):
            out_array_delta[len(out_array_delta)-1-i][0] = "R" + str(i+1)# set rows of output array to be "R1"..."R16"

        out_array_on = np.zeros((18, 17), dtype='U64')          # create string-typed numpy array
        out_array_on[1] = ["C" + str(i) for i in range(0, 17)]  # set cols of output array to be "C1"..."C16"
        for i in range(len(out_array_on)):
            out_array_on[len(out_array_on)-1-i][0] = "R" + str(i+1)# set rows of output array to be "R1"..."R16"

        out_array_delta[1][0] = "Cap TFT On - Cap TFT Off (pF)"
        out_array_on[1][0] = "Cap TFT On (pF)"

        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                serialWriteWithDelay(ser, b'Z')                         # sets all mux switches to high-Z mode
                serialWriteWithDelay(ser, CAP_FN_DICT[test_name])       # pre-sets the secondary muxes to the right state for cap measurement
                serialWriteWithDelay(ser, b'R')                         # sets primary mux to row write mode
                serialWriteWithDelay(ser, bytes(hex(row)[2:], 'utf-8')) # sets row address
                serialWriteWithDelay(ser, b'L')                         # sets primary mux to column write mode
                serialWriteWithDelay(ser, bytes(hex(col)[2:], 'utf-8')) # sets column address
                serialWriteWithDelay(ser, b'I')                         # sets primary row mux to "binary counter disable mode", which sets all TFT's off (to -8V)

                tft_off_meas = float(instQueryWithDelay(inst, 'meas:cap?'))

                serialWriteWithDelay(ser, b'Z')                         # sets all mux switches to high-Z mode
                serialWriteWithDelay(ser, CAP_FN_DICT[test_name])       # pre-sets the secondary muxes to the right state for cap measurement
                serialWriteWithDelay(ser, b'R')                         # sets primary mux to row write mode
                serialWriteWithDelay(ser, bytes(hex(row)[2:], 'utf-8')) # sets row address
                serialWriteWithDelay(ser, b'L')                         # sets primary mux to column write mode
                serialWriteWithDelay(ser, bytes(hex(col)[2:], 'utf-8')) # sets column address
                serialWriteWithDelay(ser, b'P')                         # sets primary row mux to capacitance check mode

                tft_on_meas = float(instQueryWithDelay(inst, 'meas:cap?'))
                tft_cal_meas = tft_on_meas - tft_off_meas
                if (tft_cal_meas*1e12 < cap_bound_vals[0]):
                    num_below_threshold += 1
                elif (tft_cal_meas*1e12 > cap_bound_vals[1]):
                    num_above_threshold += 1
                else:
                    num_in_threshold += 1
                out_array_delta[(16-row)+1][col+1] = tft_cal_meas*1e12
                out_array_on[(16-row)+1][col+1] = tft_on_meas*1e12
                writer.writerow([str(row+1), str(col+1), tft_off_meas, tft_on_meas, tft_cal_meas]) # appends to CSV with 1 index
            printProgressBar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    serialWriteWithDelay(ser, b'Z')
    out_array_delta = np.delete(out_array_delta, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name_full + "_" + test_name.lower() + "_alt_delta.csv", out_array_delta, delimiter=",", fmt="%s")
    out_array_on = np.delete(out_array_on, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name_full + "_" + test_name.lower() + "_alt_on.csv", out_array_on, delimiter=",", fmt="%s")
    out_text = "Ran " + test_name + " test w/ " + str(meas_range) + " F range"
    out_text += "\nNo. of sensors inside bounds: " + str(num_in_threshold)
    out_text += "\nNo. of sensors below lower threshold of " + str(cap_bound_vals[0]) + "pF: " + str(num_below_threshold)
    out_text += "\nNo. of sensors above upper threshold of " + str(cap_bound_vals[1]) + "pF: " + str(num_above_threshold) + "\n"
    print("\n" + out_text)
    return(0, out_text + "\n")

'''
Two-dimensional test that measures continuity at every intersection, e.g. row to column.
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    path: Path to save output files to
    dut_name: Full name of device + stage of test
    test_id: Test mode to run, one of the ones specified in CONT_DICT_TWO_DIM
    start_dim1: Dim1 (e.g. row) # to start iterating through (typically 0)
    start_dim2: Dim2 (e.g. col) # to start iterating through (typically 0)
    end_dim1: Dim1 (e.g. row) # to end iterating through (typically 16)
    end_dim2: Dim2 (e.g. col) # to end iterating through (typically 16)
Returns:
    Tuple, with following parameters:
        Total number of shorts detected
        Output text (to be appended to summary file)
'''
def test_cont_two_dim(ser, inst, path, dut_name, test_id, start_dim1=0, start_dim2=0, end_dim1=16, end_dim2=16):
    test_name = test_id.upper()
    if (test_name not in CONT_DICT_TWO_DIM):
        out_text = "ERROR: 2D node resistance check " + test_name + " not valid...\n"
        print(out_text)
        return (-1, out_text)
    dim1_name = test_name.split('_')[1].capitalize()
    dim2_name = test_name.split('_')[3].capitalize()
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    out_array = np.zeros((18, 17), dtype='U64')              # create string-typed numpy array
    out_array[1] = [dim2_name + str(i) for i in range(0, 17)]  # set cols of output array to be "dim2_1...dim2_16"
    for i in range(len(out_array)):
        out_array[len(out_array)-1-i][0] = dim1_name + str(i+1)# set rows of output array to be "dim1_1...dim1_16"
    out_array[1][0] = "Resistance (ohm)"
    num_shorts = 0
    out_text = ""
    inst.query('meas:res?')
    time.sleep(DELAY_TIME_SERIAL)
    out_text += "Sensor " + dim1_name + " to " + dim2_name + " Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([dim1_name + " Index", dim2_name + " Index", dim1_name + " Res. to " + dim2_name + " (ohm)"])
        printProgressBar(0, 16, suffix = dim1_name + " 0/16", length = 16)
        time.sleep(DELAY_TIME_SERIAL)
        for dim1_cnt in range(start_dim1, end_dim1):
            for dim2_cnt in range(start_dim2, end_dim2):
                serialWriteWithDelay(ser, b'Z')                              # set row switches to high-Z and disable muxes
                serialWriteWithDelay(ser, CONT_DICT_TWO_DIM[test_name][0])   # set secondary mux to specified input mode
                serialWriteWithDelay(ser, CONT_DICT_TWO_DIM[test_name][1])   # set mode to dim1 write mode
                serialWriteWithDelay(ser, bytes(hex(dim1_cnt)[2:], 'utf-8')) # write dim1 index
                serialWriteWithDelay(ser, CONT_DICT_TWO_DIM[test_name][2])   # set mode to dim2 write mode
                serialWriteWithDelay(ser, bytes(hex(dim2_cnt)[2:], 'utf-8')) # write dim2 index
                serialWriteWithDelay(ser, b'O')                              # set mode to continuity check
                val = float(instQueryWithDelay(inst, 'meas:res?'))           # read resistance measurement
                out_array[(16-dim1_cnt)+1][dim2_cnt+1] = val
                if (val < RES_SHORT_THRESHOLD_ROWCOL):
                    num_shorts += 1
                writer.writerow([str(dim1_cnt+1), str(dim2_cnt+1), val])
            printProgressBar(dim1_cnt+1, 16, suffix = dim1_name + " " + str(dim1_cnt+1) + "/16", length = 16)
    serialWriteWithDelay(ser, b'Z')                                          # set all mux enables + mux channels to OFF
    out_array = np.delete(out_array, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt.csv", out_array, delimiter=",", fmt="%s")
    num_shorts_text = "There were " + str(num_shorts) + " " + dim1_name + "/" + dim2_name + " short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    out_array = np.delete(out_array, (0), axis=1)
    out_array = out_array[1:]
    if (num_shorts > 0):
        for dim1_cnt in range(out_array.shape[0]):
            for dim2_cnt in range(out_array.shape[1]):
                if (float(out_array[dim1_cnt][dim2_cnt]) > RES_SHORT_THRESHOLD_ROWCOL):
                    print(".", end="")
                    out_text += "."
                else:
                    print("X", end="")
                    out_text += "X"
            print("")
            out_text += "\n"
    print("")
    return(num_shorts, out_text)

'''
One-dimensional test that measures continuity at intersections to a node, e.g. column to PZBIAS
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    path: Path to save output files to
    dut_name: Full name of device + stage of test
    test_id: Test mode to run, one of the ones specified in CONT_DICT_ONE_DIM
    start_ind: Dim1 (e.g. col) # to start iterating through (typically 0)
    end_ind: Dim1 (e.g. col) # to end iterating through (typically 16)
Returns:
    Tuple, with following parameters:
        Total number of shorts detected
        Output text (to be appended to summary file)
'''
def test_cont_one_dim(ser, inst, path, dut_name, test_id, start_ind=0, end_ind=16):
    test_name = test_id.upper()
    primary_mux_state = test_name.split("_")[1].capitalize()
    if (test_name not in CONT_DICT_ONE_DIM):
        out_text = "ERROR: 1D intersection resistance check " + test_name + " not valid...\n"
        print(out_text)
        return (-1, out_text)
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                              # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME_SERIAL)
    out_text += "Sensor " + test_name + " Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([primary_mux_state + " Index", test_name + " (ohm)"])
        printProgressBar(0, 16, suffix = primary_mux_state + " 0/16", length = 16)
        for ind in range(start_ind, end_ind):
            serialWriteWithDelay(ser, b'Z')                     # set row switches to high-Z and disable muxes
            serialWriteWithDelay(ser, CONT_DICT_ONE_DIM[test_name][0]) # set secondary mux to appropriate mode
            serialWriteWithDelay(ser, CONT_DICT_ONE_DIM[test_name][1]) # set write mode to appropriate
            serialWriteWithDelay(ser, bytes(hex(ind)[2:], 'utf-8'))    # write the row address to the tester
            serialWriteWithDelay(ser, b'O')                     # set mode to continuity check mode
            val = float(instQueryWithDelay(inst, 'meas:res?'))  # read resistance from the meter
            writer.writerow([str(ind+1), val])                  # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            printProgressBar(ind+1, 16, suffix = primary_mux_state + " " + str(ind+1) + "/16", length = 16)
    serialWriteWithDelay(ser, b'Z')                             # set all mux enables + mux channels to OFF
    num_shorts_text = test_name + " yielded " + str(num_shorts) + " short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

'''
Measures continuity at intersections between two nodes, e.g. PZBIAS to SHIELD
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    path: Path to save output files to
    dut_name: Full name of device + stage of test
    test_id: Test mode to run, one of the ones specified in CONT_DICT_NODE
Returns:
    Tuple, with following parameters:
        String "PASS" if no short, "FAIL" if shorted
        Output text (to be appended to summary file)
'''
def test_cont_node(ser, inst, path, dut_name, test_id):
    test_name = test_id.upper()
    if (test_name not in CONT_DICT_NODE):
        out_text = "ERROR: 1D Node resistance check " + test_name + " not valid...\n"
        print(out_text)
        return (-1, out_text)
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out_text = "Sensor " + test_name + " Continuity Detection Running..."
    out_text += "\n"
    val = 0
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        file.write(test_name.lower() + " (ohms)\n")
        serialWriteWithDelay(ser, b'Z')                      # set rst switches to high-Z and disable muxes
        serialWriteWithDelay(ser, CONT_DICT_NODE[test_id])   # set secondary mux to mode specified in input
        serialWriteWithDelay(ser, b'O')                      # enable tester outputs
        val = float(instQueryWithDelay(inst, 'meas:res?'))   # read resistance from the meter
        file.write(str(val))
        out_text += f"{val:,}"  + " ohms"
        time.sleep(DELAY_TIME_INST)
        file.close()
    serialWriteWithDelay(ser, b'Z')                               # set rst switches to high-Z and disable muxes
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\n" + test_name + " does not have shorts\n"
        print(out_text)
        return("PASS", out_text)
    else:
        out_text += "\n" + test_name + " has shorts\n"
        print(out_text)
        return ("FAIL", out_text)

'''
Measures continuity between column and PZBIAS while toggling the row TFT's on and off (to +15V and -8V)
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    path: Path to save output files to
    dut_name: Full name of device + stage of test    
    start_row: Row # to start iterating through (typically 0)
    start_col: Col # to start iterating through (typically 0)
    end_row: Row # to end iterating through (typically 16)
    end_col: Col # to end iterating through (typically 16)
Returns:
    Tuple, with following parameters:
        Total number of shorts detected
        Output text (to be appended to summary file)
'''
def test_cont_col_to_pzbias_tfts_on(ser, inst, path, dut_name, start_row=0, end_row=16, start_col=0, end_col=16):
    test_name = "CONT_COL_TO_PZBIAS_TFTS_ON"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME_SERIAL)
    out_array = np.zeros((18, 17), dtype='U64')             # create string-typed numpy array
    out_array[1] = ["C" + str(i) for i in range(0, 17)]     # set cols of output array to be "C1"..."C16"
    for i in range(len(out_array)):
        out_array[len(out_array)-1-i][0] = "R" + str(i+1)   # set rows of output array to be "R1"..."R16"
    #out_array[0][0] = "Resistance Test Column to PZBIAS w/ TFTs ON"
    #out_array[0][1] = dut_name
    #out_array[0][2] = dt.datetime.now()
    out_array[1][0] = "Resistance (ohm)"
    out_text += "Sensor Col to PZBIAS Continuity Detection with TFT's ON Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline="") as file: 
        writer = csv.writer(file)
        writer.writerow(["Row Index", "Column Index", "Col. Res. to PZBIAS w/ TFTs ON (ohm)"])
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                serialWriteWithDelay(ser, b'Z')                 # set row switches to high-Z and disable muxes
                serialWriteWithDelay(ser, b'W')                 # set secondary mux to col/PZBIAS mode
                serialWriteWithDelay(ser, b'R')                 # set mode to row write mode
                serialWriteWithDelay(ser, bytes(hex(row)[2:], 'utf-8'))         # write row index
                serialWriteWithDelay(ser, b'L')                 # set mode to column write mode
                serialWriteWithDelay(ser, bytes(hex(col)[2:], 'utf-8'))         # write column index
                serialWriteWithDelay(ser, b'P')                 # "ON" measurement - cap. check mode puts row switches in +15/-8V mode
                tft_on_meas = float(instQueryWithDelay(inst, 'meas:res?'))      # read mux on measurement
                if (tft_on_meas < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                    num_shorts += 1
                out_array[(16-row)+1][col+1] = tft_on_meas
                writer.writerow([str(row+1), str(col+1), tft_on_meas]) # appends to CSV with 1 index
                time.sleep(DELAY_TIME_SERIAL)
            printProgressBar(row + 1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    serialWriteWithDelay(ser, b'Z')                             # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " col/PZBIAS with TFT's ON short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    out_array = np.delete(out_array, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt.csv", out_array, delimiter=",", fmt="%s")
    out_array = np.delete(out_array, (0), axis=1)
    out_array = out_array[1:]
    if (num_shorts > 0):
        for row in range(out_array.shape[0]):
            for col in range(out_array.shape[1]):
                if (float(out_array[row][col]) > RES_SHORT_THRESHOLD_ROWCOL):
                    print(".", end="")
                    out_text += "."
                else:
                    print("X", end="")
                    out_text += "X"
            print("")
            out_text += "\n"
    print("")
    return(num_shorts, out_text)

'''
Placeholder function that sweeps through the reset lines on the primary mux board
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    start_rst: Rst # to start iterating through (typically 0)
    end_rst: Rst # to end iterating through (typically 16)
Returns: none
'''
def test_reset_sweep(ser, start_rst=0, end_rst=16):
    printProgressBar(0, 16, suffix = "Reset 0/16", length = 16)
    for i in range(start_rst, end_rst):
        serialWriteWithDelay(ser, b'Z')
        serialWriteWithDelay(ser, b'T')
        serialWriteWithDelay(ser, bytes(hex(i)[2:], 'utf-8'))
        serialWriteWithDelay(ser, b'S')
        # do stuff here
        printProgressBar(i+1, 16, suffix = "Reset " + str(i+1) + "/16", length = 16)
        time.sleep(DELAY_TIME_SERIAL)
    serialWriteWithDelay(b'Z') # set all mux enables + mux channels to OFF
    return(0, "")

'''
Interactive function that helps with alignment of flex presser/probe card fixtures to the die
to ensure proper loopback connectivity. Beeps one way (loop1_name) if only LoopA makes contact,
beeps another way (loop2_name) if only LoopB makes contact, and beeps a third way (both_loops_name)
when both loopbacks make contact
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
    num_counts: Function waits this number of measurement cycles with both loopbacks connected before exiting,
                to ensure stable continuity
    loop1_name: Name of file to play when Loopback A makes contact
    loop2_name: Name of file to play when Loopback B makes contact
    both_loops_name: Name of file to play when both loopbacks make contact
    silent: if True, do not play audio
Returns:
    Tuple, with following parameters:
        Loopback A resistance
        Loopback B resistance
'''
def test_loopback_resistance(ser, inst, num_counts=10, loop1_name="loop1.wav", loop2_name="loop2.wav",
                             both_loops_name="both_loops.wav", silent=False):
    mixer.init()
    loop1 = mixer.Sound(loop1_name)
    loop2 = mixer.Sound(loop2_name)
    both_loops = mixer.Sound(both_loops_name)
    inst.write('sens:res:rang 10E3')# set resistance measurement range to 10kOhm
    is_pressed = False
    count = 0
    print("")
    while not is_pressed:
        ser.write(b'&')                                  # set secondary mux to Loopback 1 mode
        time.sleep(DELAY_TIME_SERIAL)
        val1 = float(inst.query('meas:res?'))
        val1_str = "{:.4e}".format(val1)
        time.sleep(DELAY_TIME_INST)
        ser.write(b'*')                                  # set secondary mux to Loopback 2 mode
        time.sleep(DELAY_TIME_SERIAL)
        val2 = float(inst.query('meas:res?'))
        val2_str = "{:.4e}".format(val2)
        time.sleep(DELAY_TIME_INST)
        print("LOOP1 OHM " + val1_str + " LOOP2 OHM " + val2_str, end='\r')
        if (val1 < RES_SHORT_THRESHOLD_ROWCOL and val2 < RES_SHORT_THRESHOLD_ROWCOL):
            if not silent:
                both_loops.play()
            time.sleep(0.5)
            count += 1
        elif (val1 < RES_SHORT_THRESHOLD_ROWCOL):
            if not silent:
                loop1.play()
            time.sleep(0.25)
        elif (val2 < RES_SHORT_THRESHOLD_ROWCOL):
            if not silent:
                loop2.play()
            time.sleep(0.25)
        if (keyboard.is_pressed('q') or count > num_counts):
            is_pressed = True
            print("")
            inst.write('sens:res:rang 100E6')# set resistance measurement range to 10MOhm
            mixer.quit()
            return (val1, val2)

'''
Measures Loopback A resistance
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
Returns:
    Loopback A resistance (float)
'''
def test_cont_loopback_one(ser, inst):
    out_text = "Sensor Loopback One Continuity Detection Running..."
    out_text += "\n"
    val = 0
    inst.write('sens:res:rang 10E3')                 # set resistance measurement range to 10Kohm
    time.sleep(DELAY_TIME_INST)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME_SERIAL)
    ser.write(b'&')                                  # set secondary mux to Loopback 1 mode
    time.sleep(DELAY_TIME_SERIAL)
    val = float(inst.query('meas:res?'))             # read resistance from the meter
    out_text += f"{val:,}" + " ohms"
    time.sleep(DELAY_TIME_INST)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME_SERIAL)
    inst.write('sens:res:rang 100E6')                # set resistance measurement range back to 100 MOhm
    time.sleep(DELAY_TIME_INST)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nLoopback one is OPEN!\n"
    else:
        out_text += "\nLoopback one measures resistance!\n"
    print(out_text)
    return(val, out_text)

'''
Measures Loopback A resistance
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (e.g. DMM or PSU)
Returns:
    Loopback A resistance (float)
'''
def test_cont_loopback_two(ser, inst):
    out_text = "Sensor Loopback Two Continuity Detection Running..."
    out_text += "\n"
    val = 0
    inst.write('sens:res:rang 10E3')                 # set resistance measurement range to 10Kohm
    time.sleep(DELAY_TIME_INST)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME_SERIAL)
    ser.write(b'*')                                  # set secondary mux to Loopback 2 mode
    time.sleep(DELAY_TIME_SERIAL)
    val = float(inst.query('meas:res?'))             # read resistance from the meter
    out_text += f"{val:,}" + " ohms"
    time.sleep(DELAY_TIME_INST)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME_SERIAL)
    inst.write('sens:res:rang 100E6')                # set resistance measurement range back to 100 MOhm
    time.sleep(DELAY_TIME_INST)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nLoopback two is OPEN!\n"
    else:
        out_text += "\nLoopback two measures resistance!\n"
    print(out_text)
    return(val, out_text)

# helper functions for file compare/diff
'''
Helper function that extracts the timestamp from path+filename
Parameters:
    file_name: path + filename
Returns:
    Extracted timestamp, string format (e.g. YYYY-MM-DD_HH-MM-SS)
'''
def get_timestamp_raw(file_name):
    return file_name.split("\\")[-1][:19]

'''
Helper function that extracts the timestamp from filename
Parameters:
    file_name: filename alone, no path
Returns:
    Extracted timestamp, string format (e.g. YYYY-MM-DD_HH-MM-SS)
'''
def get_timestamp_truncated(file_name):    
    return file_name[:19]

'''
Helper function that extracts the text from a string before the keyword
Parameters:
    string: Full text to split
    keyword: Text to search for in string
Returns:
    String with text leading up to keyword, or the full text string if keyword is not in string
'''
def truncate_to_keyword(string, keyword):
    if keyword in string:
        index_val = string.index(keyword)
        return string[:index_val]
    else:
        return string

'''
Compares two tester output files, prints out their differences, and returns number of differences.
Splits each output file into chunks/results of each test (delineated by line breaks) and compares files chunk by chunk
If files are mismatched in number of chunks, warns user and returns -1
Parameters:
    path: base path to both filenames (they must be in the same directory)
    filename1: first file to compare
    filename2: second file to compare
Returns:
    Number of differences detected, or -1 if the two files are mismatched in number of chunks
'''
def cmp_two_files(path, filename1, filename2):
    print("\nOriginal file is " + filename1)
    print("Comparing against filename " + filename2)
    num_diffs = 0
    with open(path+filename1, 'r') as f1, open(path+filename2, 'r') as f2:
        f1_list = f1.readlines()
        f2_list = f2.readlines()
        f1_chunk_indices = []
        f2_chunk_indices = []
        f1_chunk_tuples = []
        f2_chunk_tuples = []
        f1_chunks_raw = []
        f2_chunks_raw = []
        f1_chunks = []
        f2_chunks = []
        for i in range(len(f1_list)):
            if f1_list[i] in ['\n', '\r\n']:
                f1_chunk_indices.append(i)
        f1_chunk_indices.append(len(f1_list))
        for i in range(1, len(f1_chunk_indices)):
            f1_chunk_tuples.append((f1_chunk_indices[i-1], f1_chunk_indices[i]))
        for tuple in f1_chunk_tuples:
            f1_chunks_raw.append(f1_list[tuple[0]:tuple[1]][1:])
        for chunk in f1_chunks_raw:
            chunk_output = []
            for string in chunk:
                if ("If there are shorts" not in string and "Loopback" not in string):
                    if ("array" in string):
                        string = truncate_to_keyword(string, "in")
                    chunk_output.append(string)
            if (len(chunk_output) > 0):
                f1_chunks.append(chunk_output)

        print("")
        for i in range(len(f2_list)):
            if f2_list[i] in ['\n', '\r\n']:
                f2_chunk_indices.append(i)
        f2_chunk_indices.append(len(f2_list))
        for i in range(1, len(f2_chunk_indices)):
            f2_chunk_tuples.append((f2_chunk_indices[i-1], f2_chunk_indices[i]))
        for tuple in f2_chunk_tuples:
            f2_chunks_raw.append(f2_list[tuple[0]:tuple[1]][1:])
        for chunk in f2_chunks_raw:
            chunk_output = []
            for string in chunk:
                if ("If there are shorts" not in string and "Loopback" not in string):
                    if ("array" in string):
                        string = truncate_to_keyword(string, "in")
                    chunk_output.append(string)
            if (len(chunk_output) > 0):
                f2_chunks.append(chunk_output)

        if (len(f1_chunks) == len(f2_chunks)):
            for i in range(len(f1_chunks)):
                if (f1_chunks[i] != f2_chunks[i]):
                    print("\n\n**********Difference detected:**********\n---File " + filename1 + ":")
                    for chunk in f1_chunks[i]:
                        print(chunk, end="")
                    print("")
                    print("---File " + filename2 + ":")
                    for chunk in f2_chunks[i]:
                        print(chunk, end="")
                    num_diffs += 1
                    print("\n****************************************")
            print("\nThere were " + str(num_diffs) + " difference(s) detected")
            return num_diffs
        elif (len(f1_chunks) < len(f2_chunks)):
            print("WARNING: files have different number of tests...")
            for i in range(len(f1_chunks)):
                if (f1_chunks[i] != f2_chunks[i]):
                    print("\n\n**********Difference detected:**********\n---File " + filename1 + ":")
                    for chunk in f1_chunks[i]:
                        print(chunk, end="")
                    print("")
                    print("---File " + filename2 + ":")
                    for chunk in f2_chunks[i]:
                        print(chunk, end="")
                    num_diffs += 1
                    print("\n****************************************")
            print("\nThere were " + str(num_diffs) + " difference(s) detected")
            print("WARNING: files have different number of tests...")
            return -1
        elif (len(f1_chunks) > len(f2_chunks)):
            print("WARNING: files have different number of tests...")
            for i in range(len(f2_chunks)):
                if (f1_chunks[i] != f2_chunks[i]):
                    print("\n\n**********Difference detected:**********\n---File " + filename1 + ":")
                    for chunk in f1_chunks[i]:
                        print(chunk, end="")
                    print("")
                    print("---File " + filename2 + ":")
                    for chunk in f2_chunks[i]:
                        print(chunk, end="")
                    num_diffs += 1
                    print("\n****************************************")
            print("\n\nThere were " + str(num_diffs) + " difference(s) detected")
            print("WARNING: files have different number of tests...")
            return -1
        else:
            print("ERROR: File lengths are mismatched")

# Helper functions for Google Sheets integration
'''
Returns a Python OAuth credential object that can be used to access Google Apps services,
in particular Google Sheets.
Parameters:
    token_filename : String path to the OAuth token, generated in Google Apps
    cred_filename  : String path to the OAuth secret credential file, which MUST BE KEPT PRIvATE
    scopes         : List containing link to the Google application to access
Returns:
    Python OAuth credentials object, or None if initialization error
'''
def get_creds(token_filename="token.json", cred_filename="credentials.json", scopes=SCOPES):
  try:
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_filename):
      creds = Credentials.from_authorized_user_file(token_filename, scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
      else:
        flow = InstalledAppFlow.from_client_secrets_file(
            cred_filename, scopes
        )
        creds = flow.run_local_server(port=0)
      # Save the credentials for the next run
      with open(token_filename, "w") as token:
        token.write(creds.to_json())
    return creds
  except HttpError as err:
    print(err)
    return None

'''
Function that pulls the array TFT type from the sheet 'Sensing Inventory'/'Sensor Modules'/'Sensor Module SN'
It queries the spreadsheet in column 'A' (default) and auto-parses the input array_id regardless of type
(backplane, array, module). It then looks in the corresponding column 'Q' (default) and pulls TFT type (1 or 3)
Parameters:
    creds:      Initialized Google Apps credential, with token.json initialized. Refer to 'main()' in
                'google_sheets_example.py' for initialization example
    array_id:   The query, can be a backplane, assembly, or module id, in the format 'E2421-002-001-E5_T1_R1-103'
    dieid_cols: The column in which to search for the query, by default column 'A'
    dieid_tfts: The column with the corresponding TFT count, by default column 'Q'
    spreadsheet_id: The Google Sheets spreadsheet ID, extracted from the URL (docs.google.com/spreadsheets/d/***)
    id_sheet_name : The name of the sheet to search in for array_id, by default set by global variable
Returns:
    String with '1' for 1T array or '3' for 3T array, or NoneType object if not found/error
'''
def get_array_transistor_type(creds, array_id, dieid_cols='A', dieid_tfts='R',
                              spreadsheet_id=SPREADSHEET_ID, id_sheet_name=ID_SHEET_NAME):
  try:
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    # Define the range (A1 notation) to append the data at the end of the sheet
    range_name_dieid = f'{id_sheet_name}!' + dieid_cols + ':' + dieid_cols
    range_name_tfttype = f'{id_sheet_name}!' + dieid_tfts + ':' + dieid_tfts
    result_dieid = (
      sheet.values()
      .get(spreadsheetId=spreadsheet_id, range=range_name_dieid)
      .execute()
    )
    result_tfttype = (
      sheet.values()
      .get(spreadsheetId=spreadsheet_id, range=range_name_tfttype)
      .execute()
    )
    values_dieid = result_dieid.get("values", [])
    values_tfttype = result_tfttype.get("values", [])

    found_array = False
    i = 0
    tft_type="INVALID"
    for i in range(len(values_dieid)):
      if (len(values_dieid[i]) > 0):
        if (values_dieid[i][0].rstrip("_").upper().split('_')[0] == array_id.upper().split('_')[0]):
          # print("Found at index " + str(i))
          found_array = True
          tft_type = values_tfttype[i][0]
          break
    if (found_array):
      if (tft_type.split('-')[0] == 'FS'):
        return tft_type.split('-')[1][0]
      else:
        return tft_type.split('-')[0][0]
    else:
      print("Array not found in inventory!")
      return None
  except HttpError as err:
    print(err)
    return None

'''
Writes a row to a spreadsheet, in particular the results sheet of the 'Sensing Inventory' spreadsheet.
This payload is a 1D row array containing the desired values to write to the sheet.
Data is appended after the last data-containing row of the spreadsheet.
Parameters:
    creds:      Initialized Google Apps credential, with token.json initialized. Refer to 'main()' in
                'google_sheets_example.py' for initialization example
    payload:    a 1D array containing the data to write to the spreadsheet, in string format
    range_out_start_col: The first (leftmost) column to start writing to
    range_out_end_Col  : The last (rightmost) column to end writing to
    spreadsheet_id : The Google Sheets spreadsheet ID, extracted from the URL (docs.google.com/spreadsheets/d/***)
    out_sheet_name : The name of the sheet to write in, by default set to global variable
Returns:
    True if successfully written, or False otherwise
'''
def write_to_spreadsheet(creds, payload, range_out_start_col='A', range_out_end_col='E',
                         spreadsheet_id=SPREADSHEET_ID, out_sheet_name=OUT_SHEET_NAME):
  if (type(payload) is not list):
    print("ERROR: payload is not a list...")
    return False
  try:
    service = build("sheets", "v4", credentials=creds)
     # Prepare the request body with the values to append
    body_out = {
        'values': [payload]
    }
    range_name_out = f'{out_sheet_name}!' + range_out_start_col + ':' + range_out_end_col
    # Call the API to append the new row
    sheet = service.spreadsheets()
    result = sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name_out,
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body=body_out
    ).execute()
    return True
  except HttpError as err:
    print(err)
    return False

'''
Helper function to pass/fail continuity check function results
Parameters:
    num_shorts : the value to be compared
    threshold  : the maximum count to pass
Returns:
    "PASS" if num_shorts <= threshold, "FAIL" otherwise
'''
def check_cont_results(num_shorts, threshold=0):
    return "PASS" if num_shorts <= threshold else "FAIL"

'''
Helper function to pass/fail capacitance check function results
Parameters:
    num_shorts : the value to be compared
    threshold  : the minimum count to pass
Returns:
    "PASS" if num_shorts >= threshold, "FAIL" otherwise
'''
def check_cap_results(num_shorts, threshold=MIN_PASS_CAP_COUNT):
    return "PASS" if num_shorts >= threshold else "FAIL"

def main():
    datetime_now = dt.datetime.now()
    ser = init_helper(init_serial(COM_PORT_DEFAULT))
    rm = pyvisa.ResourceManager()
    inst = init_helper(init_multimeter(rm))
    if (USING_USB_PSU):
        psu = init_helper(init_psu(rm))
        init_helper(set_psu_on(psu, PSU_DELAY_TIME))

    print("\nSetup Instructions:\n" +
        "- Plug sensor into connector on primary \n" +
        "- Connect multimeter (+) lead to secondary mux board ROW (+)/red wire\n" +
        "- Connect multimeter (-) lead to secondary mux board COL (+)/red wire\n" +
        "- Ensure power supply is ON\n")

    dut_name_input = ""
    while True:
        try:
            dut_name_input = input("Please enter the array ID (e.g. E2408-001-2-E2_T2): ")
        except ValueError:
            print("Sorry, array ID can't be blank")
            continue
        if (len(dut_name_input) < 1):
            print("Sorry, array ID can't be blank")
            continue
        else:
            break
    '''
    extracts array type from the input by splitting into chunks by underscore
    1 chunk means backplane
    2 chunks mean array (sensors on backplane)
    3 chunks mean module (array with attached flex)
    '''
    array_stage_raw = len(dut_name_input.rstrip('_').split('_'))
    array_stage_text = ARRAY_ASSY_TYPES[array_stage_raw]
    override = input("Array type is '" + array_stage_text + "'. Press 'enter' to continue with tests, " +
                     "or type 'change' to override: ")
    if (override.lower() == 'change'):
        query = "Please select from the following...\n"
        for key in ARRAY_ASSY_TYPES.keys():
            query += "- " + str(key) + " for " + ARRAY_ASSY_TYPES[key] + "\n"
        query = query[:-1] + ": "
        while True:
            try:
                array_stage_raw = int(input(query))
            except ValueError:
                print("Sorry, please enter a numerical value...")
                continue
            if (int(array_stage_raw) not in ARRAY_ASSY_TYPES.keys()):
                print("Sorry, please enter a valid selection...")
                continue
            else:
                break
        array_stage_text = ARRAY_ASSY_TYPES[array_stage_raw]

    path = PATH_BASE + array_stage_text.title() + "\\"
    if (os.path.exists(path + dut_name_input)):
        path += dut_name_input + "\\"
    else:
        make_new_path = "Y"
        valid_responses = ["Y", "N"]
        while True:
            try:
                make_new_path = input("Are you sure you want to make a new directory " + path + dut_name_input + "?\n" +
                                      "'Y' or 'N': ")
            except ValueError:
                print("Sorry, please enter 'Y' or 'N'")
                continue
            if (make_new_path.upper() not in valid_responses):
                print("Sorry, please enter 'Y' or 'N'")
                continue
            else:
                if (make_new_path.upper() == "N"):
                    print("Exiting program now...")
                    sys.exit(0)
                else:
                    print("Making new directory...")
                    os.makedirs(path + "\\" + dut_name_input)
                    path += dut_name_input + "\\"
                break

    dut_module_stage_input = ""
    if (array_stage_raw == 3):
        while True:
            try:
                dut_module_stage_input = input("\nPlease enter the array stage of assembly (e.g. onglass): ")
            except ValueError:
                print("Sorry, array stage of assembly can't be blank")
                continue
            if (len(dut_module_stage_input) < 1):
                print("Sorry, array stage of assembly can't be blank")
                continue
            else:
                break

    dut_name_full = dut_name_input + "_" +  dut_module_stage_input
    print("Test data for " + dut_name_full + " will save to path " + path + "\n")

    # Query TFT type from Google Sheets with option to override
    creds = get_creds()
    array_tft_type = get_array_transistor_type(creds, dut_name_input)
    override = ""
    if (type(array_tft_type) is int):
        override = input("Array TFT type is " + str(array_tft_type) + "T.\nPress 'enter' to continue with " +
                     str(array_tft_type) + "T tests, or type 'change' to override: ")
    else:
        override = "change"
    if (override.lower() == 'change'):
        query = "Please select from the following...\n"
        for key in ARRAY_TFT_TYPES:
            query += "- " + str(key) + " for " + str(key) + "T\n"
        query = query[:-1] + ": "
        while True:
            try:
                array_tft_type = int(input(query))
            except ValueError:
                print("Sorry, please enter a numerical value...")
                continue
            if (array_tft_type not in ARRAY_TFT_TYPES):
                print("Sorry, please enter a valid selection...")
                continue
            else:
                break
    print("Running tests for " + str(array_tft_type) + "T array...\n")

    out_string = ""
    loop_one_res = 0
    loop_two_res = 0

    if (array_stage_raw in [1, 2]): # Runs loopback check on bare backplanes and sensor arrays not bonded to flex
        print("Press 'q' to skip loopback check...")
        (loop_one_res, loop_two_res) = test_loopback_resistance(ser, inst)
        out_string += "Loopback 1 resistance: " + str(loop_one_res) + " ohms" + "\n"
        out_string += "Loopback 2 resistance: " + str(loop_two_res) + " ohms" + "\n\n"
        print("")
        with open(path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_input + dut_module_stage_input + "_loopback_measurements.csv", 'w', newline='') as file:
            file.write("Loopback 1 res. (ohm),Loopback 2 res. (ohm)\n")
            file.write(str(loop_one_res) + "," + str(loop_two_res))
    else:
        loop_one_res = test_cont_loopback_one(ser, inst)
        time.sleep(1)
        loop_two_res = test_cont_loopback_two(ser, inst)
        out_string += str(loop_one_res[1]) + "\n"
        out_string += str(loop_two_res[1]) + "\n\n"
        with open(path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_input + dut_module_stage_input + "_loopback_measurements.csv", 'w', newline='') as file:
            file.write("Loopback 1 res. (ohm),Loopback 2 res. (ohm)\n")
            file.write(str(loop_one_res[0]) + "," + str(loop_two_res[0]))

    output_payload_gsheets_dict["Timestamp"]          = datetime_now.strftime('%Y-%m-%d_%H-%M-%S')
    output_payload_gsheets_dict["Serial Number"]      = dut_name_input
    output_payload_gsheets_dict["Array Type"]         = array_stage_text
    output_payload_gsheets_dict["Array Module Stage"] = dut_module_stage_input
    output_payload_gsheets_dict["TFT Type"]           = str(array_tft_type) + "T"
    output_payload_gsheets_dict["Loopback One (ohm)"] = str(loop_one_res[0])
    output_payload_gsheets_dict["Loopback Two (ohm)"] = str(loop_two_res[0])

    if (array_tft_type == 1):
        special_test_state = 0
        test_selection_raw = input("Please hit 'enter' for default (full) 1T test, or\n" +
                                "type '1' to only run cap + TFT cont. tests and skip continuity checks, or\n" +
                                "type '2' to only run continuity tests: ")
        if (test_selection_raw == "1"):
            special_test_state = 1
            print("Running only cap and TFT ON tests...\n")
        elif (test_selection_raw == "2"):
            special_test_state = 2
            print("Running only continuity tests...\n")
        else:
            print("Running all tests...\n")

        if (special_test_state == 1): # only run capacitance and TFT ON tests
            test_selection_raw = input("Please hit 'enter' for default cap test 1nF range, or type '1' to " +
                                    "run capacitance test with 10nF range: ")
            meas_range_input = '1e-9'
            if (test_selection_raw == "1"):
                meas_range_input = '1e-8'
                print("Running cap test with new 10nF range...\n")
            else:
                meas_range_input = '1e-9'
                print("Running cap test with default 1nF range...\n")
            test_cap_out = test_cap(ser, inst, path, dut_name_input, dut_module_stage_input,
                                    "CAP_COL_TO_PZBIAS", array_stage_text, meas_range_input)
            test_cont_col_to_pzbias_tfts_on_out = test_cont_col_to_pzbias_tfts_on(ser, inst, path, dut_name_input)

            out_string += "\n" + test_cap_out[1]
            out_string += test_cont_col_to_pzbias_tfts_on_out[1]
            output_payload_gsheets_dict["Cap Col to PZBIAS "] = check_cap_results(test_cap_out[0], MIN_PASS_CAP_COUNT)
            output_payload_gsheets_dict["Col to PZBIAS with TFT's ON"] = check_cont_results(test_cont_col_to_pzbias_tfts_on_out[0], MAX_PASS_CONT_COUNT_TWO_DIM)

        elif (special_test_state == 2):
            cont_row_to_column = test_cont_two_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_COL")
            cont_row_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_PZBIAS")
            cont_row_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_SHIELD")
            cont_col_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_PZBIAS")
            cont_col_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_SHIELD")
            cont_shield_to_pzbias = test_cont_node(dut_name_full, "CONT_SHIELD_TO_PZBIAS")

            out_string += cont_row_to_column[1] + "\n"
            out_string += cont_row_to_pzbias[1] + "\n"
            out_string += cont_row_to_shield[1] + "\n"
            out_string += cont_col_to_pzbias[1] + "\n"
            out_string += cont_col_to_shield[1] + "\n"
            out_string += cont_shield_to_pzbias[1]

            output_payload_gsheets_dict["Row to Col"]    = check_cont_results(cont_row_to_column[0], MAX_PASS_CONT_COUNT_TWO_DIM)
            output_payload_gsheets_dict["Row to PZBIAS"] = check_cont_results(cont_row_to_pzbias[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["Row to SHIELD"] = check_cont_results(cont_row_to_shield[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["Col to PZBIAS"] = check_cont_results(cont_col_to_pzbias[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["Col to SHIELD"] = check_cont_results(cont_col_to_shield[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["SHIELD to PZBIAS"] = cont_shield_to_pzbias[0]
        else:
            # these are tuples of (num shorts, output string)
            cont_row_to_column = test_cont_two_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_COL")
            cont_row_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_PZBIAS")
            cont_row_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_SHIELD")
            cont_col_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_PZBIAS")
            cont_col_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_SHIELD")
            cont_shield_to_pzbias = test_cont_node(ser, inst, path, dut_name_full, "CONT_SHIELD_TO_PZBIAS")

            out_string += cont_row_to_column[1] + "\n"
            out_string += cont_row_to_pzbias[1] + "\n"
            out_string += cont_row_to_shield[1] + "\n"
            out_string += cont_col_to_pzbias[1] + "\n"
            out_string += cont_col_to_shield[1] + "\n"
            out_string += cont_shield_to_pzbias[1]

            output_payload_gsheets_dict["Row to Col"]    = check_cont_results(cont_row_to_column[0], MAX_PASS_CONT_COUNT_TWO_DIM)
            output_payload_gsheets_dict["Row to PZBIAS"] = check_cont_results(cont_row_to_pzbias[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["Row to SHIELD"] = check_cont_results(cont_row_to_shield[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["Col to PZBIAS"] = check_cont_results(cont_col_to_pzbias[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["Col to SHIELD"] = check_cont_results(cont_col_to_shield[0], MAX_PASS_CONT_COUNT_ONE_DIM)
            output_payload_gsheets_dict["SHIELD to PZBIAS"] = cont_shield_to_pzbias[0]

            hasShorts = cont_row_to_column[0]>0 or cont_row_to_pzbias[0]>0 or cont_col_to_pzbias[0]>0 or cont_row_to_shield[0]>0 or cont_col_to_shield[0]>0 or cont_shield_to_pzbias[0]>0
            response = ""
            if hasShorts:
                print("This array doesn't have pants... it has shorts!")
                response = input("Type 'test' and 'enter' to continue with cap check, or hit 'enter' to skip cap check: ")
            else:
                temp = input("Please hit 'enter' to continue with cap tests, or type 'exit' to exit: ")
                if (len(temp) == 0):
                    response = "test"
                else:
                    response = ""
            if (response == "test"):
                print("Running cap and TFT continuity tests...")
                test_selection_raw = input("\nPlease hit 'enter' for default cap test 1nF range, or type '1' to " +
                                        "run capacitance test with 10nF range: ")
                meas_range_input = '1e-9'
                if (test_selection_raw == "1"):
                    meas_range_input = '1e-8'
                    print("Running cap test with new 10nF range...\n")
                else:
                    meas_range_input = '1e-9'
                    print("Running cap test with default 1nF range...\n")
                test_cap_out = test_cap(ser, inst, path, dut_name_input, dut_module_stage_input,
                                        "CAP_COL_TO_PZBIAS", array_stage_text, meas_range_input)
                test_cont_col_to_pzbias_tfts_on_out = test_cont_col_to_pzbias_tfts_on(ser, inst, path, dut_name_input)

                out_string += "\n" + test_cap_out[1]
                out_string += test_cont_col_to_pzbias_tfts_on_out[1]
                output_payload_gsheets_dict["Cap Col to PZBIAS "] = check_cap_results(test_cap_out[0], MIN_PASS_CAP_COUNT)
                output_payload_gsheets_dict["Col to PZBIAS with TFT's ON"] = check_cont_results(test_cont_col_to_pzbias_tfts_on_out[0], MAX_PASS_CONT_COUNT_TWO_DIM)

    # 3T array testing
    elif (array_tft_type == 3):
        cont_row_to_column = test_cont_two_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_COL")
        cont_row_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_PZBIAS")
        cont_row_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_SHIELD")
        cont_col_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_PZBIAS")
        cont_col_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_SHIELD")
        cont_col_to_vdd    = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_VDD")
        cont_col_to_vrst   = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_VRST")
        cont_rst_to_column = test_cont_two_dim(ser, inst, path, dut_name_full, "CONT_RST_TO_COL")
        cont_rst_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_RST_TO_SHIELD")
        cont_rst_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_RST_TO_PZBIAS")
        cont_vdd_to_shield = test_cont_node(ser, inst, path, dut_name_full, "CONT_VDD_TO_SHIELD")
        cont_vdd_to_pzbias = test_cont_node(ser, inst, path, dut_name_full, "CONT_VDD_TO_PZBIAS")
        cont_vrst_to_shield = test_cont_node(ser, inst, path, dut_name_full, "CONT_VRST_TO_SHIELD")
        cont_vrst_to_pzbias = test_cont_node(ser, inst, path, dut_name_full, "CONT_VRST_TO_PZBIAS")
        cont_shield_to_pzbias = test_cont_node(ser, inst, path, dut_name_full, "CONT_SHIELD_TO_PZBIAS")

        out_string += cont_row_to_column[1] + "\n"
        out_string += cont_row_to_pzbias[1] + "\n"
        out_string += cont_row_to_shield[1] + "\n"
        out_string += cont_col_to_pzbias[1] + "\n"
        out_string += cont_col_to_shield[1] + "\n"
        out_string += cont_col_to_vdd[1] + "\n"
        out_string += cont_col_to_vrst[1] + "\n"
        out_string += cont_rst_to_column[1] + "\n"
        out_string += cont_rst_to_shield[1] + "\n"
        out_string += cont_rst_to_pzbias[1] + "\n"
        out_string += cont_vdd_to_shield[1] + "\n"
        out_string += cont_vdd_to_pzbias[1] + "\n"
        out_string += cont_vrst_to_shield[1] + "\n"
        out_string += cont_vrst_to_pzbias[1] + "\n"
        out_string += cont_shield_to_pzbias[1]

        output_payload_gsheets_dict["Row to Col"]    = check_cont_results(cont_row_to_column[0], MAX_PASS_CONT_COUNT_TWO_DIM)
        output_payload_gsheets_dict["Row to PZBIAS"] = check_cont_results(cont_row_to_pzbias[0], MAX_PASS_CONT_COUNT_ONE_DIM)
        output_payload_gsheets_dict["Row to SHIELD"] = check_cont_results(cont_row_to_shield[0], MAX_PASS_CONT_COUNT_ONE_DIM)
        output_payload_gsheets_dict["Col to PZBIAS"] = check_cont_results(cont_col_to_pzbias[0], MAX_PASS_CONT_COUNT_ONE_DIM)
        output_payload_gsheets_dict["Col to SHIELD"] = check_cont_results(cont_col_to_shield[0], MAX_PASS_CONT_COUNT_ONE_DIM)
        output_payload_gsheets_dict["Col to Vdd"]    = check_cont_results(cont_col_to_vdd[0], MAX_PASS_CONT_COUNT_ONE_DIM)
        output_payload_gsheets_dict["Col to Vrst"]   = check_cont_results(cont_col_to_vrst[0], MAX_PASS_CONT_COUNT_ONE_DIM)
        output_payload_gsheets_dict["Rst to Col"]    = check_cont_results(cont_rst_to_column[0], MAX_PASS_CONT_COUNT_TWO_DIM)
        output_payload_gsheets_dict["Rst to SHIELD"] = check_cont_results(cont_rst_to_shield[0], MAX_PASS_CONT_COUNT_ONE_DIM)
        output_payload_gsheets_dict["Rst to PZBIAS"] = check_cont_results(cont_rst_to_pzbias[0], MAX_PASS_CONT_COUNT_ONE_DIM)

        output_payload_gsheets_dict["Vdd to SHIELD"] = cont_vdd_to_shield[0]
        output_payload_gsheets_dict["Vdd to PZBIAS"] = cont_vdd_to_pzbias[0]
        output_payload_gsheets_dict["Vrst to SHIELD"] = cont_vrst_to_shield[0]
        output_payload_gsheets_dict["Vrst to PZBIAS"] = cont_vrst_to_pzbias[0]
        output_payload_gsheets_dict["SHIELD to PZBIAS"] = cont_shield_to_pzbias[0]
    else:
        pass

    print("Done testing serial number " + dut_name_full + "!\n")

    output_filename = datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_full + "_summary.txt"
    output_filename_full = path + output_filename
    out_string = (datetime_now.strftime('%Y-%m-%d %H:%M:%S') + "\nArray ID: " + dut_name_full + "\n" + 
                "Array Type: " + str(array_tft_type) + "T\n" +
                "\nIf there are shorts, the output (.) means open and (X) means short\n\n") + out_string

    with open(output_filename_full, 'w', newline='') as file:
        file.write(out_string)

    output_payload_gsheets = list(output_payload_gsheets_dict.values())
    write_success = write_to_spreadsheet(creds, output_payload_gsheets)
    if (write_success):
        print("Successfully wrote data to Google Sheets!")
    else:
        print("ERROR: Could not write data to Google Sheets")

    inst.close()
    if (USING_USB_PSU):
        set_psu_off(psu)
        psu.close()

    # --- begin file compare section ---

    filenames_raw = glob.glob(path + '*summary.txt')
    filenames_raw = list(sorted(filenames_raw, key=get_timestamp_raw))
    filenames = list({x.replace(path, '') for x in filenames_raw})
    filenames = list(sorted(filenames, key=get_timestamp_truncated))

    if (len(filenames) <= 1):
        print("No files to compare. Exiting...")
        sys.exit(0)

    compare_filename = ""
    file_cmp_index = -1
    valid_responses = ["Y", "M", ""]
    cmd = ""
    while True:
        try:
            cmd = input("Comparing output summary files- Please enter:\n" +
                "- 'Y' to compare data with previous test\n" +
                "- 'M' to manually compare against a file for this array, or\n" +
                "- 'enter' to exit... ").upper()
        except ValueError:
            print("Error: please enter a valid response")
            continue
        if (cmd not in valid_responses):
            print("Error: please enter a valid response")
            continue
        else:
            break

    if (cmd.upper().strip() == 'Y'):
        file_cmp_index = -2
        compare_filename = filenames[file_cmp_index]
        cmp_two_files(path, output_filename, compare_filename)
    elif (cmd.upper().strip() == 'M'):
        for i in range(len(filenames)-1):
            print(str(i) + ": " + filenames[i])
        while True:
            try:
                file_cmp_index = int(input("Please select file 1 to compare: "))
            except ValueError:
                print("Error: please enter a number between 0 and " + str(len(filenames)-2))
                continue
            if (file_cmp_index not in range(0, len(filenames)-1)):
                print("Error: please enter a number between 0 and " + str(len(filenames)-2))
                continue
            else:
                break
        compare_filename = filenames[file_cmp_index]
        cmp_two_files(path, output_filename, compare_filename)
    else:
        print("Exiting program...")
        sys.exit(0)

if (__name__ == "__main__"):
    main()