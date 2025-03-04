from logging import config
from test_helper_functions import *
import tester_hw_configs

def main():
    try:
        DEBUG_MODE = True
        if DEBUG_MODE: #let's speed things up a bit
            tester_hw_configs.SERIAL_DELAY_TIME = 0
            tester_hw_configs.SERIAL_DELAY_TIME_CAP = 0
            tester_hw_configs.PSU_DELAY_TIME = 0

        ENABLE_TFT_TYPE_OVERRIDE = False
        datetime_now = dt.datetime.now()
        tester_serial_number = None        
        ser = None
        inst = None
        psu = None
        wafer_assy_stage_text = "Post_ASU" # default value assuming it's a backplane
        # Query user for device ID (or a substring)
        wafer_name_input_raw = ""
        while True:
            try:
                wafer_name_input_raw = input("Please enter the wafer ID (e.g. E2446-002-010): ")
            except ValueError:
                print("Sorry, wafer ID can't be blank")
                continue
            if (len(wafer_name_input_raw) < 1):
                print("Sorry, wafer ID can't be blank")
                continue
            else:
                break

        # Query wafer ID from Google Sheets to determine if it's a BT2 or BT3 wafer
        creds = get_creds()
        wafer_name_input = wafer_name_input_raw.strip().upper()
        wafer_build_type_raw = str(get_wafer_build_type(creds, wafer_name_input, debug_mode_in=DEBUG_MODE))
        wafer_build_type = ""
        if (wafer_build_type_raw in dict(WAFER_BUILD_TYPES)):
            # option to override but default to queried value
            # test as BT2 or BT3
            print("\nWafer build type is BT" + str(wafer_build_type_raw) + ".")
            valid_responses = dict()
            valid_responses[""] = "test as BT" + wafer_build_type_raw + " array (default)"
            valid_responses = valid_responses | dict(WAFER_BUILD_TYPES)
            del valid_responses[wafer_build_type_raw]            
            wafer_build_type = query_valid_response(valid_responses)
            if (wafer_build_type == ""):
                wafer_build_type = wafer_build_type_raw
        else:
            print("ERROR: Unable to load wafer build type from inventory... Manually specify?")
            valid_responses = dict(WAFER_BUILD_TYPES)
            valid_responses[""] = "exit program"
            wafer_build_type = query_valid_response(valid_responses)
            if (wafer_build_type == ""):
                print("Exiting program...")
                shutdown_equipment(ser, inst, psu, exit_program=True)
        print("Running tests for BT" + str(wafer_build_type) + " wafer build type...\n")

        print("\nSetup Instructions:\n" +
            "- Connect multimeter (+) lead to secondary mux board ROW (+)/red wire\n" +
            "- Connect multimeter (-) lead to secondary mux board COL (+)/red wire\n" +
            "- Connect power supply +18V, GND, -18V to tester board probe hooks\n" +
            "- Ensure power supply is ON\n")

        print("Connecting equipment...")
        rm = pyvisa.ResourceManager()
        ser, inst, psu, tester_serial_number = init_equipment_with_config(rm, debug_mode=DEBUG_MODE)
        
        print("\nRunning tests for BT" + str(wafer_build_type) + " wafer build type...")

        # load recipes
        print("Loading recipes...")
        config_file_options = list_files_in_directory(WAFER_TEST_CONFIG_PATH)
        config_file_selected = ""
        valid_responses = dict()
        if (DEFAULT_WAFER_TEST_CONFIG_FILENAME in config_file_options):
            config_file_options.remove(DEFAULT_WAFER_TEST_CONFIG_FILENAME)
            valid_responses[""] = DEFAULT_WAFER_TEST_CONFIG_FILENAME + " (default)"
        for i in range(len(config_file_options)):
            valid_responses[i] = config_file_options[i]

        config_file_selected_index = query_valid_response(valid_responses)
        config_file_selected =  ""
        if (config_file_selected_index == ""):
            config_file_selected = DEFAULT_WAFER_TEST_CONFIG_FILENAME
        else:
            config_file_selected = config_file_options[int(config_file_selected_index)]
        print("Testing with " + config_file_selected + " recipe...")

        # check that entire file is valid, exiting if any entry is invalid
        with open(WAFER_TEST_CONFIG_PATH + "\\" + config_file_selected) as file:
            for line in file:
                #print(line.strip().upper())
                if (line.strip().upper() not in DIE_ADDRESSES and len(line.strip().upper()) > 0):
                    raise ValueError("Config file: " + line.strip().upper() + " not a valid die address...")

        wafer_stage_index = 1 # by default they're backplanes, value determined by ARRAY_ASSY_TYPES
        wafer_stage_text = ARRAY_ASSY_TYPES[wafer_stage_index]
        '''
        valid_responses = dict()
        valid_responses[""] = "test as backplane with no sensors (default)"
        valid_responses["2"] = "test as sensor array with sensors"
        wafer_stage_raw = query_valid_response(valid_responses)
        if (wafer_stage_raw == "2"):
            wafer_stage_index = 2
            print("Testing as sensor arrays with sensors...")
        else:
            print("Testing as backplane with no sensors (default)...")
        wafer_stage_text = ARRAY_ASSY_TYPES[wafer_stage_index]
        path_base = PATH_BASE + wafer_stage_text.title() + "\\"
        '''

        print(wafer_name_input)
        list_of_test_coords = []
        with open(WAFER_TEST_CONFIG_PATH + "\\" + config_file_selected) as file:
            for line in file:
                die_address = line.strip().upper()
                if (len(die_address) > 0):
                    list_of_test_coords.append(die_address)

        for coord in list_of_test_coords:
            dut_name =  wafer_name_input + "-" + coord
            dut_name_full = dut_name + "_" + wafer_assy_stage_text
            tft_type = get_array_transistor_type(creds, dut_name, debug_mode_in=DEBUG_MODE)
            if (tft_type is None):
                print("\n" + str(coord) + " is either a direct-wired array or an unknown type. Skipping...")
            else:
                print("\n" + coord + " is a " + str(tft_type) + "T array.")
                if (ENABLE_TFT_TYPE_OVERRIDE):
                    valid_responses = dict()
                    valid_responses[""] = "continue (default)"
                    valid_responses = valid_responses | ARRAY_TFT_TYPES
                    del valid_responses[tft_type]
                    tft_type_override = query_valid_response(valid_responses)
                    if (tft_type_override == ""):
                        pass
                    else:
                        tft_type = int(tft_type_override)
                
                path_base = PATH_BASE + wafer_stage_text.title() + "\\"
                if (os.path.exists(path_base + dut_name)):
                    path_base += dut_name + "\\"
                else:
                    print("Are you sure you want to make a new directory " + path_base + dut_name + "?")
                    valid_responses = dict()
                    valid_responses[""] = "make the new directory (default)"
                    valid_responses["N"] = "exit the tester"
                    make_new_path = query_valid_response(valid_responses)
                    if (make_new_path.upper() == ""):
                        path_base += dut_name + "\\"
                        os.makedirs(path_base)
                    else:
                        shutdown_equipment(ser, inst, psu, exit_program=True)
                print("Move prober to the indicated die...")
                show_closeable_img(coord)
                print(str(tft_type) + "T test data for " + dut_name + " will save to path " + path_base + "\n")
                
                loop_one_res = 0
                loop_two_res = 0
                out_string = (datetime_now.strftime('%Y-%m-%d %H:%M:%S') + "\n" +
                "Array ID: " + dut_name + "\n" +
                "Array Stage: " + wafer_assy_stage_text + "\n" +
                "Array Type: " + wafer_stage_text + "\n" +
                "TFT Type: " + str(tft_type) + "T\n" +
                "Tester S/N: " + tester_serial_number + "\n" +
                "\nIf there are shorts, the output (.) means open and (X) means short\n\n")

                print("Press 'q' to skip loopback check...")
                (loop_one_res, loop_two_res) = test_loopback_resistance(ser, inst)
                out_string += "Loopback 1 resistance: " + str(loop_one_res) + " ohms" + "\n"
                out_string += "Loopback 2 resistance: " + str(loop_two_res) + " ohms" + "\n\n"
                print("")

                with open(path_base + datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name + "_" + wafer_assy_stage_text + "_loopback_measurements.csv", 'w', newline='') as file:
                    file.write("Loopback 1 res. (ohm),Loopback 2 res. (ohm)\n")
                    file.write(str(loop_one_res) + "," + str(loop_two_res))

                if (tft_type == 1):
                    special_test_state = 0
                    valid_responses = {'': "run full 1T test", 1: "only run cap + TFT cont. tests and skip continuity checks",
                                    2: "only run continuity tests"}
                    test_selection_raw = query_valid_response(valid_responses)
                    if (test_selection_raw == "1"):
                        special_test_state = 1
                        print("Running only cap and TFT ON tests...")
                    elif (test_selection_raw == "2"):
                        special_test_state = 2
                        print("Running only continuity tests...")
                    else:
                        print("Running all tests...")
                    output_payload_tester_dict = dict()
                    if (special_test_state == 1): # only run capacitance and TFT ON tests
                        output_payload_tester_dict, out_string_test = test_cap_tft_array_1t(ser, inst, psu, path_base, dut_name_full,
                                                                                             wafer_assy_stage_text, wafer_stage_text)
                        out_string += out_string_test
                    elif (special_test_state == 2):
                        output_payload_tester_dict, out_string_test, has_shorts = test_cont_array_1t(ser, inst, psu, path_base, dut_name_full)
                        out_string += out_string_test
                    else:
                        output_payload_tester_cont_dict, out_string_cont_test, has_shorts = test_cont_array_1t(ser, inst, psu, path_base, 
                                                                                                               dut_name_full)
                        out_string += out_string_cont_test

                        response = ""
                        if has_shorts:
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
                            output_payload_tester_captft_dict, out_string_test = test_cap_tft_array_1t(ser, inst, psu, path_base, dut_name_full,
                                                                                                        wafer_assy_stage_text, wafer_stage_text)
                            output_payload_tester_dict = output_payload_tester_cont_dict | output_payload_tester_captft_dict
                            out_string += "\n" + out_string_test
                        else:
                            output_payload_tester_dict = output_payload_tester_cont_dict

                    out_string += out_string_test
                    output_filename = datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_full + "_summary.txt"
                    output_filename_full = path_base + output_filename                    
                    with open(output_filename_full, 'w', newline='') as file:
                        file.write(out_string)
                    print("Tests concluded at " + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")

                    output_payload_tester_dict["Timestamp"]            = datetime_now.strftime('%Y-%m-%d %H:%M:%S')
                    output_payload_tester_dict["Tester Serial Number"] = tester_serial_number
                    output_payload_tester_dict["Array Serial Number"]  = dut_name
                    output_payload_tester_dict["Array Type"]           = wafer_stage_text
                    output_payload_tester_dict["Array Module Stage"]   = wafer_assy_stage_text
                    output_payload_tester_dict["TFT Type"]             = str(tft_type) + "T"
                    output_payload_tester_dict["Loopback One (ohm)"] = loop_one_res
                    output_payload_tester_dict["Loopback Two (ohm)"] = loop_two_res
                    output_payload_gsheets = list(output_payload_tester_dict.values())
                    write_success = write_to_spreadsheet(creds, output_payload_gsheets)
                    if (write_success):
                        print("Successfully wrote data from " + str(coord) + " to Google Sheets!")
                    else:
                        print("ERROR: Could not write data to Google Sheets")
                elif (tft_type == 3):
                    output_payload_tester_dict, out_string_test = test_cont_array_3t(ser, inst, psu, path_base, dut_name_full)
                    out_string += out_string_test

                    output_filename = datetime_now.strftime('%Y-%m-%d_%H-%M-%S') + "_" + dut_name_full + "_summary.txt"
                    output_filename_full = path_base + output_filename                    
                    with open(output_filename_full, 'w', newline='') as file:
                        file.write(out_string)
                    print("Tests concluded at " + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")  
                  
                    output_payload_tester_dict["Timestamp"]            = datetime_now.strftime('%Y-%m-%d %H:%M:%S')
                    output_payload_tester_dict["Tester Serial Number"] = tester_serial_number
                    output_payload_tester_dict["Array Serial Number"]  = dut_name
                    output_payload_tester_dict["Array Type"]           = wafer_stage_text
                    output_payload_tester_dict["Array Module Stage"]   = wafer_assy_stage_text
                    output_payload_tester_dict["TFT Type"]             = str(tft_type) + "T"
                    output_payload_tester_dict["Loopback One (ohm)"] = loop_one_res
                    output_payload_tester_dict["Loopback Two (ohm)"] = loop_two_res
                    out_string += out_string_test
                    output_payload_gsheets = list(output_payload_tester_dict.values())
                    write_success = write_to_spreadsheet(creds, output_payload_gsheets)
                    if (write_success):
                        print("Successfully wrote data from " + str(coord) + " to Google Sheets!")
                    else:
                        print("ERROR: Could not write data to Google Sheets")
                else:
                    print("Undefined array TFT type, skipping all tests...")
                    pass
        print("\nDone with tests! Exiting...")
        shutdown_equipment(ser, inst, psu, exit_program=True)
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting program...")
        shutdown_equipment(ser, inst, psu)
    except Exception as err:
        print("\nSoftware exception: " + str(err))
        print("Exiting program...")
        shutdown_equipment(ser, inst, psu)

if (__name__ == "__main__"):
    sys.exit(main())