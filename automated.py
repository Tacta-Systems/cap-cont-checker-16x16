'''
This program performs cap, continuity, or reset sweeps

Hardware requirements:
- Keithley DMM6500 benchtop multimeter (our current unit's S/N is 04611761)
- 16x16 Array, with or without flex attached
- For arrays without flex attached, probe station aligner that joins flex to sensor
- Assembled 00013+00014 tester boards
- 00013 secondary board with SMA cables soldered to it
- Arduino MEGA 2560 R3
  * 10x2pin socket - socket ribbon cable from Arduino P36/37 to GND
  * Male header pins, double length (Amazon B077N29TP5)
  * 14x plug to socket ribbon cable to secondary board
  
  *******************************************************************************************************
  *** RUNNING THE AUTOMATED_ARDUINO_CAP_CONT_CHECKER_16X16_NO_ACK CODE THAT DOES NOT REPLY VIA SERIAL ***
  *******************************************************************************************************

- BNC to SMA cable + BNC to banana plug

- Add more wires here as the test setup gets built

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
ser.port = "COM5"                  # COM3 hardcoded this as default value (on Maxwell's laptop) but can also prompt for the COM port
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
path = "G:\\Shared drives\\Sensing\\Testing\\" # old value is C:\Users\tacta\Desktop
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

# Have pyvisa handle line termination
inst.read_termination = '\n'

# Clear buffer and status
inst.write('*CLS')

# Set measurement ranges           CAP LIMIT SHOULD BE 1E_9
inst.write('sens:cap:rang 1E-9') # limits cap range to the smallest possible value
inst.write('sens:res:rang 100E6')# set resistance measurement range to 100 MOhm for 0.7uA test current, per
                                 # https://download.tek.com/document/SPEC-DMM6500A_April_2018.pdf


for port, desc, hwid in sorted(ports):
    list_of_ports.append(str(port))
    print("{}: {} [{}]".format(port, desc, hwid))

if (len(list_of_ports)) == 0:
    print("ERROR: No serial ports/Arduinos detected. Exiting in 5 seconds...")
    time.sleep(5)
    exit()

# Query user for the Arduino COM port, will run until valid state given
# Can comment out this section if running on one computer

'''
while True:
    try:
        port_in = input("Please select the Arduino COM port COM[x]: ").upper()
    except ValueError:
        print("Sorry, please select a valid port COM[x]")
        continue
    if (port not in list_of_ports):
        print("Sorry, please select a valid port COM[x]")
        continue
    else:
        break
ser.port = port_in
'''

try:
    ser.open()
    print("Connected to Arduino!")
except Exception as e:
    print(f"Error opening serial port: {e}")
    sys.exit(0)

print("\nSetup Instructions:\n" +
      "- If new array, probe loopbacks to ensure connection\n" +
      "- Connect multimeter (+) lead to secondary mux board ROW (+)/red wire\n" +
      "- Connect multimeter (-) lead to secondary mux board COL (+)/red wire\n" +
      "- Ensure power supply is ON\n")

loop_one_res = 0
while True:
    try:
        loop_one_res = float(input("Please enter the resistance (ohms) between Loopback 1A/1B: "))
    except ValueError:
        print("Sorry, please enter a numerical value")
        continue
    if (loop_one_res <= 0):
        print("Sorry, plese enter a value greater than 0")    
    else:
        break

loop_two_res = 0
while True:
    try:
        loop_two_res = float(input("Please enter the resistance (ohms) between Loopback 2A/2B: "))
    except ValueError:
        print("Sorry, please enter a numerical value")
        continue
    if (loop_two_res <= 0):
        print("Sorry, plese enter a value greater than 0")
    else:
        break
print("")

array_types = {
    0: "Backplanes",
    1: "Sensor Arrays\\16x16",
    2: "Sensor Modules"
}
array_type_raw = 0
while True:
    try:
        array_type_raw = int(input("Please enter array type--\n- 0 for backplanes\n- 1 for sensor arrays\n- 2 for sensor modules: "))
    except ValueError:
        print("Sorry, please enter a numerical value")
    if (array_type_raw not in list(array_types.keys())):
        print("Sorry, please enter a valid response")
        continue
    else:
        break
array_type = array_types[array_type_raw]
path += array_type + "\\"

dut_id_input = ""
while True:
    try:
        dut_id_input = input("Please enter the array ID (e.g. E2408-001-2-E2_T2): ")
    except ValueError:
        print("Sorry, array ID can't be blank")
        continue
    if (len(dut_id_input) < 1):
        print("Sorry, array ID can't be blank")
        continue
    else:
        break
if (os.path.exists(path + dut_id_input)):
    path += dut_id_input + "\\"
else:
    make_new_path = "Y"
    valid_responses = ["Y", "N"]
    while True:
        try:
            make_new_path = input("Are you sure you want to make a new directory? 'Y' or 'N': ")
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
                os.makedirs(path + "\\" + dut_id_input)
                path += dut_id_input + "\\"
            break

dut_stage_input = ""
if (array_type == "Sensor Modules"):
    while True:
        try:
            dut_stage_input = "_" + input("\nPlease enter the array stage of assembly (e.g. onglass): ")
        except ValueError:
            print("Sorry, array stage of assembly can't be blank")
            continue
        if (len(dut_stage_input) < 1):
            print("Sorry, array stage of assembly can't be blank")
            continue
        else:
            break


dut_name_input = dut_id_input + dut_stage_input
print("Test data for " + dut_id_input + " will save to path " + path + "\n")

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
- 'U' for writing secondary board to "row/col" output
- 'V' for writing secondary board to "row/PZBIAS" output
- 'W' for writing secondary board to "col/PZBIAS" output
- 'X' for writing secondary board to "row/SHIELD" output
- 'Y' for writing secondary board to "col/SHIELD" output
- 'M' for writing secondary board to "rst/PZBIAS" output
- 'N' for writing secondary board to "rst/SHIELD" output
- 'Q' for writing secondary board to "rst/col" output
'''

