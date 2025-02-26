'''
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
  * csv library
  * datetime library
  * numpy library
  * serial library
  * Google Python libraries -- to install, run this command:
    pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

ONE INDEXED OUTPUT!
'''

import csv
import glob
import keyboard
import os
import os.path
import pyvisa
import serial
import serial.tools.list_ports
import sys
import time
import datetime as dt
import numpy as np


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http
from tester_hw_configs import *

# silence the PyGame import startup message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
from pygame import mixer

# Environment variable to track power supply state
# -1: OFF, 0: Undetermined, 1: ON
PSU_IS_ON_NOW = 0

'''
Dictionary used to store results from tests
Results are uploaded to Google Sheets in this order
Tests that were not run will be uploaded to GSheets as blank.
'''
output_payload_gsheets_dict = {
    "Timestamp"            : "",
    "Tester Serial Number" : "",
    "Array Serial Number"  : "",
    "Array Type"           : "",
    "Array Module Stage"   : "",
    "TFT Type"             : "",
    "Loopback One (ohm)"   : "",
    "Loopback Two (ohm)"   : "",
    "Cap Col to PZBIAS (# pass)"   : "",
    "Col to PZBIAS with TFT's ON (# shorts)" : "",
    "Row to Col (# shorts)"    : "",
    "Rst to Col (# shorts)"    : "",
    "Row to PZBIAS (# shorts)" : "",
    "Row to SHIELD (# shorts)" : "",
    "Col to PZBIAS (# shorts)" : "",
    "Col to SHIELD (# shorts)" : "",
    "Col to Vdd (# shorts)"    : "",
    "Col to Vrst (# shorts)"   : "",
    "Rst to SHIELD (# shorts)" : "",
    "Rst to PZBIAS (# shorts)" : "",
    "SHIELD to PZBIAS (ohm)"   : "",
    "Vdd to SHIELD (ohm)"      : "",
    "Vdd to PZBIAS (ohm)"      : "",
    "Vrst to SHIELD (ohm)"     : "",
    "Vrst to PZBIAS (ohm)"     : ""
}

