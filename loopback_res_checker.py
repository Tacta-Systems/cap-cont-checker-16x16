'''
****************************
This program is Windows ONLY
****************************
'''

import serial
import serial.tools.list_ports
import keyboard
import sys
import pyvisa
import time
import tkinter
from tkinter import filedialog

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

DELAY_TIME = 0.005
DELAY_TEST_EQUIPMENT_TIME = 0.01
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
inst.write('sens:res:rang 10E3 ')# set resistance measurement range to 10kOhm


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

print("\nMeasuring loopback 1 and 2 resistance, mash the 'q' key to exit:\n")

print("PSU turning on...")
# set PSU voltage to 18V, current limits to 0.05A on (-) and 0.075A on (+)
psu.write('INST:SEL 0')
psu.write('APPL 18,0.05')
psu.write('OUTP:STAT 1')
psu.write('INST:SEL 1')
psu.write('APPL 18,0.075')
psu.write('OUTP:STAT 1')
time.sleep(PSU_DELAY_TIME)
print("PSU on!\n")   

time.sleep(3)
is_pressed = False
while not is_pressed:
    ser.write(b'&')                                  # set secondary mux to Loopback 1 mode
    time.sleep(DELAY_TIME)
    val1 = "{:.4e}".format(float(inst.query('meas:res?')))
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    ser.write(b'*')                                  # set secondary mux to Loopback 2 mode
    time.sleep(DELAY_TIME)
    val2 = "{:.4e}".format(float(inst.query('meas:res?')))
    time.sleep(DELAY_TEST_EQUIPMENT_TIME)
    print("LOOP1 OHM " + val1 + " LOOP2 OHM " + val2, end='\r')
    if (keyboard.is_pressed('q')):
        is_pressed = True

ser.write(b'Z')                                  # set rst switches to high-Z and disable muxes
time.sleep(DELAY_TIME)

print("\n\nTurning PSU off...")
psu.write('OUTP:ALL 0')
time.sleep(PSU_DELAY_TIME)
print("PSU off!")
print("Disconnecting from meter...")
inst.close()
psu.close()