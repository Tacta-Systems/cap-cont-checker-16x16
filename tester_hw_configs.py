from collections import defaultdict

# ------------------------------------------
# HARDWARE CONFIGURATIONS
# ------------------------------------------

# first element of this list is the default config, which the tester will try to connect to first
TESTER_HW_CONFIG_LIST = [
    {"tester_name"             : "array_tester_v1_001",
     "serial_port"             : "COM3",
     "dmm_hw_type"             : "Keithley DMM6500",
     "dmm_serial_string"       : "USB0::0x05E6::0x6500::04611761::INSTR",
     "psu_hw_type"             : "B&K 9141-GPIB",
     "psu_serial_string"       : "USB0::0x3121::0x0002::583H23104::INSTR",
     "interposer_hw_version"   : "1500-00017",
     "interposer_sn"           : "001",
     "tester_pcba_1_hw_version": "1500-00013", # the mux board connecting to interposer board/the DUT
     "tester_pcba_1_sn"        : "001",
     "tester_pcba_2_hw_version": "1500-00013", # if applicable, the secondary mux board from main board to DMM
     "tester_pcba_2_sn"        : "006",
    },
    {"tester_name"             : "tester_tester",
     "serial_port"             : "COM5",
     "dmm_hw_type"             : "Keithley DMM6500",
     "dmm_serial_string"       : "USB0::0x05E6::0x6500::04611761::INSTR",
     "psu_hw_type"             : "B&K 9141-GPIB",
     "psu_serial_string"       : "USB0::0x3121::0x0002::583H23104::INSTR",
     "interposer_hw_version"   : "1500-00014",
     "interposer_sn"           : "001",        # we don't have S/N for the little B2B to ZIF adapter
     "tester_pcba_1_hw_version": "1500-00013", # the mux board connecting to interposer board/the DUT
     "tester_pcba_1_sn"        : "005",
     "tester_pcba_2_hw_version": "1500-00013", # if applicable, the secondary mux board from main board to DMM
     "tester_pcba_2_sn"        : "002",
    }
]
# first element of this list is the default array connection type
ARRAY_CONNECTION_LIST = [
    "ProbeCard_1400-00001_SN_002",
    "ProbeCard_1400-00001_SN_001",
    "ZIFConnector_on_interposer",
    "ZIFConnector_standalone",
    "OtherArrayConnection"
]

# default/fallback test equipment configuration
USING_USB_PSU = True
PSU_SERIAL_STRING_DEFAULT  = "USB0::0x3121::0x0002::583H23104::INSTR"
DMM_SERIAL_STRING_DEFAULT  = "USB0::0x05E6::0x6500::04611761::INSTR"
SERIAL_PORT_DEFAULT = "COM3"

# default amount of time to wait between commands for each instrument
PSU_DELAY_TIME = 3 # seconds, PSU delay to stabilize output voltage especially when switching on/off
DMM_DELAY_TIME = 0 # seconds, DMM delay not necessary for continuity checks
SERIAL_DELAY_TIME = 0.02 # seconds, any faster and the GPIB interface cannot keep up
DMM_DELAY_TIME_CAP = 0 # seconds, for experimenting with cap check specifically
SERIAL_DELAY_TIME_CAP = 0.02 # tester cannot synchronize GPIB/serial faster than 0.02sec delay

# default multimeter ranges for each class of measurement
RES_RANGE_DEFAULT = '100E6'  # ohm
RES_RANGE_LOOPBACKS = '10E3' # ohm
CAP_RANGE_DEFAULT = '1E-9'   # farad

# ------------------------------------------
# TEST PASS/FAIL THRESHOLDS
# ------------------------------------------

RES_SHORT_THRESHOLD_ROWCOL = 100e6        # any value below this is considered a short
RES_SHORT_THRESHOLD_RC_TO_PZBIAS = 100e6  # any value below this is considered a short
RES_OPEN_THRESHOLD_LOOPBACKS = 10e3      # any value above this is considered an open loopback

