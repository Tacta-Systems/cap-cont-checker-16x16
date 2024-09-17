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
import csv
import glob
import keyboard
import os
import sys
import time
import datetime as dt
import numpy as np
import pyvisa
import tkinter
from tkinter import filedialog
from pygame import mixer

USING_USB_PSU = True

VISA_SERIAL_NUMBER = "04611761"
PSU_SERIAL_NUMBER  = "583H23104"
PSU_DELAY_TIME = 3 # seconds

ser = serial.Serial()
ser.port = "COM3"                  # COM3 hardcoded this as default value (on Maxwell's laptop) but can also prompt for the COM port
ser.baudrate = 115200
ser.bytesize = serial.EIGHTBITS    # number of bits per bytes
ser.parity = serial.PARITY_NONE    # set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE # number of stop bits
ser.timeout = 1                    # non-block read
ser.xonxoff = False                # disable software flow control
ser.rtscts = False                 # disable hardware (RTS/CTS) flow control
ser.dsrdtr = False                 # disable hardware (DSR/DTR) flow control
ser.write_timeout = None           # timeout for write -- changed from writeTimeout

DELAY_TIME = 0.02 # 0.05
DELAY_TEST_EQUIPMENT_TIME = 0 # 0.1
RES_SHORT_THRESHOLD_ROWCOL = 100e6        # any value below this is considered a short
RES_SHORT_THRESHOLD_RC_TO_PZBIAS = 100e6  # any value below this is considered a short

tkinter.Tk().withdraw()
path = "G:\\Shared drives\\Sensing\\Testing\\" # old value is C:\Users\tacta\Desktop
# print("Please select the directory to output data to:")
# path = filedialog.askdirectory()

mixer.init()
loop1 = mixer.Sound("loop1.wav")
loop2 = mixer.Sound("loop2.wav")
both_loops = mixer.Sound("both_loops.wav")

# Connect to Keithley multimeter
rm = pyvisa.ResourceManager()
print("Listing available VISA resources below:")
print(rm.list_resources())
try:
    inst = rm.open_resource('USB0::0x05E6::0x6500::' + VISA_SERIAL_NUMBER + '::INSTR')
    print("Connected to VISA multimeter!")
    if (USING_USB_PSU):
        psu = rm.open_resource('USB0::0x3121::0x0002::' + PSU_SERIAL_NUMBER + '::INSTR')
        print("Connected to VISA PSU!")
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
        continue
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
    num_shorts_text = "There were " + str(num_shorts) + " row/col short(s)"
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
    num_shorts_text = "There were " + str(num_shorts) + " row/PZBIAS short(s)"
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
    num_shorts_text = "There were " + str(num_shorts) + " col/PZBIAS short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

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
    num_shorts_text = "There were " + str(num_shorts) + " row/SHIELD short(s)"
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
    num_shorts_text = "There were " + str(num_shorts) + " col/SHIELD short(s)"
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
    num_shorts_text = "There were " + str(num_shorts) + " rst/col short(s)"
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
    num_shorts_text = "There were " + str(num_shorts) + " rst/PZBIAS short(s)"
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
    num_shorts_text = "There were " + str(num_shorts) + " rst/SHIELD short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

def test_cont_vdd_to_column(dut_name=dut_name_input, start_col=0, end_col=16):
    test_name = "CONT_VDD_TO_COLUMN"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Vdd to Column Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Column Index", "Vdd Res. to Column (ohm)"])
        printProgressBar(0, 16, suffix = "Col 0/16", length = 16)
        for col in range(start_col, end_col):
            ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'!')                                  # set secondary mux to vdd/column mode
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
    ser.write(b'Z')                                         # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " Vdd/Column short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

def test_cont_vrst_to_column(dut_name=dut_name_input, start_col=0, end_col=16):
    test_name = "CONT_VRST_TO_COLUMN"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    num_shorts = 0
    summary_text = ""
    out_text = ""
    inst.query('meas:res?')                                  # set Keithley mode to resistance measurement
    time.sleep(DELAY_TIME)
    out_text += "Sensor Vrst to Column Continuity Detection Running..."
    print(out_text)
    out_text += "\n"
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Column Index", "Vrst Res. to Column (ohm)"])
        printProgressBar(0, 16, suffix = "Col 0/16", length = 16)
        for col in range(start_col, end_col):
            ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
            time.sleep(DELAY_TIME)
            ser.write(b'$')                                  # set secondary mux to vrst/column mode
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
    ser.write(b'Z')                                         # set all mux enables + mux channels to OFF
    num_shorts_text = "There were " + str(num_shorts) + " Vrst/Column short(s)"
    print(num_shorts_text)
    out_text += num_shorts_text + "\n"
    if (num_shorts > 0):
        print(summary_text)
        out_text += summary_text + "\n"
    print("")
    return(num_shorts, out_text)