# Helper functions for overall program
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
def print_progress_bar(iteration, total, prefix='', suffix='', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()

'''
Queries user for an input until a valid response is given (e.g. response is in the parameter dictionary)
Input is case agnostic, but returned value is in upper case.
Prompt will substitute empty keys "" with 'enter', as inputting an 'enter' key will return a blank character
Parameters:
    options: either a dictionary of (valid_response_key: corresponding_value), e.g. (1: "test one"), with keys as either string or int
             or a list of acceptable values, int or string
Returns:
    String with valid response that is in the dictionary keys, converted to upper case
'''
def query_valid_response(options):
    response_in = ""
    query_text = "Please enter one of the following:\n"
    valid_responses = []
    if (type(options) is list):
        for option in options:
            valid_responses.append(str(option).upper())
        for item in valid_responses:
            if (item == ""):
                item = "enter"
            query_text += "- '" + str(item) + "'\n"
    elif (type(options) is dict):
        new_options = {}
        for key in list(options.keys()):
            new_options[str(key).upper()] = options[key]
        for option in new_options:
            valid_responses.append(str(option))
        for item in valid_responses:
            item_print = item
            if (item == ""):
                item_print = "'enter'"
            query_text += "- " + str(item_print) + " to '" + str(new_options[item]) + "'\n"
    else:
        print("ERROR: invalid options to query...")
        return None

    while True:
        try:
            response_in = input(query_text)
        except ValueError:
            print("Error: please enter a valid response")
            continue
        if (response_in.upper() not in valid_responses):
            print("Error: please enter a valid response")
            continue
        else:
            return response_in.upper()

# Init and set functions for test equipment
'''
Helper function that checks if a newly initialized hardware object (e.g. serial, multimeter, PSU) is null
If object is null, exit program. If not, return the object.
Parameter:
    object: A function call (e.g. init_serial())
    exit_if_unsuccessful:
        True (default) if program should quit if improper initialization
        False if program should continue running
Return:
    the created object, or exits program if function returns null
'''
def init_helper(object, exit_if_unsuccessful=True):
    if (object == None):
        print("ERROR: COULD NOT INITIALIZE OBJECT!")
        if (exit_if_unsuccessful):
            print("Exiting...")
            time.sleep(5)
            sys.exit(0)
        return None
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
    ser.bytesize = serial.EIGHTBITS    #number of bits per bytes
    ser.parity = serial.PARITY_NONE    #set parity check: no parity
    ser.stopbits = serial.STOPBITS_ONE #number of stop bits
    ser.timeout = 1                    #non-block read
    ser.xonxoff = False                #disable software flow control
    ser.rtscts = False                 #disable hardware (RTS/CTS) flow control
    ser.dsrdtr = False                 #disable hardware (DSR/DTR) flow control
    ser.writeTimeout = 2               #timeout for write
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
        print("Selecting the Arduino COM port COM[x],")
        port_in = query_valid_response(list_of_ports)
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
    rm: A PyVISA resource manager object (rm)
    dmm_id: String serial name, default: USB0::0x05E6::0x6500::04611761::INSTR
    res_range: Default resistance range '100e6'
    cap_range: Default capacitance range '10e-3
Returns:
    An initialized PyVISA object, or a null object if not initialized
TODO: implement equipment type check that quits if this address is not actually the right equipment
NOTE: remember to run 'dmm.close()' when done with the DMM
'''
def init_multimeter(rm, dmm_id=DMM_SERIAL_STRING_DEFAULT, res_range=RES_RANGE_DEFAULT, cap_range=CAP_RANGE_DEFAULT):
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
    rm: A PyVISA resource manager object (rm)
    psu_id: String serial name, default: USB0::0x05E6::0x6500::04611761::INSTR
Returns:
    An initialized PyVISA object, or a null object if not initialized
TODO: implement equipment type check that quits if this address is not actually the right equipment
NOTE: remember to run 'psu.close()' when done with the PSU
'''
def init_psu(rm, psu_id=PSU_SERIAL_STRING_DEFAULT):
    global PSU_IS_ON_NOW
    PSU_IS_ON_NOW = 0
    try:
        psu = rm.open_resource(psu_id)
        print("Connected to VISA PSU!")
        # Have pyvisa handle line termination
        psu.read_termination = '\n'
        # Clear buffer and status
        psu.write('*CLS')
        return psu
    except Exception as e:
        print("ERROR: couldn't connect to VISA power supply...")
        return None

'''
Turns on the BK power supply
Parameters: 
    psu: A PyVISA object containing the initialized power supply
    psu_wait: The time to wait for the power supply to turn on
Returns:
    True if successfully turned PSU on, None if PSU not successfully turned on
'''
def set_psu_on(psu, psu_wait=PSU_DELAY_TIME):
    global PSU_IS_ON_NOW
    if (PSU_IS_ON_NOW == 1):
        print("PSU already on")
        return True
    else:
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
            PSU_IS_ON_NOW = 1
            return True
        except Exception as e:
            print("ERROR: couldn't turn on VISA power supply...")
            PSU_IS_ON_NOW = 0 # undetermined
            return None

'''
Turns off the BK power supply. Will not be successful if the PSU object has already been closed.
Parameters:
    psu: A PyVISA object containing the initialized power supply
    psu_wait: The time to wait for the power supply to turn off
Returns:
    True if successfully turned PSU off, False if PSU not successfully turned off
NOTE: remember to run 'psu.close()' when done with the PSU
'''
def set_psu_off(psu, psu_wait=PSU_DELAY_TIME):
    global PSU_IS_ON_NOW
    if (PSU_IS_ON_NOW == -1):
        print("PSU already off")
        return True
    else:
        print("Turning PSU off...")
        try:
            psu.write('OUTP:ALL 0')
            time.sleep(psu_wait)
            print("PSU off!")
            PSU_IS_ON_NOW = -1
            return True
        except Exception as e:
            print("ERROR: couldn't turn off VISA power supply...")
            PSU_IS_ON_NOW = 0 # undetermined
            return None

'''
Writes (or tries) specified data to the serial port.
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    byte: Data payload to send over serial
    delay: Amount of time to wait after writing serial command
Returns: None
'''
def serial_write_with_delay(ser, byte, delay=SERIAL_DELAY_TIME):
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
def inst_write_with_delay(inst, writeString, delay=DMM_DELAY_TIME):
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
def inst_query_with_delay(inst, queryString, delay=DMM_DELAY_TIME):
    val = inst.query(queryString)
    time.sleep(delay)
    return val

'''
Shuts down, safely disconnects from equipment, and exits the program if specified
Parameters:
    ser:  Serial object that has been initialized (i.e. the Arduino)
    inst: DMM PyVISA object that has been initialized
    psu:  PSU PyVisa object that has been initialized
    exit_program: True to quit program, False (default) to continue running
    using_psu: True (default) to also shut down/disconnect PSU, False to skip PSU stuff
Returns: None
'''
def shutdown_equipment(ser, inst, psu, exit_program=False, using_psu=USING_USB_PSU):
    if (ser is not None):
        ser.close()
        print("Disconnected tester")
    else:
        print("Tester not initialized")
    if (inst is not None):
        inst.close()
        print("Disconnected DMM")
    else:
        print("DMM not initialized")
    if (using_psu and (psu is not None)):
        set_psu_off(psu)
        psu.close()
        print("Disconnected PSU")
    else:
        print("PSU not initialized")
    if (exit_program):
        print("Exiting program now...")
        sys.exit(0)

'''
Initializes and returns tuple with hardware and tester serial number
Tries to setup hardware using dictionary of known tester hardware setups, or manual input,
until hardware is properly initialized
Returns hardware-- Arduino (serial), DMM (VISA), and PSU (VISA) objects-- and a tester hardware # (string)
Parameters:
    rm:                         A PyVISA resource manager object (rm)
    tester_hw_config_list_in:   A list of dictionaries with tester hardware config options,
                                by default TESTER_HW_CONFIG_LIST in tester_hw_configs.py
                                Parameters: "tester_name", "serial_port",
                                "dmm_serial_string", "psu_serial_string"
    array_connection_list_in:   A list of interfaces to the array (strings), i.e. probe card,
                                ZIF connector, or other interface,
                                by default ARRAY_CONNECTION_LIST
    using_usb_psu_in:           True if USB PSU should be set up, False if PSU shouldn't be setup
Returns: A tuple with the following:
    ser: Initialized PySerial object representing the tester's Arduino
    dmm: Initialized PyVISA object representing the multimeter
    psu: Initialized PyVISA object representing the power supply, or None if using_usb_psu_in is false
    tester_serial_string: Serial number string, (hardware config name) + "__" + (array connection type)
'''
def init_equipment_with_config(rm, tester_hw_config_list_in=TESTER_HW_CONFIG_LIST,
                               array_connection_list_in=ARRAY_CONNECTION_LIST,
                               using_usb_psu_in=USING_USB_PSU):
    ser = None
    inst = None
    psu = None
    try:
        # Attempt to connect using default configuration -- first element of tester_hw_config_list_in
        # in tester_hw_configs.py
        config_default = tester_hw_config_list_in[0]
        config_name = config_default["tester_name"]
        ser = init_helper(init_serial(config_default["serial_port"]), False)
        inst = init_helper(init_multimeter(rm, config_default["dmm_serial_string"]), False)
        if (using_usb_psu_in):
            psu = init_helper(init_psu(rm, config_default["psu_serial_string"]))

        # If default configuration successfully connects,
        # - selecting 'enter' (default) will use that configuration
        # - selecting 'N' will allow selecting of another configuration
        #   or manually specifying the hardware
        use_custom_config = False
        success_config = (ser is not None) and (inst is not None) and (not (using_usb_psu_in and psu is None))
        if (success_config):
            valid_responses = {"": "continue with default tester config", "N": "specify custom tester config"}
            override = query_valid_response(valid_responses)
            if (override.lower() == "n"):
                shutdown_equipment(ser, inst, psu, False, using_usb_psu_in)
                ser = None
                inst = None
                psu = None
                use_custom_config = True

        # If default config fails to connect OR user specifies manual config
        if ((not success_config) or use_custom_config):
            print("")
            if (success_config):
                success_config = False
            if ser is None:
                print("Unable to connect to default port")
            valid_responses = {}
            # Loop until serial port, DMM, and PSU if applicable, are all successfully connected
            # Ask user to either use a predefined hardware setup or specify a manual config
            while (not success_config):
                for i in range(len(tester_hw_config_list_in)):
                    valid_responses[str(i)] = tester_hw_config_list_in[i]["tester_name"]
                valid_responses["M"] = "Set manual config"
                print("Select the tester config from below.")
                config_id = query_valid_response(valid_responses)
                # If the user specifies manual config, input the serial port and DMM/PSU ID
                # and try to connect
                if (config_id.lower() == "m"):
                    config_name = "Manual"
                    serial_port_in = input("Enter serial port (e.g. COMx): ")
                    print("Sample VISA serial number: USB0::0x0000::0x0000::00000000::INSTR")
                    dmm_serial_in = input("Enter DMM VISA serial number: ")
                    ser = init_helper(init_serial(serial_port_in), False)
                    inst = init_helper(init_multimeter(rm, dmm_serial_in), False)
                    if (using_usb_psu_in):
                        psu_serial_in = input("Enter PSU VISA serial number: ")
                        psu = init_helper(init_psu(rm, psu_serial_in), False)
                # Else, try to connect to the selected config
                else:
                    config_id_index = int(config_id)
                    config_name = tester_hw_config_list_in[config_id_index]["tester_name"]
                    print("Using selected tester config: " + config_name)
                    ser = init_helper(init_serial(tester_hw_config_list_in[config_id_index]["serial_port"]), False)
                    inst = init_helper(init_multimeter(rm, tester_hw_config_list_in[config_id_index]["dmm_serial_string"]), False)
                    psu = None
                    if (using_usb_psu_in):
                        psu = init_helper(init_psu(rm, tester_hw_config_list_in[config_id_index]["psu_serial_string"]), False)
                success_config = (ser is not None) and (inst is not None) and (not (using_usb_psu_in and psu is None))
                if (not success_config):
                    if (ser is not None):
                        ser.close()
                        ser = None
                    if (inst is not None):
                        inst.close()
                        inst = None
                    if (psu is not None):
                        set_psu_off(psu)
                        psu.close()
                        psu = None
                    print("Could not connect with selected tester config\n")

        print("Using tester config: " + config_name)
        init_helper(set_psu_on(psu, PSU_DELAY_TIME))
        # Query user for array connection type, e.g. probe card, ZIF, or something else
        array_connection_default = array_connection_list_in[0]
        valid_responses = {}
        valid_responses[""] = array_connection_default + " (default)"
        for i in range(1, len(array_connection_list_in)):
            valid_responses[i] = array_connection_list_in[i]
        print("\nSelect array connection type")
        result_index = query_valid_response(valid_responses)
        result_index = 0 if result_index == "" else int(result_index)
        array_connection = array_connection_list_in[result_index]
        print("Selected " + array_connection)

        tester_serial_string = config_name + "__" + array_connection
        print("Tester Serial Number: " + tester_serial_string)
        return (ser, inst, psu, tester_serial_string)
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting program...")
        shutdown_equipment(ser, inst, psu, True, using_usb_psu_in)

# Test routines
'''
Two-dimensional test measures capacitance between column and one other node 
specified in the 'test_mode_in' parameter (linked to the CAP_FN_DICT dictionary).
Test measures the difference between (row TFT on cap) - (row TFT off cap)
by first iterating through row TFT's and toggling them to +15V (on) or -8V (off).
Inside, it iterates through all the columns and measures capacitance between column[x]
and the specified node (e.g. PZBIAS)
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
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
    dut_name_full = ""
    if (dut_stage_raw == ""):
        dut_name_full = dut_name_raw
    else:
        dut_name_full = dut_name_raw + "_" + dut_stage_raw
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
        inst_write_with_delay(inst, 'sens:cap:rang ' + meas_range, DMM_DELAY_TIME_CAP)
        inst_query_with_delay(inst, 'meas:cap?', DMM_DELAY_TIME_CAP)
        print("Sensor " + test_name + " Check Running...")
        print_progress_bar(0, 16, suffix = "Row 0/16", length = 16)
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
                serial_write_with_delay(ser, b'Z', SERIAL_DELAY_TIME_CAP)                         # sets all mux switches to high-Z mode
                serial_write_with_delay(ser, CAP_FN_DICT[test_name], SERIAL_DELAY_TIME_CAP)       # pre-sets the secondary muxes to the right state for cap measurement
                serial_write_with_delay(ser, b'R', SERIAL_DELAY_TIME_CAP)                         # sets primary mux to row write mode
                serial_write_with_delay(ser, bytes(hex(row)[2:], 'utf-8'), SERIAL_DELAY_TIME_CAP) # sets row address
                serial_write_with_delay(ser, b'L', SERIAL_DELAY_TIME_CAP)                         # sets primary mux to column write mode
                serial_write_with_delay(ser, bytes(hex(col)[2:], 'utf-8'), SERIAL_DELAY_TIME_CAP) # sets column address
                serial_write_with_delay(ser, b'I', SERIAL_DELAY_TIME_CAP)                         # sets primary row mux to "binary counter disable mode", which sets all TFT's off (to -8V)

                tft_off_meas = float(inst_query_with_delay(inst, 'meas:cap?', DMM_DELAY_TIME_CAP))

                serial_write_with_delay(ser, b'Z', SERIAL_DELAY_TIME_CAP)                         # sets all mux switches to high-Z mode
                serial_write_with_delay(ser, CAP_FN_DICT[test_name], SERIAL_DELAY_TIME_CAP)       # pre-sets the secondary muxes to the right state for cap measurement
                serial_write_with_delay(ser, b'R', SERIAL_DELAY_TIME_CAP)                         # sets primary mux to row write mode
                serial_write_with_delay(ser, bytes(hex(row)[2:], 'utf-8'), SERIAL_DELAY_TIME_CAP) # sets row address
                serial_write_with_delay(ser, b'L', SERIAL_DELAY_TIME_CAP)                         # sets primary mux to column write mode
                serial_write_with_delay(ser, bytes(hex(col)[2:], 'utf-8'), SERIAL_DELAY_TIME_CAP) # sets column address
                serial_write_with_delay(ser, b'P', SERIAL_DELAY_TIME_CAP)                         # sets primary row mux to capacitance check mode

                tft_on_meas = float(inst_query_with_delay(inst, 'meas:cap?', DMM_DELAY_TIME_CAP))
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
            print_progress_bar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    serial_write_with_delay(ser, b'Z', SERIAL_DELAY_TIME_CAP)
    out_array_delta = np.delete(out_array_delta, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name_full + "_" + test_name.lower() + "_alt_delta.csv", out_array_delta, delimiter=",", fmt="%s")
    out_array_on = np.delete(out_array_on, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name_full + "_" + test_name.lower() + "_alt_on.csv", out_array_on, delimiter=",", fmt="%s")
    out_text = "Ran " + test_name + " test w/ " + str(meas_range) + " F range"
    out_text += "\nNo. of sensors inside bounds: " + str(num_in_threshold)
    out_text += "\nNo. of sensors below lower threshold of " + str(cap_bound_vals[0]) + "pF: " + str(num_below_threshold)
    out_text += "\nNo. of sensors above upper threshold of " + str(cap_bound_vals[1]) + "pF: " + str(num_above_threshold) + "\n"
    print("\n" + out_text)
    return(num_in_threshold, out_text + "\n")

'''
Two-dimensional test that measures continuity at every intersection, e.g. row to column.
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
    path: Path to save output files to
    dut_name: Full name of device + stage of test
    test_id: Test mode to run, one of the ones specified in CONT_DICT_TWO_DIM
    start_dim1: Dim1 (e.g. row) # to start iterating through (typically 0)
    start_dim2: Dim2 (e.g. col) # to start iterating through (typically 0)
    end_dim1: Dim1 (e.g. row) # to end iterating through (typically 16)
    end_dim2: Dim2 (e.g. col) # to end iterating through (typically 16)
    res_threshold: Threshold below which a measurement is considered a short
Returns:
    Tuple, with following parameters:
        Total number of shorts detected
        Output text (to be appended to summary file)
'''
def test_cont_two_dim(ser, inst, path, dut_name, test_id, start_dim1=0, start_dim2=0,
                      end_dim1=16, end_dim2=16, res_threshold = RES_SHORT_THRESHOLD_ROWCOL):
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
    time.sleep(SERIAL_DELAY_TIME)
    out_text += "Sensor " + test_name + " Detection Running..."
    print(out_text)
    out_text += "\n"

    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([dim1_name + " Index", dim2_name + " Index", dim1_name + " Res. to " + dim2_name + " (ohm)"])
        print_progress_bar(0, 16, suffix = dim1_name + " 0/16", length = 16)
        time.sleep(SERIAL_DELAY_TIME)
        for dim1_cnt in range(start_dim1, end_dim1):
            for dim2_cnt in range(start_dim2, end_dim2):
                serial_write_with_delay(ser, b'Z')                              # set row switches to high-Z and disable muxes
                serial_write_with_delay(ser, CONT_DICT_TWO_DIM[test_name][0])   # set secondary mux to specified input mode
                serial_write_with_delay(ser, CONT_DICT_TWO_DIM[test_name][1])   # set mode to dim1 write mode
                serial_write_with_delay(ser, bytes(hex(dim1_cnt)[2:], 'utf-8')) # write dim1 index
                serial_write_with_delay(ser, CONT_DICT_TWO_DIM[test_name][2])   # set mode to dim2 write mode
                serial_write_with_delay(ser, bytes(hex(dim2_cnt)[2:], 'utf-8')) # write dim2 index
                serial_write_with_delay(ser, b'O')                              # set mode to continuity check
                val = float(inst_query_with_delay(inst, 'meas:res?'))           # read resistance measurement
                out_array[(16-dim1_cnt)+1][dim2_cnt+1] = val
                if (val < res_threshold):
                    num_shorts += 1
                writer.writerow([str(dim1_cnt+1), str(dim2_cnt+1), val])
            print_progress_bar(dim1_cnt+1, 16, suffix = dim1_name + " " + str(dim1_cnt+1) + "/16", length = 16)
    serial_write_with_delay(ser, b'Z')                                          # set all mux enables + mux channels to OFF
    out_array = np.delete(out_array, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt.csv", out_array, delimiter=",", fmt="%s")
    num_shorts_text = test_name + " yielded " + str(num_shorts) + " short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    out_array = np.delete(out_array, (0), axis=1)
    out_array = out_array[1:]
    if (num_shorts > 0):
        for dim1_cnt in range(out_array.shape[0]):
            for dim2_cnt in range(out_array.shape[1]):
                if (float(out_array[dim1_cnt][dim2_cnt]) > res_threshold):
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
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
    path: Path to save output files to
    dut_name: Full name of device + stage of test
    test_id: Test mode to run, one of the ones specified in CONT_DICT_ONE_DIM
    start_ind: Dim1 (e.g. col) # to start iterating through (typically 0)
    end_ind: Dim1 (e.g. col) # to end iterating through (typically 16)
    res_threshold: Threshold below which a measurement is considered a short
Returns:
    Tuple, with following parameters:
        Total number of shorts detected
        Output text (to be appended to summary file)
'''
def test_cont_one_dim(ser, inst, path, dut_name, test_id, start_ind=0,
                      end_ind=16, res_threshold=RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
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
    time.sleep(SERIAL_DELAY_TIME)
    out_text += "Sensor " + test_name + " Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([primary_mux_state + " Index", test_name + " (ohm)"])
        print_progress_bar(0, 16, suffix = primary_mux_state + " 0/16", length = 16)
        for ind in range(start_ind, end_ind):
            serial_write_with_delay(ser, b'Z')                     # set row switches to high-Z and disable muxes
            serial_write_with_delay(ser, CONT_DICT_ONE_DIM[test_name][0]) # set secondary mux to appropriate mode
            serial_write_with_delay(ser, CONT_DICT_ONE_DIM[test_name][1]) # set write mode to appropriate
            serial_write_with_delay(ser, bytes(hex(ind)[2:], 'utf-8'))    # write the row address to the tester
            serial_write_with_delay(ser, b'O')                     # set mode to continuity check mode
            val = float(inst_query_with_delay(inst, 'meas:res?'))  # read resistance from the meter
            writer.writerow([str(ind+1), val])                  # write value to CSV
            if (val < res_threshold):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            print_progress_bar(ind+1, 16, suffix = primary_mux_state + " " + str(ind+1) + "/16", length = 16)
    serial_write_with_delay(ser, b'Z')                             # set all mux enables + mux channels to OFF
    num_shorts_text = test_name + " yielded " + str(num_shorts) + " short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

'''
Measures continuity across two nodes, e.g. PZBIAS to SHIELD
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
    path: Path to save output files to
    dut_name: Full name of device + stage of test
    test_id: Test mode to run, one of the ones specified in CONT_DICT_NODE
    res_threshold: Threshold below which a measurement is considered a short
Returns:
    Tuple, with following parameters:
        Resistance across two nodes
        Output text (to be appended to summary file)
'''
def test_cont_node(ser, inst, path, dut_name, test_id, res_threshold=RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
    test_name = test_id.upper()
    if (test_name not in CONT_DICT_NODE):
        out_text = "ERROR: 1D Node resistance check " + test_name + " not valid...\n"
        print(out_text)
        return (-1, out_text)
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out_text = "Sensor " + test_name + " Detection Running..."
    out_text += "\n"
    val = 0

    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        file.write(test_name.lower() + " (ohms)\n")
        serial_write_with_delay(ser, b'Z')                      # set rst switches to high-Z and disable muxes
        serial_write_with_delay(ser, CONT_DICT_NODE[test_id])   # set secondary mux to mode specified in input
        serial_write_with_delay(ser, b'O')                      # enable tester outputs
        val = float(inst_query_with_delay(inst, 'meas:res?'))   # read resistance from the meter
        file.write(str(val))
        out_text += f"{val:,}"  + " ohms"
        time.sleep(DMM_DELAY_TIME)
        file.close()
    serial_write_with_delay(ser, b'Z')                               # set rst switches to high-Z and disable muxes
    if (val > res_threshold):
        out_text += "\n" + test_name + " is not shorted\n"
    else:
        out_text += "\n" + test_name + " is shorted\n"
    print(out_text)
    return (val, out_text)

'''
Measures continuity between column and PZBIAS while toggling the row TFT's on and off (to +15V and -8V)
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
    path: Path to save output files to
    dut_name: Full name of device + stage of test    
    start_row: Row # to start iterating through (typically 0)
    start_col: Col # to start iterating through (typically 0)
    end_row: Row # to end iterating through (typically 16)
    end_col: Col # to end iterating through (typically 16)
    res_threshold: Threshold below which a measurement is considered a short
Returns:
    Tuple, with following parameters:
        Total number of shorts detected
        Output text (to be appended to summary file)
'''
def test_cont_col_to_pzbias_tfts_on(ser, inst, path, dut_name, start_row=0, end_row=16,
                                    start_col=0, end_col=16, res_threshold=RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
    test_name = "CONT_COL_TO_PZBIAS_TFTS_ON"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    out_text = ""

    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(SERIAL_DELAY_TIME)
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
        print_progress_bar(0, 16, suffix = "Row 0/16", length = 16)
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                serial_write_with_delay(ser, b'Z')                 # set row switches to high-Z and disable muxes
                serial_write_with_delay(ser, b'W')                 # set secondary mux to col/PZBIAS mode
                serial_write_with_delay(ser, b'R')                 # set mode to row write mode
                serial_write_with_delay(ser, bytes(hex(row)[2:], 'utf-8'))         # write row index
                serial_write_with_delay(ser, b'L')                 # set mode to column write mode
                serial_write_with_delay(ser, bytes(hex(col)[2:], 'utf-8'))         # write column index
                serial_write_with_delay(ser, b'P')                 # "ON" measurement - cap. check mode puts row switches in +15/-8V mode
                tft_on_meas = float(inst_query_with_delay(inst, 'meas:res?'))      # read mux on measurement
                if (tft_on_meas < res_threshold):
                    num_shorts += 1
                out_array[(16-row)+1][col+1] = tft_on_meas
                writer.writerow([str(row+1), str(col+1), tft_on_meas]) # appends to CSV with 1 index
                time.sleep(SERIAL_DELAY_TIME)
            print_progress_bar(row + 1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    serial_write_with_delay(ser, b'Z')                             # set all mux enables + mux channels to OFF
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
                if (float(out_array[row][col]) > res_threshold):
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
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    start_rst: Rst # to start iterating through (typically 0)
    end_rst: Rst # to end iterating through (typically 16)
Returns: none
'''
def test_reset_sweep(ser, start_rst=0, end_rst=16):
    print_progress_bar(0, 16, suffix = "Reset 0/16", length = 16)
    for i in range(start_rst, end_rst):
        serial_write_with_delay(ser, b'Z')
        serial_write_with_delay(ser, b'T')
        serial_write_with_delay(ser, bytes(hex(i)[2:], 'utf-8'))
        serial_write_with_delay(ser, b'S')
        # do stuff here
        print_progress_bar(i+1, 16, suffix = "Reset " + str(i+1) + "/16", length = 16)
        time.sleep(SERIAL_DELAY_TIME)
    serial_write_with_delay(b'Z') # set all mux enables + mux channels to OFF
    return(0, "")

'''
Interactive function that helps with alignment of flex presser/probe card fixtures to the die
to ensure proper loopback connectivity. Beeps one way (loop1_name) if only LoopA makes contact,
beeps another way (loop2_name) if only LoopB makes contact, and beeps a third way (both_loops_name)
when both loopbacks make contact
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
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
def test_loopback_resistance(ser, inst, num_counts=10, loop1_name=LOOP1_SOUND_FILE_DEFAULT,
                             loop2_name=LOOP2_SOUND_FILE_DEFAULT,
                             both_loops_name=BOTH_LOOPS_SOUND_FILE_DEFAULT, silent=SILENT_MODE_DEFAULT,
                             res_threshold=RES_SHORT_THRESHOLD_ROWCOL):
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
        time.sleep(SERIAL_DELAY_TIME)
        val1 = float(inst.query('meas:res?'))
        val1_str = "{:.4e}".format(val1)
        time.sleep(DMM_DELAY_TIME)
        ser.write(b'*')                                  # set secondary mux to Loopback 2 mode
        time.sleep(SERIAL_DELAY_TIME)
        val2 = float(inst.query('meas:res?'))
        val2_str = "{:.4e}".format(val2)
        time.sleep(DMM_DELAY_TIME)
        print("LOOP1 OHM " + val1_str + " LOOP2 OHM " + val2_str, end='\r')
        if (val1 < res_threshold and val2 < res_threshold):
            if not silent:
                both_loops.play()
            time.sleep(0.5)
            count += 1
        elif (val1 < res_threshold):
            if not silent:
                loop1.play()
            time.sleep(0.25)
        elif (val2 < res_threshold):
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
Measures Loopback 1 resistance
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
Returns:
    Tuple containing:
        Loopback 1 resistance (float)
        String text output
'''
def test_cont_loopback_one(ser, inst):
    val = 0
    out_text = "Loopback 1 resistance: "
    inst.write('sens:res:rang 10E3')                 # set resistance measurement range to 10Kohm
    time.sleep(DMM_DELAY_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(SERIAL_DELAY_TIME)
    ser.write(b'&')                                  # set secondary mux to Loopback 1 mode
    time.sleep(SERIAL_DELAY_TIME)
    val = float(inst.query('meas:res?'))             # read resistance from the meter
    out_text += f"{val:,}" + " ohms"
    time.sleep(DMM_DELAY_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(SERIAL_DELAY_TIME)
    inst.write('sens:res:rang 100E6')                # set resistance measurement range back to 100 MOhm
    time.sleep(DMM_DELAY_TIME)
    print(out_text)
    return(val, out_text)

'''
Measures Loopback 2 resistance
***PREREQUISITE: Power supply to tester boards MUST be on!
Parameters:
    ser: PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
Returns:
    Tuple containing:
        Loopback 2 resistance (float)
        String text output
'''
def test_cont_loopback_two(ser, inst):
    val = 0
    out_text = "Loopback 2 resistance: "
    inst.write('sens:res:rang 10E3')                 # set resistance measurement range to 10Kohm
    time.sleep(DMM_DELAY_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(SERIAL_DELAY_TIME)
    ser.write(b'*')                                  # set secondary mux to Loopback 2 mode
    time.sleep(SERIAL_DELAY_TIME)
    val = float(inst.query('meas:res?'))             # read resistance from the meter
    out_text += f"{val:,}" + " ohms"
    time.sleep(DMM_DELAY_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(SERIAL_DELAY_TIME)
    inst.write('sens:res:rang 100E6')                # set resistance measurement range back to 100 MOhm
    time.sleep(DMM_DELAY_TIME)
    print(out_text)
    return(val, out_text)

'''
Run capacitance and TFT tests for 1T arrays
Will turn on the power supply if not already on, and turn it off when done.
Parameters:
    ser:  PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
    psu:  PyVISA object that has been initialized (i.e. the PSU in this case)
    path: Path to save the output files for each test
    dut_name_raw: Raw name of the DUT (e.g. E2412-001-007-D2_T1)
    dut_stage_raw: Stage of assembly in plaintext (e.g. Post_Flex_Bond_ETest)
    dut_type: If the device is a backplane, sensor array, or sensor module    
    using_usb_psu_in: True if USB PSU should be set up, False if PSU shouldn't be setup
Returns: a tuple with the following:
    output_payload_gsheets_dict: A dictionary with key/value pairs for each test output,
                                 intended to update a database like the GSheets
    out_string: A string with each test output summary on its own line, intended for summary text file
'''
def test_cap_tft_array_1t(ser, inst, psu, path, dut_name_raw, dut_stage_raw, dut_type,
                          using_usb_psu_in=USING_USB_PSU):
    global PSU_IS_ON_NOW
    dut_name_full = dut_name_raw + "_" + dut_stage_raw
    print("Running cap and TFT ON continuity tests...")
    print("Tests starting at " + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
    if (using_usb_psu_in and PSU_IS_ON_NOW != 1):
        set_psu_on(psu)
    valid_responses = {'': "run cap test with default 1nF range", 1: "run cap test with 10nF range"}
    test_selection_raw = query_valid_response(valid_responses)
    meas_range_input = '1e-9'
    if (test_selection_raw == "1"):
        meas_range_input = '1e-8'
        print("Running cap test with new 10nF range...\n")
    else:
        meas_range_input = '1e-9'
        print("Running cap test with default 1nF range...\n")
    test_cap_out = test_cap(ser, inst, path, dut_name_raw, dut_stage_raw,
                            "CAP_COL_TO_PZBIAS", dut_type, meas_range_input)
    test_cont_col_to_pzbias_tfts_on_out = test_cont_col_to_pzbias_tfts_on(ser, inst, path, dut_name_full)

    out_string = test_cap_out[1]
    out_string += test_cont_col_to_pzbias_tfts_on_out[1]
    output_payload_gsheets_dict["Cap Col to PZBIAS (# pass)"] = test_cap_out[0]
    output_payload_gsheets_dict["Col to PZBIAS with TFT's ON (# shorts)"] = test_cont_col_to_pzbias_tfts_on_out[0]
    if (using_usb_psu_in):
        set_psu_off(psu)
    return (output_payload_gsheets_dict, out_string)
'''
Run full panel of continuity tests for 1T arrays
Will turn on the power supply if not already on, and turn it off when done.
Parameters:
    ser:  PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
    psu:  PyVISA object that has been initialized (i.e. the PSU in this case)
    path: Path to save the output files for each test
    dut_name_full: name of the device under test
    using_usb_psu_in: True if USB PSU should be set up, False if PSU shouldn't be setup
Returns: a tuple with the following:
    output_payload_gsheets_dict: A dictionary with key/value pairs for each test output,
                                 intended to update a database like the GSheets
    out_string: A string with each test output summary on its own line, intended for summary text file
    has_shorts: Boolean, true if any of the tests yield shorts with resistance below threshold
'''
def test_cont_array_1t(ser, inst, psu, path, dut_name_full, using_usb_psu_in=USING_USB_PSU):
    global PSU_IS_ON_NOW
    if (using_usb_psu_in and PSU_IS_ON_NOW != 1):
        set_psu_on(psu)
    print("\nTests starting at " + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
    cont_row_to_column = test_cont_two_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_COL")
    cont_row_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_PZBIAS")
    cont_row_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_SHIELD")
    cont_col_to_pzbias = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_PZBIAS")
    cont_col_to_shield = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_SHIELD")
    cont_shield_to_pzbias = test_cont_node(ser, inst, path, dut_name_full, "CONT_SHIELD_TO_PZBIAS")

    out_string = cont_row_to_column[1] + "\n"
    out_string += cont_row_to_pzbias[1] + "\n"
    out_string += cont_row_to_shield[1] + "\n"
    out_string += cont_col_to_pzbias[1] + "\n"
    out_string += cont_col_to_shield[1] + "\n"
    out_string += cont_shield_to_pzbias[1]

    output_payload_gsheets_dict["Row to Col (# shorts)"]    = cont_row_to_column[0]
    output_payload_gsheets_dict["Row to PZBIAS (# shorts)"] = cont_row_to_pzbias[0]
    output_payload_gsheets_dict["Row to SHIELD (# shorts)"] = cont_row_to_shield[0]
    output_payload_gsheets_dict["Col to PZBIAS (# shorts)"] = cont_col_to_pzbias[0]
    output_payload_gsheets_dict["Col to SHIELD (# shorts)"] = cont_col_to_shield[0]
    output_payload_gsheets_dict["SHIELD to PZBIAS (ohm)"]   = cont_shield_to_pzbias[0]
    has_shorts = cont_row_to_column[0]>0 or cont_row_to_pzbias[0]>0 or cont_col_to_pzbias[0]>0 or cont_row_to_shield[0]>0 or cont_col_to_shield[0]>0 or cont_shield_to_pzbias[0]=="FAIL"
    if (using_usb_psu_in):
        set_psu_off(psu)
    return (output_payload_gsheets_dict, out_string, has_shorts)

'''
Run full panel of continuity tests for 3T arrays
Will turn on the power supply if not already on, and turn it off when done.
Parameters:
    ser:  PySerial object that has been initialized to the Arduino's serial port
    inst: PyVISA object that has been initialized (i.e. the DMM in this case)
    psu:  PyVISA object that has been initialized (i.e. the PSU in this case)
    path: Path to save the output files for each test
    dut_name_full: name of the device under test
    using_usb_psu_in: True if USB PSU should be set up, False if PSU shouldn't be setup
Returns: a tuple with the following:
    output_payload_gsheets_dict: A dictionary with key/value pairs for each test output,
                                 intended to update a database like the GSheets
    out_string: A string with each test output summary on its own line, intended for summary text file
'''
def test_cont_array_3t(ser, inst, psu, path, dut_name_full, using_usb_psu_in=USING_USB_PSU):
    global PSU_IS_ON_NOW
    if (using_usb_psu_in and PSU_IS_ON_NOW != 1):
        set_psu_on(psu)
    print("\nTests starting at " + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
    cont_row_to_column    = test_cont_two_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_COL")
    cont_row_to_pzbias    = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_PZBIAS")
    cont_row_to_shield    = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_ROW_TO_SHIELD")
    cont_col_to_pzbias    = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_PZBIAS")
    cont_col_to_shield    = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_SHIELD")
    cont_col_to_vdd       = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_VDD")
    cont_col_to_vrst      = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_COL_TO_VRST")
    cont_rst_to_column    = test_cont_two_dim(ser, inst, path, dut_name_full, "CONT_RST_TO_COL")
    cont_rst_to_shield    = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_RST_TO_SHIELD")
    cont_rst_to_pzbias    = test_cont_one_dim(ser, inst, path, dut_name_full, "CONT_RST_TO_PZBIAS")
    cont_vdd_to_shield    = test_cont_node(ser, inst, path, dut_name_full, "CONT_VDD_TO_SHIELD")
    cont_vdd_to_pzbias    = test_cont_node(ser, inst, path, dut_name_full, "CONT_VDD_TO_PZBIAS")
    cont_vrst_to_shield   = test_cont_node(ser, inst, path, dut_name_full, "CONT_VRST_TO_SHIELD")
    cont_vrst_to_pzbias   = test_cont_node(ser, inst, path, dut_name_full, "CONT_VRST_TO_PZBIAS")
    cont_shield_to_pzbias = test_cont_node(ser, inst, path, dut_name_full, "CONT_SHIELD_TO_PZBIAS")

    out_string = cont_row_to_column[1] + "\n"
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

    output_payload_gsheets_dict["Row to Col (# shorts)"]    = cont_row_to_column[0]
    output_payload_gsheets_dict["Row to PZBIAS (# shorts)"] = cont_row_to_pzbias[0]
    output_payload_gsheets_dict["Row to SHIELD (# shorts)"] = cont_row_to_shield[0]
    output_payload_gsheets_dict["Col to PZBIAS (# shorts)"] = cont_col_to_pzbias[0]
    output_payload_gsheets_dict["Col to SHIELD (# shorts)"] = cont_col_to_shield[0]
    output_payload_gsheets_dict["Col to Vdd (# shorts)"]    = cont_col_to_vdd[0]
    output_payload_gsheets_dict["Col to Vrst (# shorts)"]   = cont_col_to_vrst[0]
    output_payload_gsheets_dict["Rst to Col (# shorts)"]    = cont_rst_to_column[0]
    output_payload_gsheets_dict["Rst to SHIELD (# shorts)"] = cont_rst_to_shield[0]
    output_payload_gsheets_dict["Rst to PZBIAS (# shorts)"] = cont_rst_to_pzbias[0]
    output_payload_gsheets_dict["Vdd to SHIELD (ohm)"]      = cont_vdd_to_shield[0]
    output_payload_gsheets_dict["Vdd to PZBIAS (ohm)"]      = cont_vdd_to_pzbias[0]
    output_payload_gsheets_dict["Vrst to SHIELD (ohm)"]     = cont_vrst_to_shield[0]
    output_payload_gsheets_dict["Vrst to PZBIAS (ohm)"]     = cont_vrst_to_pzbias[0]
    output_payload_gsheets_dict["SHIELD to PZBIAS (ohm)"]   = cont_shield_to_pzbias[0]
    if (using_usb_psu_in):
        set_psu_off(psu)
    return (output_payload_gsheets_dict, out_string)

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
def get_creds(token_filename=TOKEN_FILE_DEFAULT, cred_filename=CRED_FILE_DEFAULT, scopes=SCOPES):
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
Helper function that checks if a passed-in value is an integer or something else
Parameters:
    value: The value to check
Returns:
    True if value is an integer, False otherwise
'''
def is_valid_int(value):
    try:
        int(value)
        return True
    except ValueError:
        return False

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
                val_raw = tft_type.split('-')[1][0]
                if (is_valid_int(val_raw)):
                    return int(val_raw)
            else:
                val_raw = tft_type.split('-')[0][0]
                if (is_valid_int(val_raw)):
                    return int(val_raw)
        else:
            print("Array not found in inventory!")
            return None
    except HttpError as err:
        print(err)
        return None

'''
Function that does a wildcard search in the inventory for a substring; in most cases this can be the
flex serial number for a sensor module. Only works for unique matches; multiple matches do not count.
It queries the spreadsheet DieID column ('A') and returns the full sensor name if a unique match is found;
otherwise, NoneType object is returned.
Parameters:
    creds:      Initialized Google Apps credential, with token.json initialized. Refer to 'main()' in
                'google_sheets_example.py' for initialization example
    array_id:   The query, can be a backplane, assembly, or module id, in the format 'E2421-002-001-E5_T1_R1-103'
    dieid_cols: The column in which to search for the query, by default column 'A'
    dieid_tfts: The column with the corresponding TFT count, by default column 'Q'
    spreadsheet_id: The Google Sheets spreadsheet ID, extracted from the URL (docs.google.com/spreadsheets/d/***)
    id_sheet_name : The name of the sheet to search in for array_id, by default set by global variable
Returns:
    String with full sensor ID of the match, or NoneType object if not found/error
'''
def get_array_full_name(creds, search_string, dieid_cols='A', flexid_cols='AK',
                        spreadsheet_id=SPREADSHEET_ID, id_sheet_name=ID_SHEET_NAME):
    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        # Define the range (A1 notation) to append the data at the end of the sheet
        range_name_dieid = f'{id_sheet_name}!' + dieid_cols + ':' + dieid_cols
        result_dieid = (
            sheet.values()
            .get(spreadsheetId=spreadsheet_id, range=range_name_dieid)
            .execute()
        )
        values_dieid = result_dieid.get("values", [])
        full_array_id = None
        i = 0
        match_count = 0
        for i in range(len(values_dieid)):
            if (len(values_dieid[i]) > 0):
                if (search_string.upper() in values_dieid[i][0].upper()):
                    # print("Found at index " + str(i))
                    full_array_id = values_dieid[i][0].upper()
                    match_count += 1
        if (match_count <= 0):
            print("Array not found in inventory!")
            return None
        elif (match_count > 1):
            print("Duplicate matches found!")
            return None
        return full_array_id.rstrip("_")
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
