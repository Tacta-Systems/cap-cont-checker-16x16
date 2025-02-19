'''
This program runs automated continuity and capacitance (if applicable) tests on
BT[x] sensor arrays (polyimide on glass substrate, row/column addressing with TFT's).
This is used for pre-flex-bonding units (backplanes, sensor arrays) and
post-flex-bonding units (sensor modules) to track sensor functionality at each stage
of the manufacturing and integration process.

Test procedure is:
* Initiate Arduino tester, multimeter, and power supply
* Input unit ID and extract unit type (backplane/array/module), as well as
  transistor type (1T, 3T) from Google Sheets with option to override both.
* Input unit stage of assembly (contact Evan for the standard names we're using)
* Loopback continuity check -- measures resistance of the loopbacks to ensure proper
  electrical contact with the DUT. For pre-flex-bonding units (backplanes, sensor arrays),
  this is an interactive function that gives audio feedback until electrical contact is made
  on both loopbacks
* Tests -- depends on 1T or 3T array type, each test saves its own output CSV file
* Data saving -- saves *summary.txt of the entire test, and uploads summary to Google Sheets
* File compare -- provides the option to compare summary files with a previous test

Dependencies: test_helper_functions.py. See that file for the list of required
Python packages to run this test, as well as hardware requirements.
'''

from test_helper_functions import *