def test_cont_vdd_to_shield(dut_name=dut_name_input):
    test_name = "CONT_VDD_TO_SHIELD"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out_text = "Sensor Vdd to Shield Continuity Detection Running..."
    out_text += "\n"
    val = 0
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        file.write(test_name.lower() + " (ohms)\n")
        ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
        time.sleep(DELAY_TIME)
        ser.write(b'@')                                  # set secondary mux to vdd/SHIELD mode
        time.sleep(DELAY_TIME)
        ser.write(b'O')                                  # enable tester outputs
        time.sleep(DELAY_TIME)
        val = float(inst.query('meas:res?'))             # read resistance from the meter
        file.write(str(val))
        out_text += f"{val:,}"  + " ohms"
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
        file.close()
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nNo short between Vdd and SHIELD\n"
        print(out_text)
        return(0, out_text)
    else:
        out_text += "\nShort between Vdd and SHIELD\n"
        print(out_text)
        return (1, out_text)

def test_cont_vrst_to_shield(dut_name=dut_name_input):
    test_name = "CONT_VRST_TO_SHIELD"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out_text = "Sensor Vrst to Shield Continuity Detection Running..."
    out_text += "\n"
    val = 0
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        file.write(test_name.lower() + " (ohms)\n")
        ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
        time.sleep(DELAY_TIME)
        ser.write(b'%')                                  # set secondary mux to Vrst/SHIELD mode
        time.sleep(DELAY_TIME)
        ser.write(b'O')                                  # enable tester outputs
        time.sleep(DELAY_TIME)
        val = float(inst.query('meas:res?'))             # read resistance from the meter
        file.write(str(val))
        out_text += f"{val:,}" + " ohms"
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
        file.close()
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nNo short between Vrst and SHIELD\n"
        print(out_text)
        return(0, out_text)
    else:
        out_text += "\nShort between Vrst and SHIELD\n"
        print(out_text)
        return (1, out_text)

def test_cont_vdd_to_pzbias(dut_name=dut_name_input):
    test_name = "CONT_VDD_TO_PZBIAS"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out_text = "Sensor Vdd to PZBIAS Continuity Detection Running..."
    out_text += "\n"
    val = 0
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        file.write(test_name.lower() + " (ohms)\n")
        ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
        time.sleep(DELAY_TIME)
        ser.write(b'#')                                  # set secondary mux to vdd/PZBIAS mode
        time.sleep(DELAY_TIME)
        ser.write(b'O')                                  # enable tester outputs
        time.sleep(DELAY_TIME)
        val = float(inst.query('meas:res?'))             # read resistance from the meter
        file.write(str(val))
        out_text += f"{val:,}" + " ohms"
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
        file.close()
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nNo short between Vdd and PZBIAS\n"
        print(out_text)
        return(0, out_text)
    else:
        out_text += "\nShort between Vdd and PZBIAS\n"
        print(out_text)
        return (1, out_text)

def test_cont_vrst_to_pzbias(dut_name=dut_name_input):
    test_name = "CONT_VRST_TO_PZBIAS"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out_text = "Sensor Vrst to PZBIAS Continuity Detection Running..."
    out_text += "\n"
    val = 0
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        file.write(test_name.lower() + " (ohms)\n")
        ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
        time.sleep(DELAY_TIME)
        ser.write(b'^')                                  # set secondary mux to Vrst/SHIELD mode
        time.sleep(DELAY_TIME)
        ser.write(b'O')                                  # enable tester outputs
        time.sleep(DELAY_TIME)
        val = float(inst.query('meas:res?'))             # read resistance from the meter
        file.write(str(val))
        out_text += f"{val:,}" + " ohms"
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
        file.close()
        ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
        time.sleep(DELAY_TIME)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nNo short between Vrst and SHIELD\n"
        print(out_text)
        return(0, out_text)
    else:
        out_text += "\nShort between Vrst and SHIELD\n"
        print(out_text)
        return (1, out_text)

