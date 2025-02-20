# first element of this list is the default config, which the tester will try to connect to first
TESTER_CONFIG_LIST = [
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
ARRAY_CONNECTION_LIST = [
    "ProbeCard_1400-00001_SN_002",
    "ProbeCard_1400-00001_SN_001",
    "ZIFConnector_on_interposer",
    "ZIFConnector_standalone",
    "OtherArrayConnection"
]