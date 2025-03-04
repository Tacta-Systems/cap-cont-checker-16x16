
# dummy classes for serial and VISA objects
class Serial_Dummy:
    def __init__(self, port_in=""):
        self.port = port_in
        self.baudrate = 115200
        self.bytesize = None
        self.parity = None
        self.stopbits = None
        self.timeout = None
        self.xonxoff = None
        self.rtscts = None
        self.dsrdtr = None
        self.writeTimeout = 0
        print("FOR DEBUGGING USE ONLY, VIRTUAL SERIAL DEVICE CREATED")
    def __str__(self):
        return self.port
    def open(self):
        return self.port
    def write(self, data):
        return True
    def close(self):
        self.port = ""
        print("FOR DEBUGGING USE ONLY, VIRTUAL SERIAL DEVICE CLOSED")
        return True

class VISA_Dummy:
    def __init__(self, visa_id_in=""):
        self.read_termination=""
        self.config_val = ""
        self.res_default = 0.01
        self.cap_default = 1e-9
        self.visa_id = visa_id_in
        print("FOR DEBUGGING USE ONLY, VIRTUAL VISA DEVICE CREATED")
    def __str__(self):
        return self.visa_id
    def open(self, port_in):
        self.visa_id = port_in
        return self.visa_id
    def query(self, query_in):
        if (query_in == "meas:res?"):
            return self.res_default
        elif (query_in == "meas:cap?"):
            return self.cap_default
        else:
            return 0
    def write(self, data):
        self.config_val = data
        return True
    def close(self):
        self.visa_id = ""
        print("FOR DEBUGGING USE ONLY, VIRTUAL SERIAL DEVICE CLOSED")
        return True