def main():
    datetime_now = dt.datetime.now()
    ser = init_helper(init_serial(COM_PORT_DEFAULT))
    rm = pyvisa.ResourceManager()
    inst = init_helper(init_multimeter(rm))
    if (USING_USB_PSU):
        psu = init_helper(init_psu(rm))
        init_helper(set_psu_on(psu, PSU_DELAY_TIME))

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
        print("\nEntered array ID: " + dut_name_input + "\n" +
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

    out_string = ""
    loop_one_res = 0
    loop_two_res = 0

    if (array_stage_raw in [1, 2]): # Runs loopback check on bare backplanes and sensor arrays not bonded to flex
        print("Press 'q' to skip loopback check...")
        (loop_one_res, loop_two_res) = test_loopback_resistance(ser, inst)
        out_string += "Loopback 1 resistance: " + str(loop_one_res) + " ohms" + "\n"
        out_string += "Loopback 2 resistance: " + str(loop_two_res) + " ohms" + "\n\n"
        output_payload_gsheets_dict["Loopback One (ohm)"] = loop_one_res
        output_payload_gsheets_dict["Loopback Two (ohm)"] = loop_two_res
        print("")
    else:
        loop_one_res_raw = test_cont_loopback_one(ser, inst)
        time.sleep(1)
        loop_two_res_raw = test_cont_loopback_two(ser, inst)
        print("")
        loop_one_res = loop_one_res_raw[0]
        loop_two_res = loop_two_res_raw[0]
        out_string += str(loop_one_res_raw[1]) + "\n"
        out_string += str(loop_two_res_raw[1]) + "\n\n"
        output_payload_gsheets_dict["Loopback One (ohm)"] = loop_one_res
        output_payload_gsheets_dict["Loopback Two (ohm)"] = loop_two_res

    if (loop_one_res > RES_OPEN_THRESHOLD_LOOPBACKS or loop_two_res > RES_OPEN_THRESHOLD_LOOPBACKS):
        print("WARNING: One or more loopbacks is open. Continue with test?")
        valid_responses = {'Y': "continue", '': "exit program"}
        query = query_valid_response(valid_responses)
        if (query == 'Y'):
            print("Continuing with tests...\n")
        else:
            shutdown_equipment(inst, psu, True)

    with open(path + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_input + "_" + dut_stage_input + "_loopback_measurements.csv", 'w', newline='') as file:
        file.write("Loopback 1 res. (ohm),Loopback 2 res. (ohm)\n")
        file.write(str(loop_one_res) + "," + str(loop_two_res))

    output_payload_gsheets_dict["Timestamp"]            = datetime_now.strftime('%Y-%m-%d %H:%M:%S')
    output_payload_gsheets_dict["Tester Serial Number"] = TESTER_SERIAL_NUMBER
    output_payload_gsheets_dict["Array Serial Number"]  = dut_name_input
    output_payload_gsheets_dict["Array Type"]           = array_stage_text
    output_payload_gsheets_dict["Array Module Stage"]   = dut_stage_input
    output_payload_gsheets_dict["TFT Type"]             = str(array_tft_type) + "T"

    if (array_tft_type == 1):
        special_test_state = 0
        valid_responses = {'': "run full 1T test", 1: "only run cap + TFT cont. tests and skip continuity checks",
                           2: "only run continuity tests"}
        test_selection_raw = query_valid_response(valid_responses)
        if (test_selection_raw == "1"):
            special_test_state = 1
            print("Running only cap and TFT ON tests...\n")
        elif (test_selection_raw == "2"):
            special_test_state = 2
            print("Running only continuity tests...\n")
        else:
            print("Running all tests...\n")

        if (special_test_state == 1): # only run capacitance and TFT ON tests
            valid_responses = {'': "run cap test with default 1nF range", 1: "run cap test with 10nF range"}
            test_selection_raw = query_valid_response(valid_responses)
            meas_range_input = '1e-9'
            if (test_selection_raw == "1"):
                meas_range_input = '1e-8'
                print("Running cap test with new 10nF range...\n")
            else:
                meas_range_input = '1e-9'
                print("Running cap test with default 1nF range...\n")
            test_cap_out = test_cap(ser, inst, path, dut_name_input, dut_stage_input,
                                    "CAP_COL_TO_PZBIAS", array_stage_text, meas_range_input)
            test_cont_col_to_pzbias_tfts_on_out = test_cont_col_to_pzbias_tfts_on(ser, inst, path, dut_name_full)

            out_string += "\n" + test_cap_out[1]
            out_string += test_cont_col_to_pzbias_tfts_on_out[1]
            output_payload_gsheets_dict["Cap Col to PZBIAS (# pass)"] = test_cap_out[0]
            output_payload_gsheets_dict["Col to PZBIAS with TFT's ON (# shorts)"] = test_cont_col_to_pzbias_tfts_on_out[0]

        elif (special_test_state == 2):
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

            output_payload_gsheets_dict["Row to Col (# shorts)"]    = cont_row_to_column[0]
            output_payload_gsheets_dict["Row to PZBIAS (# shorts)"] = cont_row_to_pzbias[0]
            output_payload_gsheets_dict["Row to SHIELD (# shorts)"] = cont_row_to_shield[0]
            output_payload_gsheets_dict["Col to PZBIAS (# shorts)"] = cont_col_to_pzbias[0]
            output_payload_gsheets_dict["Col to SHIELD (# shorts)"] = cont_col_to_shield[0]
            output_payload_gsheets_dict["SHIELD to PZBIAS (ohm)"]   = cont_shield_to_pzbias[0]
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

            output_payload_gsheets_dict["Row to Col (# shorts)"]    = cont_row_to_column[0]
            output_payload_gsheets_dict["Row to PZBIAS (# shorts)"] = cont_row_to_pzbias[0]
            output_payload_gsheets_dict["Row to SHIELD (# shorts)"] = cont_row_to_shield[0]
            output_payload_gsheets_dict["Col to PZBIAS (# shorts)"] = cont_col_to_pzbias[0]
            output_payload_gsheets_dict["Col to SHIELD (# shorts)"] = cont_col_to_shield[0]
            output_payload_gsheets_dict["SHIELD to PZBIAS (ohm)"]   = cont_shield_to_pzbias[0]

            hasShorts = cont_row_to_column[0]>0 or cont_row_to_pzbias[0]>0 or cont_col_to_pzbias[0]>0 or cont_row_to_shield[0]>0 or cont_col_to_shield[0]>0 or cont_shield_to_pzbias[0]=="FAIL"
            response = ""
            if hasShorts:
                print("This array doesn't have pants... it has shorts!")
                valid_responses = {"test": "continue with cap check", '': "skip cap check"}
                response = query_valid_response(valid_responses)
            else:
                valid_responses = {"exit": "exit", '': "continue with cap tests"}
                temp = query_valid_response(valid_responses)
                if (len(temp) == 0):
                    response = "test"
                else:
                    response = ""
            if (response.lower() == "test"):
                print("Running cap and TFT continuity tests...")
                valid_responses = {'': "run cap test with default 1nF range", 1: "run cap test with 10nF range"}
                test_selection_raw = query_valid_response(valid_responses)
                meas_range_input = '1e-9'
                if (test_selection_raw == "1"):
                    meas_range_input = '1e-8'
                    print("Running cap test with new 10nF range...\n")
                else:
                    meas_range_input = '1e-9'
                    print("Running cap test with default 1nF range...\n")
                test_cap_out = test_cap(ser, inst, path, dut_name_input, dut_stage_input,
                                        "CAP_COL_TO_PZBIAS", array_stage_text, meas_range_input)
                test_cont_col_to_pzbias_tfts_on_out = test_cont_col_to_pzbias_tfts_on(ser, inst, path, dut_name_full)
                out_string += "\n" + test_cap_out[1]
                out_string += test_cont_col_to_pzbias_tfts_on_out[1]
                output_payload_gsheets_dict["Cap Col to PZBIAS (# pass)"] = test_cap_out[0]
                output_payload_gsheets_dict["Col to PZBIAS with TFT's ON (# shorts)"] = test_cont_col_to_pzbias_tfts_on_out[0]

    # 3T array testing
    elif (array_tft_type == 3):
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
    else:
        print("Undefined array TFT type, skipping all tests...")
        pass

    print("Done testing serial number " + dut_name_full + "!\n")

    output_filename = datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_full + "_summary.txt"
    output_filename_full = path + output_filename
    out_string = (datetime_now.strftime('%Y-%m-%d %H:%M:%S') + "\n" +
                  "Array ID: " + dut_name_input + "\n" +
                  "Array Stage: " + dut_stage_input + "\n" +
                  "Array Type: " + array_stage_text + "\n" +
                  "TFT Type: " + str(array_tft_type) + "T\n" +
                  "Tester S/N: " + TESTER_SERIAL_NUMBER + "\n" +
                  "\nIf there are shorts, the output (.) means open and (X) means short\n\n") + out_string

    with open(output_filename_full, 'w', newline='') as file:
        file.write(out_string)

    output_payload_gsheets = list(output_payload_gsheets_dict.values())
    write_success = write_to_spreadsheet(creds, output_payload_gsheets)
    if (write_success):
        print("Successfully wrote data to Google Sheets!")
    else:
        print("ERROR: Could not write data to Google Sheets")

    shutdown_equipment(inst, psu, False)

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
    print("Comparing output summary files...")
    valid_responses = {'Y': "compare data with previous test", 'M': "manually compare against a file for this array", '': "exit program"}
    cmd = query_valid_response(valid_responses)

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