def test_cont_shield_to_pzbias(dut_name=dut_name_input):
    test_name = "CONT_SHIELD_TO_PZBIAS"
    datetime_now = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    out_text = "Sensor Shield to PZBIAS Continuity Detection Running..."
    out_text += "\n"
    val = 0
    with open(path + datetime_now + "_" + dut_name + "_" + test_name.lower() + ".csv", 'w', newline='') as file:
        file.write(test_name.lower() + " (ohms)\n")
        ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
        time.sleep(DELAY_TIME)
        ser.write(b'(')                                  # set secondary mux to SHIELD/PZBIAS mode
        time.sleep(DELAY_TIME)
        ser.write(b'O')                                  # enable tester outputs
        time.sleep(DELAY_TIME)
        val = float(inst.query('meas:res?'))             # read resistance from the meter
        file.write(str(val))
        out_text += f"{val:,}" + " ohms"
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
        file.close()
        ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
        time.sleep(DELAY_TIME)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nNo short between SHIELD and PZBIAS\n"
        print(out_text)
        return(0, out_text)
    else:
        out_text += "\nShort between SHIELD and PZBIAS\n"
        print(out_text)
        return (1, out_text)

def test_loopback_resistance(num_counts=10, silent=False):
    inst.write('sens:res:rang 10E3 ')# set resistance measurement range to 10kOhm
    is_pressed = False
    count = 0
    print("")
    while not is_pressed:
        ser.write(b'&')                                  # set secondary mux to Loopback 1 mode
        time.sleep(DELAY_TIME)    
        val1 = float(inst.query('meas:res?'))
        val1_str = "{:.4e}".format(val1)
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
        ser.write(b'*')                                  # set secondary mux to Loopback 2 mode
        time.sleep(DELAY_TIME)
        val2 = float(inst.query('meas:res?'))
        val2_str = "{:.4e}".format(val2)
        time.sleep(DELAY_TEST_EQUIPMENT_TIME)
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
            return (val1, val2)

def test_cont_loopback_one():
    out_text = "Sensor Loopback One Continuity Detection Running..."
    out_text += "\n"
    val = 0
    inst.write('sens:res:rang 10E3')                 # set resistance measurement range to 10Kohm
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME)
    ser.write(b'&')                                  # set secondary mux to Loopback 1 mode
    time.sleep(DELAY_TIME)
    val = float(inst.query('meas:res?'))             # read resistance from the meter
    out_text += f"{val:,}" + " ohms"
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME)
    inst.write('sens:res:rang 100E6')                # set resistance measurement range back to 100 MOhm
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nLoopback one is OPEN!\n"
    else:
        out_text += "\nLoopback one measures resistance!\n"
    print(out_text)
    return(val, out_text)

def test_cont_loopback_two():
    out_text = "Sensor Loopback Two Continuity Detection Running..."
    out_text += "\n"
    val = 0
    inst.write('sens:res:rang 10E3')                 # set resistance measurement range to 10Kohm
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME)
    ser.write(b'*')                                  # set secondary mux to Loopback 2 mode
    time.sleep(DELAY_TIME)
    val = float(inst.query('meas:res?'))             # read resistance from the meter
    out_text += f"{val:,}" + " ohms"
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
    time.sleep(DELAY_TIME)
    inst.write('sens:res:rang 100E6')                # set resistance measurement range back to 100 MOhm
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    if (val > RES_SHORT_THRESHOLD_RC_TO_PZBIAS):
        out_text += "\nLoopback two is OPEN!\n"
    else:
        out_text += "\nLoopback two measures resistance!\n"
    print(out_text)
    return(val, out_text)

datetime_now = dt.datetime.now()

if (USING_USB_PSU):
    print("PSU turning on...")
    # set PSU voltage to 18V, current limits to 0.05A on (-) and 0.075A on (+)
    psu.write('INST:SEL 0')
    psu.write('APPL 18,0.05')
    psu.write('OUTP:STAT 1')
    psu.write('INST:SEL 1')
    psu.write('APPL 18,0.075')
    psu.write('OUTP:STAT 1')

    time.sleep(PSU_DELAY_TIME)
    print("PSU on!")