# Define dictionary linking sensor types to their acceptable capacitance range
# Sensor type (key) is a string (e.g. "T1")
# Acceptable capacitance range (value) is a tuple of (low, high) in pF
# Add add'l sensor types like below:
# CAP_THRESHOLD_VALS["sensor_type"] = (low bound, high bound)
CAP_THRESHOLD_MIN_DEFAULT = 5 # pF
CAP_THRESHOLD_MAX_DEFAULT = 50
CAP_THRESHOLD_VALS = defaultdict(lambda: (CAP_THRESHOLD_MIN_DEFAULT, CAP_THRESHOLD_MAX_DEFAULT))
CAP_THRESHOLD_VALS["backplane"] = (-2, 2) # bare backplane without sensors

# Define max number of shorts are permitted acceptable for an array
MAX_PASS_CONT_COUNT_TWO_DIM = 0
MAX_PASS_CONT_COUNT_ONE_DIM = 0
MIN_PASS_CAP_COUNT = 255

# ------------------------------------------
# GOOGLE DRIVE SETTINGS (for saving results)
# ------------------------------------------

# Root path where test results are saved.
# Inside has the following folders: "Sensor Modules", "Sensor Arrays", and "Backplanes"
PATH_BASE = "G:\\Shared drives\\Sensing\\Testing\\"

# Google Sheets integration
# API key access to Google Sheets required, provided by token.json and credentials.json in this repository
# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1EUixsb3LHau9IkTxp01H6DhMEBFxH59obI4z_YGYBko"
ID_SHEET_NAME = "Sensor Modules"
OUT_SHEET_NAME = "Tester Output"
TOKEN_FILE_DEFAULT = "token.json"
CRED_FILE_DEFAULT = "credentials.json"

# ------------------------------------------
# WAFER IMAGE PREVIEW SETTINGS
# ------------------------------------------
# graphics are also in GDrive in 'Shared Drives/Sensing/Testing/Wafers/graphics' directory
WAFER_GRAPHICS_PATH = ".\\graphics"
IMAGE_FIGURE_SIZE_X = 3.8 # this is a relative size that Matplotlib will use to determine how big to draw the image preview window
IMAGE_FIGURE_SIZE_Y = 3 # this is a relative size that Matplotlib will use to determine how big to draw the image preview window

# ------------------------------------------
# LOOPBACK SOUND CONFIGURATION (beepy boi)
# ------------------------------------------

# specify sound file to use for loopback continuity checks
# Sound files must be .wav format and in the same directory as the main routine's python file.
LOOP1_SOUND_FILE_DEFAULT = "loop1.wav"
LOOP2_SOUND_FILE_DEFAULT = "loop2.wav"
BOTH_LOOPS_SOUND_FILE_DEFAULT = "both_loops.wav"
SILENT_MODE_DEFAULT = False # False: play sounds, True: mute

# ------------------------------------------
# ARRAY CONFIGURATION
# ------------------------------------------

# Arrays can be 1T or 3T,
# and they can be "backplanes", "sensor arrays", or "sensor modules".
ARRAY_TFT_TYPES = {1: "test 1T array",
                   3: "test 3T array"}
ARRAY_ASSY_TYPES = {
    1: "Backplanes",
    2: "Sensor Arrays",
    3: "Sensor Modules"
}

# ------------------------------------------
# WAFER CONFIGURATION
# ------------------------------------------

# Wafer build type must be string
WAFER_BUILD_TYPES = {"1": "test as BT1 wafer",
                     "2": "test as BT2 wafer",
                     "3": "test as BT3 wafer"}
WAFER_TEST_CONFIG_PATH = "G:\\Shared drives\\Sensing\\Testing\\Wafers\\test_configs"
DEFAULT_WAFER_TEST_CONFIG_FILENAME = "default_test_all.txt"
DIE_ADDRESSES = ["F3", "F4", "E2", "E3", "E4", "E5", "D1", "D2", "D3", "D4", "D5", "D6",
                 "C1", "C2", "C3", "C4", "C5", "C6", "B2", "B3", "B4", "B5", "A3", "A4"]

# ------------------------------------------
# ARDUINO SERIAL COMMAND CONFIGURATION
# ------------------------------------------

'''
Define character commands for Arduino
Arduino sets the tester muxes to the appropriate configuration based on character commands
received over serial from the test computer.
These dictionaries contain the various commands for each combination of tests.
Working with tester hardware array_tester_v1 (2x chained 00013 boards with Arduino Mega)
and automated_arduino_cap_cont_checker_16x16_noack.ino Arduino code as of 2025-01-21.

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