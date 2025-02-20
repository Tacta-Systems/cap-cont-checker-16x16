from test_helper_functions import *

# Attempt to connect using default configuration -- first element of TESTER_CONFIG_LIST
# in tester_hw_configs.py
config_default = TESTER_CONFIG_LIST[0]
config_name = config_default["tester_name"]
rm = pyvisa.ResourceManager()
ser = init_helper(init_serial(default_config["serial_port"]), False)
inst = init_helper(init_multimeter(rm, default_config["dmm_serial_string"]), False)
psu = None
if (USING_USB_PSU):
    psu = init_helper(init_psu(rm, default_config["psu_serial_string"]))

# If default configuration successfully connects,
# - selecting 'enter' (default) will use that configuration
# - selecting 'N' will allow selecting of another configuration
#   or manually specifying the hardware
use_custom_config = False
success_config = (ser is not None) and (inst is not None) and (not (USING_USB_PSU and psu is None))
if (success_config):
    valid_responses = {"": "continue with default tester config", "N": "specify custom tester config"}
    override = query_valid_response(valid_responses)
    if (override.lower() == "n"):
        shutdown_equipment(ser, inst, psu, False)
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
        for i in range(len(TESTER_CONFIG_LIST)):
            valid_responses[str(i)] = TESTER_CONFIG_LIST[i]["tester_name"]
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
            if (USING_USB_PSU):
                psu_serial_in = input("Enter PSU VISA serial number: ")
                psu = init_helper(init_psu(rm, psu_serial_in), False)
        # Else, try to connect to the selected config
        else:
            config_id_index = int(config_id)
            config_name = TESTER_CONFIG_LIST[config_id_index]["tester_name"]
            print("Using selected tester config: " + config_name)
            ser = init_helper(init_serial(TESTER_CONFIG_LIST[config_id_index]["serial_port"]), False)
            inst = init_helper(init_multimeter(rm, TESTER_CONFIG_LIST[config_id_index]["dmm_serial_string"]), False)
            psu = None
            if (USING_USB_PSU):
                psu = init_helper(init_psu(rm, TESTER_CONFIG_LIST[config_id_index]["psu_serial_string"]), False)
        success_config = (ser is not None) and (inst is not None) and (not (USING_USB_PSU and psu is None))
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

# Query user for array connection type, e.g. probe card, ZIF, or something else
array_connection_default = ARRAY_CONNECTION_LIST[0]
valid_responses = {}
valid_responses[""] = array_connection_default + " (default)"
for i in range(1, len(ARRAY_CONNECTION_LIST)):
    valid_responses[i] = ARRAY_CONNECTION_LIST[i]
print("\nSelect array connection type")
result_index = query_valid_response(valid_responses)
result_index = 0 if result_index == "" else int(result_index)
array_connection = ARRAY_CONNECTION_LIST[result_index]
print("Selected " + array_connection)

tester_serial_number = config_name + "__" + array_connection
print("Tester Serial Number: " + tester_serial_number)

shutdown_equipment(ser, inst, psu, True) # this will throw an error if the PSU object has already been closed