out_string = ""
loop_one_res = 0
loop_two_res = 0
if (array_type_raw in [0, 1]):
    print("Press 'q' to skip loopback check...")
    (loop_one_res, loop_two_res) = test_loopback_resistance()
    out_string += "Loopback 1 resistance: " + str(loop_one_res) + " ohms" + "\n"
    out_string += "Loopback 2 resistance: " + str(loop_two_res) + " ohms" + "\n\n"
    print("")
    with open(path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_id_input + dut_stage_input + "_loopback_measurements.csv", 'w', newline='') as file:
        file.write("Loopback 1 res. (ohm),Loopback 2 res. (ohm)\n")
        file.write(str(loop_one_res) + "," + str(loop_two_res))
else:
    loop_one_res = test_cont_loopback_one()
    time.sleep(1)
    loop_two_res = test_cont_loopback_two()
    out_string += str(loop_one_res[1]) + "\n"
    out_string += str(loop_two_res[1]) + "\n\n"
    with open(path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_id_input + dut_stage_input + "_loopback_measurements.csv", 'w', newline='') as file:
        file.write("Loopback 1 res. (ohm),Loopback 2 res. (ohm)\n")
        file.write(str(loop_one_res[0]) + "," + str(loop_two_res[0]))

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

if (array_type == 1):
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
        out_string += "\n" + test_cap_col_to_pzbias(dut_name_input, meas_range_input)[1] + "\n"
        # test_cap_col_to_shield(dut_name_input, meas_range_input)
        out_string += test_cont_col_to_pzbias_tfts_on()[1]
    elif (special_test_state == 2):
        cont_row_to_column = test_cont_row_to_column()
        cont_row_to_pzbias = test_cont_row_to_pzbias()
        cont_col_to_pzbias = test_cont_col_to_pzbias()
        cont_row_to_shield = test_cont_row_to_shield()
        cont_col_to_shield = test_cont_col_to_shield()
        cont_shield_to_pzbias = test_cont_shield_to_pzbias()

        out_string += cont_row_to_column[1] + "\n"
        out_string += cont_row_to_pzbias[1] + "\n"
        out_string += cont_row_to_shield[1] + "\n"
        out_string += cont_col_to_pzbias[1] + "\n"
        out_string += cont_col_to_shield[1] + "\n"
        out_string += cont_shield_to_pzbias[1]
    else:
        # these are tuples of (num shorts, output string)
        cont_row_to_column = test_cont_row_to_column()
        cont_row_to_pzbias = test_cont_row_to_pzbias()
        cont_col_to_pzbias = test_cont_col_to_pzbias()
        cont_row_to_shield = test_cont_row_to_shield()
        cont_col_to_shield = test_cont_col_to_shield()
        cont_shield_to_pzbias = test_cont_shield_to_pzbias()

        out_string += cont_row_to_column[1] + "\n"
        out_string += cont_row_to_pzbias[1] + "\n"
        out_string += cont_row_to_shield[1] + "\n"
        out_string += cont_col_to_pzbias[1] + "\n"
        out_string += cont_col_to_shield[1] + "\n"
        out_string += cont_shield_to_pzbias[1]

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
            out_string += "\n" + test_cap_col_to_pzbias(dut_name_input, meas_range_input)[1] + "\n"
            #test_cap_col_to_shield(dut_name_input, meas_range_input)
            out_string += test_cont_col_to_pzbias_tfts_on()[1]

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
    cont_vdd_to_column = test_cont_vdd_to_column()
    cont_vrst_to_column = test_cont_vrst_to_column()
    cont_vdd_to_shield = test_cont_vdd_to_shield()
    cont_vrst_to_shield = test_cont_vrst_to_shield()
    cont_vdd_to_pzbias = test_cont_vdd_to_pzbias()
    cont_vrst_to_pzbias = test_cont_vrst_to_pzbias()
    cont_shield_to_pzbias = test_cont_shield_to_pzbias()

    out_string += cont_row_to_column[1] + "\n"
    out_string += cont_row_to_pzbias[1] + "\n"
    out_string += cont_row_to_shield[1] + "\n"
    out_string += cont_col_to_pzbias[1] + "\n"
    out_string += cont_col_to_shield[1] + "\n"
    out_string += cont_vdd_to_column[1] + "\n"
    out_string += cont_vrst_to_column[1] + "\n"
    out_string += cont_rst_to_column[1] + "\n"
    out_string += cont_rst_to_shield[1] + "\n"
    out_string += cont_rst_to_pzbias[1] + "\n"
    out_string += cont_vdd_to_shield[1] + "\n"
    out_string += cont_vrst_to_shield[1] + "\n"
    out_string += cont_vdd_to_pzbias[1] + "\n"
    out_string += cont_vrst_to_pzbias[1] + "\n"
    out_string += cont_shield_to_pzbias[1]