# TODO? implement string output of cap check as a returned value in the tuple
def test_cap_col_to_pzbias (dut_name=dut_name_input, meas_range='1e-9', start_row=0, start_col=0, end_row=16, end_col=16):
    test_name = "CAP_COL_TO_PZBIAS"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Row Index", "Column Index", "Cap Off Measurement (F)", "Cap On Measurement (F)", "Calibrated Measurement (F)"])
        inst.write('sens:cap:rang ' + meas_range)            # limits cap range to the smallest possible value
        time.sleep(DELAY_TIME)
        inst.query('meas:cap?')                              # set Keithley mode to capacitance measurement
        time.sleep(DELAY_TIME)
        print("Sensor Capacitance Check to PZBIAS Running...")
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
                ser.write(b'Z')                              # set row switches to high-Z and disable muxes
                time.sleep(DELAY_TIME)
                ser.write(b'W')                              # set secondary mux board to col/PZBIAS mode for cap measurement
                time.sleep(DELAY_TIME)
                ser.write(b'R')                              # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))      # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                              # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(DELAY_TIME)
                ser.write(b'I')                              # "OFF" measurement" - all row switches are held at -8V
                time.sleep(DELAY_TIME)
                tft_off_meas = float(inst.query('meas:cap?'))# read mux off measurement
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)        # TODO: see how small we can make this delay

                ser.write(b'Z')                              # set row switches to high-Z and disable muxes
                time.sleep(DELAY_TIME)
                ser.write(b'W')                              # set secondary mux board to col/PZBIAS mode for cap measurement
                time.sleep(DELAY_TIME)
                ser.write(b'R')                              # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))      # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                              # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(DELAY_TIME)
                ser.write(b'P')                              # "ON" measurement - cap. check mode puts row switches in +15/-8V mode
                time.sleep(DELAY_TIME)
                tft_on_meas = float(inst.query('meas:cap?')) # read mux on measurement
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)        # TODO: see how small we can make this delay
                tft_cal_meas = tft_on_meas - tft_off_meas
                out_array_delta[(16-row)+1][col+1] = tft_cal_meas*1e12
                out_array_on[(16-row)+1][col+1] = tft_on_meas*1e12
                writer.writerow([str(row+1), str(col+1), tft_off_meas, tft_on_meas, tft_cal_meas]) # appends to CSV with 1 index
                time.sleep(DELAY_TIME)
            printProgressBar(row + 1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                          # set all mux enables + mux channels to OFF
    out_array_delta = np.delete(out_array_delta, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt_delta.csv", out_array_delta, delimiter=",", fmt="%s")
    out_array_on = np.delete(out_array_on, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt_on.csv", out_array_on, delimiter=",", fmt="%s")
    print("")
    return(0, "Ran cap col to PZBIAS test w/ " + str(meas_range) + " F range\n")
 
# TODO? implement string output of cap check as a returned value in the tuple
def test_cap_col_to_shield (dut_name=dut_name_input, meas_range='1e-9', start_row=0, start_col=0, end_row=16, end_col=16):
    test_name = "CAP_COL_TO_SHIELD"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Row Index", "Column Index", "Cap Off Measurement (F)", "Cap On Measurement (F)", "Calibrated Measurement (F)"])
        inst.write('sens:cap:rang ' + meas_range)            # limits cap range to the smallest possible value
        time.sleep(DELAY_TIME)
        inst.query('meas:cap?')                              # set Keithley mode to capacitance measurement
        time.sleep(DELAY_TIME)
        print("Sensor Capacitance Check to SHIELD Running...")
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
                ser.write(b'Z')                              # set row switches to high-Z and disable muxes
                time.sleep(DELAY_TIME)
                ser.write(b'Y')                              # set secondary mux board to col/SHIELD mode for cap measurement
                time.sleep(DELAY_TIME)
                ser.write(b'R')                              # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))      # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                              # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(DELAY_TIME)
                ser.write(b'I')                              # "OFF" measurement" - all row switches are held at -8V
                time.sleep(DELAY_TIME)
                tft_off_meas = float(inst.query('meas:cap?'))# read mux off measurement
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)        # TODO: see how small we can make this delay

                ser.write(b'Z')                              # set row switches to high-Z and disable muxes
                time.sleep(DELAY_TIME)
                ser.write(b'Y')                              # set secondary mux board to col/SHIELD mode for cap measurement
                time.sleep(DELAY_TIME)
                ser.write(b'R')                              # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))      # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                              # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))      # write column index
                time.sleep(DELAY_TIME)
                ser.write(b'P')                              # "ON" measurement - cap. check mode puts row switches in +15/-8V mode
                time.sleep(DELAY_TIME)
                tft_on_meas = float(inst.query('meas:cap?')) # read mux on measurement
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)        # TODO: see how small we can make this delay
                tft_cal_meas = tft_on_meas - tft_off_meas
                out_array_delta[(16-row)+1][col+1] = tft_cal_meas*1e12
                out_array_on[(16-row)+1][col+1] = tft_on_meas*1e12
                writer.writerow([str(row+1), str(col+1), tft_off_meas, tft_on_meas, tft_cal_meas]) # appends to CSV with 1 index
                time.sleep(DELAY_TIME)
            printProgressBar(row + 1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                          # set all mux enables + mux channels to OFF
    out_array_delta = np.delete(out_array_delta, (0), axis=0)
    out_array_on = np.delete(out_array_on, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt_delta.csv", out_array_delta, delimiter=",", fmt="%s")
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt_on.csv", out_array_on, delimiter=",", fmt="%s")
    print("")
    return(0, "Ran cap col to SHIELD test w/ " + str(meas_range) + " F range\n")

def test_cont_row_to_column(dut_name=dut_name_input, start_row=0, start_col=0, end_row=16, end_col=16):
    test_name = "CONT_ROW_TO_COL"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    out_array = np.zeros((18, 17), dtype='U64')          # create string-typed numpy array
    out_array[1] = ["C" + str(i) for i in range(0, 17)]  # set cols of output array to be "C1"..."C16"
    for i in range(len(out_array)):
        out_array[len(out_array)-1-i][0] = "R" + str(i+1)# set rows of output array to be "R1"..."R16"
    # out_array[0][0] = "Continuity Detection Row to Column"
    # out_array[0][1] = dut_name
    # out_array[0][2] = dt.datetime.now()
    out_array[1][0] = "Resistance (ohm)"
    num_shorts = 0
    out_text = ""
    inst.query('meas:res?')
    time.sleep(DELAY_TIME)
    out_text += "Sensor Row to Col Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Row Index", "Column Index", "Row Res. to Col. (ohm)"])
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        time.sleep(DELAY_TIME)
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                time.sleep(DELAY_TIME)
                ser.write(b'Z')                                  # set row switches to high-Z and disable muxes
                time.sleep(DELAY_TIME)
                ser.write(b'U')                                  # set secondary mux to row/col mode
                time.sleep(DELAY_TIME)
                ser.write(b'R')                                  # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))          # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                                  # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))          # write column index
                time.sleep(DELAY_TIME)
                ser.write(b'O')                                  # set mode to continuity check
                time.sleep(DELAY_TIME)
                val = float(inst.query('meas:res?'))             # read resistance measurement
                out_array[(16-row)+1][col+1] = val
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)   # TODO: see how small we can make this delay
                if (val < RES_SHORT_THRESHOLD_ROWCOL):
                    num_shorts += 1
                writer.writerow([str(row+1), str(col+1), val])
            printProgressBar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                              # set all mux enables + mux channels to OFF
    out_array = np.delete(out_array, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt.csv", out_array, delimiter=",", fmt="%s")
    num_shorts_text = "There were " + str(num_shorts) + " row/col short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
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

def test_cont_row_to_pzbias(dut_name=dut_name_input, start_row=0, end_row=16):
    test_name = "CONT_ROW_TO_PZBIAS"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                              # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Row to PZBIAS Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Row Index", "Row Res. to PZBIAS (ohm)"])
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        for row in range(start_row, end_row):
            ser.write(b'Z')                                     # set row switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'V')                                     # set secondary mux to row/PZBIAS mode
            time.sleep(DELAY_TIME)
            ser.write(b'R')                                     # set mode to row write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(row)[2:], 'utf-8'))             # write the row address to the tester
            time.sleep(DELAY_TIME)
            ser.write(b'O')                                     # set mode to continuity check mode
            time.sleep(DELAY_TIME)
            val = float(inst.query('meas:res?'))                # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([str(row+1), val])                  # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            printProgressBar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                           # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " row/PZBIAS short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

def test_cont_col_to_pzbias(dut_name=dut_name_input, start_col=0, end_col=16):
    test_name = "CONT_COL_TO_PZBIAS"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Col to PZBIAS Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline="") as file:        
        writer = csv.writer(file)
        writer.writerow(["Col Index", "Col. Res. to PZBIAS (ohm)"])
        printProgressBar(0, 16, suffix = "Col 0/16", length = 16)
        for col in range(start_col, end_col):
            ser.write(b'Z')                                  # set row switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'W')                                  # set secondary board mode to col/PZBIAS
            time.sleep(DELAY_TIME)
            ser.write(b'L')                                  # set mode to column write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(col)[2:], 'utf-8'))          # write the column address to the tester
            time.sleep(DELAY_TIME)
            ser.write(b'O')                                  # set mode to continuity check mode
            time.sleep(DELAY_TIME)
            val = float(inst.query('meas:res?'))             # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([str(col+1), val])               # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            printProgressBar(col+1, 16, suffix = "Col " + str(col+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                              # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " col/PZBIAS short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

