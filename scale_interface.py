import serial
import serial.tools.list_ports
import threading
import queue
import time
import re
import logging
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ScaleProtocol(Enum):
    """Common scale communication protocols"""
    TOLEDO = "toledo"
    OHAUS = "ohaus"
    AND = "and"
    METTLER = "mettler"
    GENERIC = "generic"

@dataclass
class ScaleReading:
    """Data class for scale readings"""
    weight: float
    unit: str
    stable: bool
    timestamp: float
    raw_data: str
    
class ScaleInterface:
    """Interface for serial communication with weighing scales"""
    
    # Protocol patterns for different scale manufacturers
    PROTOCOL_PATTERNS = {
        ScaleProtocol.TOLEDO: {
            'pattern': r'([+-]?\d+\.?\d*)\s*(kg|g|lb|oz)',
            'stable_indicator': 'S',
            'commands': {'zero': 'Z\r\n', 'tare': 'T\r\n', 'print': 'P\r\n'}
        },
        ScaleProtocol.OHAUS: {
            'pattern': r'([+-]?\d+\.?\d*)\s*(kg|g|lb|oz)',
            'stable_indicator': 'S',
            'commands': {'zero': 'Z\r', 'tare': 'T\r', 'print': 'P\r'}
        },
        ScaleProtocol.AND: {
            'pattern': r'ST,([+-]\d+\.\d+)\s*(kg|g)',
            'stable_indicator': 'ST',
            'commands': {'zero': 'Z\r\n', 'tare': 'T\r\n', 'request': 'Q\r\n'}
        },
        ScaleProtocol.METTLER: {
            'pattern': r'S\s+([+-]?\d+\.?\d*)\s*(kg|g|lb)',
            'stable_indicator': 'S',
            'commands': {'zero': 'Z\r\n', 'tare': 'T\r\n', 'send_stable': 'SI\r\n'}
        },
        ScaleProtocol.GENERIC: {
            'pattern': r'([+-]?\d+\.?\d*)\s*(kg|g|lb|oz)',
            'stable_indicator': None,
            'commands': {}
        }
    }
    
    def __init__(self, 
                 port: Optional[str] = None,
                 baudrate: int = 9600,
                 protocol: ScaleProtocol = ScaleProtocol.GENERIC,
                 timeout: float = 0.1):
        """Initialize scale interface
        
        Args:
            port: Serial port name (e.g., '/dev/ttyUSB0', 'COM1')
            baudrate: Baud rate for serial communication
            protocol: Scale protocol to use
            timeout: Read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.protocol = protocol
        self.timeout = timeout
        self.serial_port = None
        self.is_connected = False
        
        # Threading for continuous reading
        self.read_thread = None
        self.stop_reading = threading.Event()
        self.data_queue = queue.Queue()
        self.last_reading = None
        self.callbacks = []
        
        # Auto-detect port if not specified
        if not self.port:
            self.port = self.auto_detect_scale()
    
    def auto_detect_scale(self) -> Optional[str]:
        """Auto-detect scale on serial ports"""
        logger.info("Auto-detecting scale...")
        
        ports = self.list_serial_ports()
        
        for port_info in ports:
            port = port_info['device']
            logger.debug(f"Checking port {port}...")
            
            try:
                # Try to open port and read data
                with serial.Serial(port, self.baudrate, timeout=1) as ser:
                    # Send a generic command to trigger response
                    ser.write(b'\r\n')
                    time.sleep(0.5)
                    
                    # Read any available data
                    if ser.in_waiting > 0:
                        data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                        
                        # Check if data matches any known pattern
                        for protocol, config in self.PROTOCOL_PATTERNS.items():
                            if re.search(config['pattern'], data):
                                logger.info(f"Scale detected on {port} using {protocol.value} protocol")
                                self.protocol = protocol
                                return port
                                
            except Exception as e:
                logger.debug(f"Failed to check port {port}: {e}")
                
        logger.warning("No scale detected on any serial port")
        return None
    
    def list_serial_ports(self) -> List[Dict[str, str]]:
        """List available serial ports"""
        ports = []
        
        for port in serial.tools.list_ports.comports():
            port_info = {
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            }
            
            # Filter for likely scale ports
            if any(keyword in port.description.lower() 
                   for keyword in ['usb', 'serial', 'uart', 'scale', 'ftdi', 'ch340']):
                ports.append(port_info)
                
        return ports
    
    def connect(self) -> bool:
        """Connect to the scale"""
        if not self.port:
            logger.error("No port specified or detected")
            return False
            
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            self.is_connected = True
            logger.info(f"Connected to scale on {self.port} at {self.baudrate} baud")
            
            # Start reading thread
            self.start_continuous_reading()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to scale: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the scale"""
        self.stop_continuous_reading()
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            
        self.is_connected = False
        logger.info("Disconnected from scale")
    
    def start_continuous_reading(self):
        """Start continuous reading thread"""
        if self.read_thread and self.read_thread.is_alive():
            return
            
        self.stop_reading.clear()
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
    
    def stop_continuous_reading(self):
        """Stop continuous reading thread"""
        self.stop_reading.set()
        
        if self.read_thread:
            self.read_thread.join(timeout=1)
    
    def _read_loop(self):
        """Continuous reading loop"""
        buffer = ""
        
        while not self.stop_reading.is_set() and self.is_connected:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    buffer += data.decode('utf-8', errors='ignore')
                    
                    # Process complete lines
                    while '\n' in buffer or '\r' in buffer:
                        line, buffer = self._extract_line(buffer)
                        
                        if line:
                            reading = self._parse_reading(line)
                            
                            if reading:
                                self.last_reading = reading
                                self.data_queue.put(reading)
                                
                                # Call callbacks
                                for callback in self.callbacks:
                                    try:
                                        callback(reading)
                                    except Exception as e:
                                        logger.error(f"Callback error: {e}")
                                        
                time.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                logger.error(f"Read error: {e}")
                time.sleep(0.1)
    
    def _extract_line(self, buffer: str) -> tuple[str, str]:
        """Extract a complete line from buffer"""
        # Find line ending
        end_idx = -1
        for delimiter in ['\r\n', '\n', '\r']:
            idx = buffer.find(delimiter)
            if idx != -1 and (end_idx == -1 or idx < end_idx):
                end_idx = idx
                
        if end_idx != -1:
            line = buffer[:end_idx].strip()
            buffer = buffer[end_idx+1:]
            return line, buffer
            
        return "", buffer
    
    def _parse_reading(self, data: str) -> Optional[ScaleReading]:
        """Parse scale reading from raw data"""
        if not data:
            return None
            
        config = self.PROTOCOL_PATTERNS[self.protocol]
        pattern = config['pattern']
        stable_indicator = config.get('stable_indicator')
        
        match = re.search(pattern, data)
        if match:
            try:
                weight = float(match.group(1))
                unit = match.group(2) if len(match.groups()) > 1 else 'g'
                
                # Check stability
                stable = True
                if stable_indicator:
                    stable = stable_indicator in data
                
                return ScaleReading(
                    weight=weight,
                    unit=unit,
                    stable=stable,
                    timestamp=time.time(),
                    raw_data=data
                )
                
            except Exception as e:
                logger.debug(f"Failed to parse reading: {e}")
                
        return None
    
    def get_weight(self, stable_only: bool = True, timeout: float = 5.0) -> Optional[ScaleReading]:
        """Get current weight reading
        
        Args:
            stable_only: Only return stable readings
            timeout: Maximum time to wait for stable reading
            
        Returns:
            ScaleReading or None if no reading available
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Try to get from queue
                reading = self.data_queue.get(timeout=0.1)
                
                if not stable_only or reading.stable:
                    return reading
                    
            except queue.Empty:
                # Check last reading
                if self.last_reading:
                    if not stable_only or self.last_reading.stable:
                        return self.last_reading
                        
        return None
    
    def send_command(self, command: str) -> bool:
        """Send command to scale"""
        if not self.is_connected:
            return False
            
        try:
            self.serial_port.write(command.encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False
    
    def zero_scale(self) -> bool:
        """Zero the scale"""
        config = self.PROTOCOL_PATTERNS[self.protocol]
        command = config['commands'].get('zero')
        
        if command:
            return self.send_command(command)
        
        logger.warning(f"Zero command not available for {self.protocol.value} protocol")
        return False
    
    def tare_scale(self) -> bool:
        """Tare the scale"""
        config = self.PROTOCOL_PATTERNS[self.protocol]
        command = config['commands'].get('tare')
        
        if command:
            return self.send_command(command)
        
        logger.warning(f"Tare command not available for {self.protocol.value} protocol")
        return False
    
    def add_callback(self, callback: Callable[[ScaleReading], None]):
        """Add callback for new readings"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[ScaleReading], None]):
        """Remove callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()