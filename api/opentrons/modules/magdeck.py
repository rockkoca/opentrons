import os
import subprocess
import logging
from time import sleep
from opentrons.drivers.mag_deck import MagDeck as MagDeckDriver
from opentrons import commands


log = logging.getLogger(__name__)


class MissingDevicePortError(Exception):
    pass


# TODO: BC 2018-08-03 this class shares a fair amount verbatim from TempDeck,
# there should be an upstream ABC in the future to contain shared logic
# between modules
class MagDeck:
    '''
    Under development. API subject to change
    '''
    def __init__(self, lw=None, port=None):
        self.labware = lw
        self._port = port
        self._engaged = False
        self._driver = None
        self._device_info = None

    @commands.publish.both(command=commands.magdeck_calibrate)
    def calibrate(self):
        '''
        Calibration involves probing for top plate to get the plate height
        '''
        if self._driver and self._driver.is_connected():
            self._driver.probe_plate()
            # return if successful or not?
            self._engaged = False

    @commands.publish.both(command=commands.magdeck_engage)
    def engage(self):
        '''
        Move the magnet to plate top - 0.4 mm
        '''
        if self._driver and self._driver.is_connected():
            self._driver.move(self._driver.plate_height - 0.4)
            self._engaged = True

    @commands.publish.both(command=commands.magdeck_disengage)
    def disengage(self):
        '''
        Home the magnet
        '''
        if self._driver and self._driver.is_connected():
            self._driver.home()
            self._engaged = False

    # TODO: there should be a separate decoupled set of classes that
    # construct the http api response entity given the model instance.
    def to_dict(self):
        return {
            'name': 'magdeck',
            'port': self.port,
            'serial': self.device_info and self.device_info.get('serial'),
            'model': self.device_info and self.device_info.get('model'),
            'fwVersion': self.device_info and self.device_info.get('version'),
            'displayName': 'Magnetic Deck',
            'status': self.status,
            'data': {'engaged': self._engaged}
        }

    @property
    def port(self):
        """ Serial Port """
        return self._port

    @property
    def device_info(self):
        """
        Returns a dict:
            { 'serial': 'abc123', 'model': '8675309', 'version': '9001' }
        """
        return self._device_info

    @property
    def status(self):
        return 'engaged' if self._engaged else 'disengaged'

    # Internal Methods

    def connect(self):
        '''
        Connect to the serial port
        '''
        if self._port:
            self._driver = MagDeckDriver()
            self._driver.connect(self._port)
            self._device_info = self._driver.get_device_info()
        else:
            # Sanity check: Should never happen, because connect should
            # never be called without a port on Module
            raise MissingDevicePortError(
                "MagDeck couldnt connect to port {}".format(self._port)
            )

    def disconnect(self):
        '''
        Disconnect from the serial port
        '''
        if self._driver:
            self._driver.disconnect()

    def enter_bootloader(self):
        """
        Disconnect from current port, connect at 1200 baud and disconnect to
        enter bootloader on a different port
        """
        old_ports = discover_ports()
        port = self._port
        self.disconnect()
        new_ports = discover_ports()
        if not old_ports == new_ports and len(old_ports) == len(new_ports):
            for _port in new_ports:
                if _port not in old_ports:
                    absolute_port = '/dev/modules/{}'.format(_port)
                    port = absolute_port
        self._driver.connect(port, 1200)
        sleep(2)
        self._driver.disconnect()
        sleep(5)    # Wait for the new port to register
        return port

    def update_firmware(self, firmware_file_path, config_file_path):
        """
        Enter bootloader then run avrdude firmware upload command
        :return:
        """
        # Make sure the module isn't in the middle of operation
        self.disengage()
        port = self.enter_bootloader()
        avrdude_cmd = {
            'config_file': config_file_path,
            'part_no': 'atmega32u4',
            'programmer_id': 'avr109',
            'port_name': port,
            'baudrate': '57600',
            'firmware_file': firmware_file_path
        }
        res = subprocess.run(
            'avrdude '
            '-C{config_file} '
            '-v -p{part_no} '
            '-c{programmer_id} '
            '-P{port_name} '
            '-b{baudrate} -D '
            '-Uflash:w:{firmware_file}:i'.format(**avrdude_cmd), shell=True,
            stdout=subprocess.PIPE).stdout.decode()

        if 'flash verified' in res:
            log.debug('Firmware uploaded successfully')
        else:
            log.debug('Firmware upload failed\n{}'.format(res.strip()))


def discover_ports():
    if os.environ.get('RUNNING_ON_PI') and os.path.isdir('/dev/modules'):
        devices = os.listdir('/dev/modules')
    else:
        devices = []
    return devices