else:
    pass

if (USING_USB_PSU):
    print("\nTurning PSU off...")
    psu.write('OUTP:ALL 0')
    time.sleep(PSU_DELAY_TIME)
    print("PSU off!")

datetime_now = dt.datetime.now()
output_filename = path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_input + "_summary.txt"
out_string = (datetime_now.strftime('%Y-%m-%d %H:%M:%S') + "\nArray ID: " + dut_name_input + "\n" + 
             "Array Type: " + str(array_type) + "T\n" + 
             "\nIf there are shorts, the output (.) means open and (X) means short\n\n") + out_string

with open(output_filename, 'w', newline='') as file:
    file.write(out_string)

inst.close()
psu.close()

# --- begin file compare section ---
def get_timestamp_raw(file_name):
    return file_name.split("\\")[-1][:19]

def get_timestamp_truncated(file_name):    
    return file_name[:19]

def truncate_to_keyword(string, keyword):
    if keyword in string:
        index_val = string.index(keyword)
        return string[:index_val]
    else:
        return string

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
        cmd = input("\nComparing output summary files- Please enter:\n" +
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
    compare_filename = filenames_raw[file_cmp_index]
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
    compare_filename = filenames_raw[file_cmp_index]
else:
    print("Exiting program...")
    sys.exit(0)

print("\nOriginal file is " + output_filename)
print("Comparing against filename " + filenames[file_cmp_index])
with open(output_filename) as f1, open(compare_filename) as f2:
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
        num_diffs = 0
        for i in range(len(f1_chunks)):
            if (f1_chunks[i] != f2_chunks[i]):
                print("\n\n**********Difference detected:**********\n---File " + filenames[-1] + ":")
                for chunk in f1_chunks[i]:
                    print(chunk, end="")
                print("")
                print("---File " + filenames[file_cmp_index] + ":")
                for chunk in f2_chunks[i]:
                    print(chunk, end="")
                num_diffs += 1
                print("\n****************************************")
        print("\nThere were " + str(num_diffs) + " difference(s) detected")
    elif (len(f1_chunks) < len(f2_chunks)):
        print("WARNING: files have different number of tests...")
        num_diffs = 0
        for i in range(len(f1_chunks)):
            if (f1_chunks[i] != f2_chunks[i]):
                print("\n\n**********Difference detected:**********\n---File " + filenames[-1] + ":")
                for chunk in f1_chunks[i]:
                    print(chunk, end="")
                print("")
                print("---File " + filenames[file_cmp_index] + ":")
                for chunk in f2_chunks[i]:
                    print(chunk, end="")
                num_diffs += 1
                print("\n****************************************")
        print("\nThere were " + str(num_diffs) + " difference(s) detected")
        print("WARNING: files have different number of tests...")
    elif (len(f1_chunks) > len(f2_chunks)):
        print("WARNING: files have different number of tests...")
        num_diffs = 0
        for i in range(len(f2_chunks)):
            if (f1_chunks[i] != f2_chunks[i]):
                print("\n\n**********Difference detected:**********\n---File " + filenames[-1] + ":")
                for chunk in f1_chunks[i]:
                    print(chunk, end="")
                print("")
                print("---File " + filenames[file_cmp_index] + ":")
                for chunk in f2_chunks[i]:
                    print(chunk, end="")
                num_diffs += 1
                print("\n****************************************")
        print("\n\nThere were " + str(num_diffs) + " difference(s) detected")
        print("WARNING: files have different number of tests...")
    else:
        print("ERROR: File lengths are mismatched")