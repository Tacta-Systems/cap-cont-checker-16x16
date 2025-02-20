from test_helper_functions import *

default_config = TESTER_CONFIG_LIST[0]
rm = pyvisa.ResourceManager()
ser = init_helper(init_serial(default_config["com_port"]), False)
inst = init_helper(init_multimeter(rm, default_config["dmm_serial_string"]), False)
psu = None
if (USING_USB_PSU):
    psu = init_helper(init_psu(rm, default_config["psu_serial_string"]))

use_custom_config = False
success_default_config = (ser is not None) and (inst is not None) and (not (USING_USB_PSU and psu is None))
if (success_default_config):
    print("Using default tester config: " + default_config["tester_name"])
    valid_responses = {"": "continue with default tester config", "N": "specify custom tester config"}
    override = query_valid_response(valid_responses)
    if (override.lower() == "n"):
        shutdown_equipment(ser, inst, psu, False)
        use_custom_config = True

if ((not success_default_config) or use_custom_config):
    if ser is None:
        print("Unable to connect to default port")
    valid_responses = {}
    for i in range(len(TESTER_CONFIG_LIST)):
        valid_responses[str(i)] = TESTER_CONFIG_LIST[i]["tester_name"]
    valid_responses["M"] = "Set manual configuration"
    print("Select the hardware configuration from below.")
    config_id = query_valid_response(valid_responses)
    print("Selected config ID: " + config_id)
    # Loop until successfully connected
    # Select config OR manually enter info

# Init all hardware

shutdown_equipment(ser, inst, psu, True) # this will throw an error if the PSU object has already been closed