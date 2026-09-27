import pyvisa

rm = pyvisa.ResourceManager("@py")
inst = rm.open_resource("ASRL/dev/ttyUSB0::INSTR",
    baud_rate = 9600,
    data_bits = 8,
    parity = pyvisa.constants.Parity.none,
    stop_bits = pyvisa.constants.StopBits.two,
    read_termination = "\r\n",
    write_termination = "\r\n"
)


### START: FIX FOR AGILENT E3631A DSR BEHAVIOR ###
from pyvisa_py.serial import SerialSession
from pyvisa.constants import StatusCode
import time

class E3631ASerialSession(SerialSession):
    # Time between each poll for DSR line state
    dsr_poll = 0.005
    # Maximum time between sending a command and the E3631 asserting DSR low
    dsr_ack = 0.050
    # Maximum time the E3631 processes a command
    dsr_timeout = 2.0
    
    def after_parsing(self) -> None:
        super().after_parsing()
        # Override control of DSR and DTR
        self.interface.dsrdtr = False
        # Force DTR to always high
        self.interface.dtr = True
        
    def _wait_dsr(self, dsr_state: bool, timeout: float) -> bool:
        start = time.time()
        while self.interface.dsr is not dsr_state:
            if time.time() - start > timeout:
                return False
            time.sleep(self.dsr_poll)
        return True
    
    def write(self, data: bytes) -> tuple[int, StatusCode]:
        # Wait for device to be idle before sending
        if not self._wait_dsr(True, self.dsr_timeout):
            return 0, StatusCode.error_timeout
        count, status = super().write(data)
        if status is not StatusCode.success:
            return count, status
        got_ack = self._wait_dsr(False, self.dsr_ack)
        if not self._wait_dsr(True, self.dsr_timeout):
            return count, StatusCode.error_timeout
        return count, status

session_obj = rm.visalib.sessions[inst.session]
assert isinstance(session_obj, SerialSession)
# Re-class with a patched subclass of SerialSession
session_obj.__class__ = E3631ASerialSession
### END: FIX FOR AGILENT E3631A DSR BEHAVIOR ###


# Test multiple commands back to back
try:
    inst.write("SYSTem:REMote")
    inst.write("*CLS")
    print(inst.query("*IDN?"))
except Exception as e:
    print(f"!!! ERROR: {e} !!!")
finally:
    inst.close()
    rm.close()
    print("Session closed")