# TODO: implement tuple output of (arrayID, text output)
def test_cont_col_to_pzbias_tfts_on(dut_name=dut_name_input, start_row=0, end_row=16, start_col=0, end_col=16):
    test_name = "CONT_COL_TO_PZBIAS_TFTS_ON"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
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
                ser.write(b'Z')                                 # set row switches to high-Z and disable muxes
                time.sleep(DELAY_TIME)
                ser.write(b'W')                                 # set secondary mux to col/PZBIAS mode
                time.sleep(DELAY_TIME)
                ser.write(b'R')                                 # set mode to row write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(row)[2:], 'utf-8'))         # write row index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                                 # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))         # write column index
                time.sleep(DELAY_TIME)
                ser.write(b'P')                                 # "ON" measurement - cap. check mode puts row switches in +15/-8V mode
                time.sleep(DELAY_TIME)
                tft_on_meas = float(inst.query('meas:res?'))    # read mux on measurement
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)           # TODO: see how small we can make this delay
                if (tft_on_meas < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                    num_shorts += 1
                out_array[(16-row)+1][col+1] = tft_on_meas
                writer.writerow([str(row+1), str(col+1), tft_on_meas]) # appends to CSV with 1 index
                time.sleep(DELAY_TIME)
            printProgressBar(row + 1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                              # set all mux enables + mux channels to OFF
    time.sleep(DELAY_TIME)
    num_shorts_text = "There were " + str(num_shorts) + " col/PZBIAS with TFT's ON short(s) in array " + dut_name
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

def test_cont_row_to_shield(dut_name=dut_name_input, start_row=0, end_row=16):
    test_name = "CONT_ROW_TO_SHIELD"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Row to SHIELD Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Row Index", "Row Res. to SHIELD (ohm)"])
        printProgressBar(0, 16, suffix = "Row 0/16", length = 16)
        for row in range(start_row, end_row):
            ser.write(b'Z')                                  # set row switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'X')                                  # set secondary mux to row/SHIELD mode
            time.sleep(DELAY_TIME)
            ser.write(b'R')                                  # set mode to row write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(row)[2:], 'utf-8'))          # write the row address to the tester
            time.sleep(DELAY_TIME)
            ser.write(b'O')                                  # set mode to continuity check mode
            time.sleep(DELAY_TIME)
            val = float(inst.query('meas:res?'))             # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([str(row+1), val])               # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            printProgressBar(row+1, 16, suffix = "Row " + str(row+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                         # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " row/SHIELD short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

def test_cont_col_to_shield(dut_name=dut_name_input, start_col=0, end_col=16):
    test_name = "CONT_COL_TO_SHIELD"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Col to SHIELD Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Col Index", "Col. Res. to SHIELD (ohm)"])
        printProgressBar(0, 16, suffix = "Col 0/16", length = 16)
        for col in range(start_col, end_col):
            ser.write(b'Z')                                  # set row switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'Y')                                  # set secondary mux to col/SHIELD mode
            time.sleep(DELAY_TIME)
            ser.write(b'L')                                  # set mode to column write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(col)[2:], 'utf-8'))          # write the column address to the tester
            time.sleep(DELAY_TIME)
            ser.write(b'O')                                  # set mode to continuity check mode
            time.sleep(DELAY_TIME)
            val = float(inst.query('meas:res?'))             # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([str(col+1), val])               # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            printProgressBar(col+1, 16, suffix = "Col " + str(col+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                          # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " col/SHIELD short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

def test_reset_sweep(dut_name=dut_name_input, start_rst=0, end_rst=16):
    printProgressBar(0, 16, suffix = "Reset 0/16", length = 16)
    for i in range(start_rst, end_rst):
        ser.write(b'Z')
        time.sleep(DELAY_TIME)
        ser.write(b'T')
        time.sleep(DELAY_TIME)
        ser.write(bytes(hex(i)[2:], 'utf-8'))
        time.sleep(DELAY_TIME)
        ser.write(b'S')
        time.sleep(DELAY_TIME)
        # do stuff here
        printProgressBar(i+1, 16, suffix = "Reset " + str(i+1) + "/16", length = 16)
        time.sleep(DELAY_TIME)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                              # set all mux enables + mux channels to OFF
    return(0, "")

def test_cont_rst_to_column(dut_name=dut_name_input, start_rst=0, start_col=0, end_rst = 16, end_col = 16):
    test_name = "CONT_RST_TO_COL"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    out_array = np.zeros((18, 17), dtype='U64')          # create string-typed numpy array
    out_array[1] = ["C" + str(i) for i in range(0, 17)]  # set cols of output array to be "C1"..."C16"
    for i in range(len(out_array)):
        out_array[len(out_array)-1-i][0] = "Rst" + str(i+1)# set rows of output array to be "R1"..."R16"
    # out_array[0][0] = "Continuity Detection Row to Column"
    # out_array[0][1] = dut_name
    # out_array[0][2] = dt.datetime.now()
    out_array[1][0] = "Resistance (ohm)"
    num_shorts = 0
    out_text = ""
    inst.query('meas:res?')
    time.sleep(DELAY_TIME)
    out_text += "Sensor Rst to Col Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Rst Index", "Column Index", "Rst Res. to Col. (ohm)"])
        printProgressBar(0, 16, suffix = "Rst 0/16", length = 16)
        time.sleep(DELAY_TIME)
        for rst in range(start_rst, end_rst):
            for col in range(start_col, end_col):
                time.sleep(DELAY_TIME)
                ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
                time.sleep(DELAY_TIME)
                ser.write(b'Q')                                  # set secondary mux to row/col mode
                time.sleep(DELAY_TIME)
                ser.write(b'T')                                  # set mode to rst write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(rst)[2:], 'utf-8'))          # write rst index
                time.sleep(DELAY_TIME)
                ser.write(b'L')                                  # set mode to column write mode
                time.sleep(DELAY_TIME)
                ser.write(bytes(hex(col)[2:], 'utf-8'))          # write column index
                time.sleep(DELAY_TIME)
                ser.write(b'O')                                  # set mode to continuity check
                time.sleep(DELAY_TIME)
                val = float(inst.query('meas:res?'))             # read resistance measurement
                out_array[(16-rst)+1][col+1] = val
                time.sleep(DELAY_TEST_EQUIPMENT_TIME)   # TODO: see how small we can make this delay
                if (val < RES_SHORT_THRESHOLD_ROWCOL):
                    num_shorts += 1
                writer.writerow([str(rst+1), str(col+1), val])
            printProgressBar(rst+1, 16, suffix = "Rst " + str(rst+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                              # set all mux enables + mux channels to OFF
    out_array = np.delete(out_array, (0), axis=0)
    np.savetxt(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + "_alt.csv", out_array, delimiter=",", fmt="%s")
    num_shorts_text = "There were " + str(num_shorts) + " rst/col short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    out_array = np.delete(out_array, (0), axis=1)
    out_array = out_array[1:]
    if (num_shorts > 0):
        for rst in range(out_array.shape[0]):
            for col in range(out_array.shape[1]):
                if (float(out_array[rst][col]) > RES_SHORT_THRESHOLD_ROWCOL):
                    print(".", end="")
                    out_text += "."
                else:
                    print("X", end="")
                    out_text += "X"
            print("")
            out_text += "\n"
    print("")
    return(num_shorts, out_text)

def test_cont_rst_to_pzbias(dut_name=dut_name_input, start_rst=0, end_rst=16):
    test_name = "CONT_RST_TO_PZBIAS"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                              # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Rst to PZBIAS Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Rst Index", "Rst Res. to PZBIAS (ohm)"])
        printProgressBar(0, 16, suffix = "Rst 0/16", length = 16)
        for rst in range(start_rst, end_rst):
            ser.write(b'Z')                                     # set rst switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'M')                                     # set secondary mux to rst/PZBIAS mode
            time.sleep(DELAY_TIME)
            ser.write(b'T')                                     # set mode to rst write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(rst)[2:], 'utf-8'))             # write the rst address to the tester
            time.sleep(DELAY_TIME)
            ser.write(b'O')                                     # set mode to continuity check mode
            time.sleep(DELAY_TIME)
            val = float(inst.query('meas:res?'))                # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([str(rst+1), val])                  # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            printProgressBar(rst+1, 16, suffix = "Rst " + str(rst+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                           # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " rst/PZBIAS short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

def test_cont_rst_to_shield(dut_name=dut_name_input, start_rst=0, end_rst=16):
    test_name = "CONT_RST_TO_SHIELD"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Rst to SHIELD Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Rst Index", "Rst Res. to SHIELD (ohm)"])
        printProgressBar(0, 16, suffix = "Rst 0/16", length = 16)
        for rst in range(start_rst, end_rst):
            ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'N')                                  # set secondary mux to rst/SHIELD mode
            time.sleep(DELAY_TIME)
            ser.write(b'T')                                  # set mode to rst write mode
            time.sleep(DELAY_TIME)
            ser.write(bytes(hex(rst)[2:], 'utf-8'))          # write the rst address to the tester
            time.sleep(DELAY_TIME)
            ser.write(b'O')                                  # set mode to continuity check mode
            time.sleep(DELAY_TIME)
            val = float(inst.query('meas:res?'))             # read resistance from the meter
            time.sleep(DELAY_TEST_EQUIPMENT_TIME)
            writer.writerow([str(rst+1), val])               # write value to CSV
            if (val < RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
                num_shorts += 1
                summary_text += "X"
            else:
                summary_text += "."
            printProgressBar(rst+1, 16, suffix = "Rst " + str(rst+1) + "/16", length = 16)
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                         # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " rst/SHIELD short(s) in array " + dut_name
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)


array_types = [1, 3]
array_type = 1
while True:
    try:
        array_type = int(input("Please select array type: '1' for 1T, '3' for 3T: "))
    except ValueError:
        print("Sorry, please select a valid array type")
        continue
    if (array_type not in array_types):
        print("Sorry, please select a valid array type")
        continue
    else:
        break
print("Running " + str(array_type) + "T array tests...")
print("\nIf there are shorts, the terminal output (.) means open and (X) means short\n")


out_string = ""
out_string += "Loopback 1A/1B resistance: " + str(loop_one_res) + " ohms\n"
out_string += "Loopback 2A/2B resistance: " + str(loop_two_res) + " ohms\n\n"


if (array_type == 1):
    special_test_state = 0
    test_selection_raw = input("Please hit 'enter' for default (full) 1T test, or\n" +
                               "type '1' to skip continuity checks and only run cap + TFT cont. tests, or\n" +
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
        out_string += "\n" + test_cap_col_to_pzbias(dut_name_input, meas_range_input)[1] + "\n"
        # test_cap_col_to_shield(dut_name_input, meas_range_input)
        out_string += test_cont_col_to_pzbias_tfts_on()[1]
    elif (special_test_state == 2):
        cont_row_to_column = test_cont_row_to_column()
        cont_row_to_pzbias = test_cont_row_to_pzbias()
        cont_col_to_pzbias = test_cont_col_to_pzbias()
        cont_row_to_shield = test_cont_row_to_shield()
        cont_col_to_shield = test_cont_col_to_shield()

        out_string += cont_row_to_column[1] + "\n"
        out_string += cont_row_to_pzbias[1] + "\n"
        out_string += cont_col_to_pzbias[1] + "\n"
        out_string += cont_row_to_shield[1] + "\n"
        out_string += cont_col_to_shield[1]
    else:
        # these are tuples of (num shorts, output string)
        cont_row_to_column = test_cont_row_to_column()
        cont_row_to_pzbias = test_cont_row_to_pzbias()
        cont_col_to_pzbias = test_cont_col_to_pzbias()
        cont_row_to_shield = test_cont_row_to_shield()
        cont_col_to_shield = test_cont_col_to_shield()

        out_string += cont_row_to_column[1] + "\n"
        out_string += cont_row_to_pzbias[1] + "\n"
        out_string += cont_col_to_pzbias[1] + "\n"
        out_string += cont_row_to_shield[1] + "\n"
        out_string += cont_col_to_shield[1]

        hasShorts = cont_row_to_column[0]>0 or cont_row_to_pzbias[0]>0 or cont_col_to_pzbias[0]>0 or cont_row_to_shield[0]>0 or cont_col_to_shield[0]>0
        response = "test"
        if hasShorts:
            print("This array doesn't have pants... it has shorts!")
            response = input("Type 'test' and 'enter' to continue with cap check, or hit 'enter' to quit: ")
        if (response.lower() == "test"):
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
            out_string += "\n" + test_cap_col_to_pzbias(dut_name_input, meas_range_input)[1] + "\n"
            #test_cap_col_to_shield(dut_name_input, meas_range_input)
            out_string += test_cont_col_to_pzbias_tfts_on()[1]
        else:
            datetime_now = dt.datetime.now()
            out_string = (datetime_now.strftime('%Y-%m-%d %H:%M:%S') + "\nArray ID: " + dut_name_input + "\n" + 
                         "Array Type: " + str(array_type) + "T\n" +
                         "\nIf there are shorts, the output (.) means open and (X) means short\n\n") + out_string
            with open(path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_input + "_summary.txt", 'w', newline='') as file:
                file.write(out_string)
            print("Exiting program now...")
            sys.exit(0)

# 3T array testing
elif (array_type == 3):
    cont_row_to_column = test_cont_row_to_column()
    cont_row_to_pzbias = test_cont_row_to_pzbias()
    cont_col_to_pzbias = test_cont_col_to_pzbias()
    cont_row_to_shield = test_cont_row_to_shield()
    cont_col_to_shield = test_cont_col_to_shield()
    cont_rst_to_column = test_cont_rst_to_column()
    cont_rst_to_pzbias = test_cont_rst_to_pzbias()
    cont_rst_to_shield = test_cont_rst_to_shield()

    out_string += cont_row_to_column[1] + "\n"
    out_string += cont_row_to_pzbias[1] + "\n"
    out_string += cont_col_to_pzbias[1] + "\n"
    out_string += cont_row_to_shield[1] + "\n"
    out_string += cont_col_to_shield[1] + "\n"
    out_string += cont_rst_to_column[1] + "\n"
    out_string += cont_rst_to_pzbias[1] + "\n"
    out_string += cont_rst_to_shield[1]
else:
    pass

datetime_now = dt.datetime.now()
out_string = (datetime_now.strftime('%Y-%m-%d %H:%M:%S') + "\nArray ID: " + dut_name_input + "\n" + 
             "Array Type: " + str(array_type) + "T\n" + 
             "\nIf there are shorts, the output (.) means open and (X) means short\n\n") + out_string
with open(path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_input + "_summary.txt", 'w', newline='') as file:
    file.write(out_string)