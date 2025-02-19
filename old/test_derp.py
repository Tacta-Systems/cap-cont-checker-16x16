from test_helper_functions import *

datetime_now = dt.datetime.now()
inst = None
psu = None

print("\nSetup Instructions:\n" +
    "- Plug sensor into connector on primary mux board\n" +
    "- Connect multimeter (+) lead to secondary mux board ROW (+)/red wire\n" +
    "- Connect multimeter (-) lead to secondary mux board COL (+)/red wire\n" +
    "- Ensure power supply is ON\n")

# Query user for device ID (or a substring)
dut_name_input_raw = ""
while True:
    try:
        dut_name_input_raw = input("Please enter the array ID (e.g. E2408-001-2-E2_T2): ")
    except ValueError:
        print("Sorry, array ID can't be blank")
        continue
    if (len(dut_name_input_raw) < 1):
        print("Sorry, array ID can't be blank")
        continue
    else:
        break

# Query full name of entered device ID from Google Sheets
creds = get_creds()
dut_name_input = get_array_full_name(creds, dut_name_input_raw)

# If a valid array name, or a substring of an array name, is entered...
if (dut_name_input is not None):
    print("Testing array ID: " + dut_name_input + "\n")

    # get TFT type of the device with option to override, exiting if not found in inventory
    override = ""
    array_tft_type = get_array_transistor_type(creds, dut_name_input)
    if (type(array_tft_type) is int):
        print("Array TFT type is " + str(array_tft_type) + "T.")
        valid_responses = {"": "continue with " + str(array_tft_type) + "T tests", "change": "override"}
        override = query_valid_response(valid_responses)
    else:
        print("ERROR loading TFT type from inventory... Manually specify TFT type?")
        valid_responses = dict(ARRAY_TFT_TYPES)
        valid_responses[""] = "exit program"
        override = query_valid_response(valid_responses)
        if (override == ""):
            shutdown_equipment(inst, psu, True)
        else:
            array_tft_type = int(override)
    if (override.lower() == "change"):
        array_tft_type = int(query_valid_response(ARRAY_TFT_TYPES))
    print("Running tests for " + str(array_tft_type) + "T array...\n")

    '''
    extracts array type from the input by splitting into chunks by underscore
    1 chunk means backplane
    2 chunks mean array (sensors on backplane)
    3 chunks mean module (array with attached flex)
    '''
    array_stage_raw = len(dut_name_input.rstrip('_').split('_'))
    array_stage_text = ARRAY_ASSY_TYPES[array_stage_raw]

    # prompt the user if they want to change the array type
    valid_responses = {"":"continue tests", "change":"change"}
    print("Array type is '" + array_stage_text + "'.")
    override = query_valid_response(valid_responses)
    if (override.lower() == 'change'):
        array_stage_raw = int(query_valid_response(ARRAY_ASSY_TYPES))
        array_stage_text = ARRAY_ASSY_TYPES[array_stage_raw]
    print("Running tests for '" + array_stage_text + "' array type...")

    # Check if full path already exists, or allows user to make a new directory
    path = PATH_BASE + array_stage_text.title() + "\\"
    if (os.path.exists(path + dut_name_input)):
        path += dut_name_input + "\\"
    else:
        valid_responses = ['Y', 'N']
        print("\nAre you sure you want to make a new directory " + path + dut_name_input + "?")
        make_new_path = query_valid_response(valid_responses)
        if (make_new_path.upper() == 'Y'):
            path += dut_name_input + "\\"
            os.makedirs(path)
        else:
            shutdown_equipment(inst, psu, True)
else:
    dut_name_input = dut_name_input_raw
    print("Entered array ID: " + dut_name_input + "\n" +
          "EXIT THE PROGRAM or choose below to run a manual test\n")
    # manually input TFT type with option to exit program
    valid_responses = dict(ARRAY_TFT_TYPES)
    valid_responses[""] = "exit program"
    override = query_valid_response(valid_responses)
    if (override == ""):
        shutdown_equipment(inst, psu, True)
    else:
        array_tft_type = int(override)
        print("Running tests for " + str(array_tft_type) + "T array...\n")

    '''
    extracts array type from the input by splitting into chunks by underscore
    1 chunk means backplane
    2 chunks mean array (sensors on backplane)
    3 chunks mean module (array with attached flex)
    '''
    array_stage_raw = len(dut_name_input.rstrip('_').split('_'))
    array_stage_text = ARRAY_ASSY_TYPES[array_stage_raw]

    # prompt the user if they want to change the array type
    valid_responses = {"":"continue tests", "change":"change"}
    print("Array type is '" + array_stage_text + "'.")
    override = query_valid_response(valid_responses)
    if (override.lower() == 'change'):
        array_stage_raw = int(query_valid_response(ARRAY_ASSY_TYPES))
        array_stage_text = ARRAY_ASSY_TYPES[array_stage_raw]
    print("Running tests for '" + array_stage_text + "' array type...")

    # Check if full path already exists, or allows user to make a new directory
    path = PATH_BASE + array_stage_text.title() + "\\"
    if (os.path.exists(path + dut_name_input)):
        path += dut_name_input + "\\"
    else:
        valid_responses = ['Y', 'N']
        print("\nAre you sure you want to make a new directory " + path + dut_name_input + "?")
        make_new_path = query_valid_response(valid_responses)
        if (make_new_path.upper() == 'Y'):
            path += dut_name_input + "\\"
            os.makedirs(path)
        else:
            shutdown_equipment(inst, psu, True)

# Prompt user for the device assembly stage -- mandatory if it's a sensor module,
# not mandatory if it's a backplane or a sensor array
dut_name_full = dut_name_input
dut_stage_input = ""
if (array_stage_raw == 3):
    dut_name_full += "_"
    while True:
        try:
            dut_stage_input = input("\nPlease enter the module stage of assembly (e.g. onglass): ")
        except ValueError:
            print("Sorry, array stage of assembly can't be blank")
            continue
        if (len(dut_stage_input) < 1):
            print("Sorry, array stage of assembly can't be blank")
            continue
        else:
            break
else:
    dut_stage_input = input("\nPlease enter the stage of assembly, or leave blank: ")
    if (len(dut_stage_input) > 0):
        dut_name_full += "_"

dut_name_full += dut_stage_input
print(str(array_tft_type) + "T test data for " + dut_name_full + " will save to path " + path + "\n")