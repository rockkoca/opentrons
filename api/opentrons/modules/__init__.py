import os
import logging
import re
import asyncio
from time import sleep
from multiprocessing import Process
from opentrons.modules.magdeck import MagDeck
from opentrons.modules.tempdeck import TempDeck
from opentrons import robot, labware

log = logging.getLogger(__name__)

PORT_SEARCH_TIMEOUT = 4
SUPPORTED_MODULES = {'magdeck': MagDeck, 'tempdeck': TempDeck}


class UnsupportedModuleError(Exception):
    pass


class AbsentModuleError(Exception):
    pass


def load(name, slot):
    module_instance = None
    if name in SUPPORTED_MODULES:
        if robot.is_simulating():
            labware_instance = labware.load(name, slot)
            module_class = SUPPORTED_MODULES.get(name)
            module_instance = module_class(lw=labware_instance)
        else:
            # TODO: BC 2018-08-01 this currently loads the first module of
            # that type that is on the robot, in the future we should add
            # support for multiple instances of one module type this
            # accessor would then load the correct disambiguated module
            # instance via the module's serial
            matching_modules = [
                module for module in robot.modules if isinstance(
                    module, SUPPORTED_MODULES.get(name)
                )
            ]
            if matching_modules:
                module_instance = matching_modules[0]
                labware_instance = labware.load(name, slot)
                module_instance.labware = labware_instance
            else:
                raise AbsentModuleError(
                    "no module of name {} is currently connected".format(name)
                )
    else:
        raise UnsupportedModuleError("{} is not a valid module".format(name))

    return module_instance


# Note: this function should be called outside the robot class, because
# of the circular dependency that it would create if imported into robot.py
def discover_and_connect():
    if os.environ.get('RUNNING_ON_PI') and os.path.isdir('/dev/modules'):
        devices = os.listdir('/dev/modules')
    else:
        devices = []

    discovered_modules = []

    module_port_regex = re.compile('|'.join(SUPPORTED_MODULES.keys()), re.I)
    for port in devices:
        match = module_port_regex.search(port)
        if match:
            module_class = SUPPORTED_MODULES.get(match.group().lower())
            absolute_port = '/dev/modules/{}'.format(port)
            discovered_modules.append(module_class(port=absolute_port))

    log.debug('Discovered modules: {}'.format(discovered_modules))
    for module in discovered_modules:
        try:
            module.connect()
        except AttributeError:
            log.exception('Failed to connect module')

    return discovered_modules


def enter_bootloader(module):
    """
    Disconnect from current port, connect at 1200 baud and disconnect to
    enter bootloader on a (possibly) different port. On disconnect, the
    kernel could assign it a lower port number if available, or keep it on
    the same port. So we check for changes in port assigned and use the
    appropriate one
    """
    ports_before_dfu_mode = discover_ports()  # Required only for old bootloadr

    module._driver.enter_programming_mode()
    module.disconnect()

    # Check for bootloader port
    port_poller = Process(target=port_poll, args=(
        module, ports_before_dfu_mode))
    port_poller.start()
    port_poller.join(timeout=PORT_SEARCH_TIMEOUT)
    print("Time out")
    print("Process ended with exitcode: {}".format(port_poller.exitcode))
    if port_poller.exitcode and port_poller.exitcode > 0:
        raise ConnectionError
    port_poller.terminate()


async def update_firmware(module, firmware_file_path, config_file_path, loop):
    """
    Enter bootloader then run avrdude firmware upload command. The kernel
    could assign the module a new port after the update (since the board is
    automatically reset). Scan for such a port change and use the
    appropriate port
    """
    # TODO: Make sure the module isn't in the middle of operation

    ports_before_update = discover_ports()

    avrdude_cmd = {
        'config_file': config_file_path,
        'part_no': 'atmega32u4',
        'programmer_id': 'avr109',
        'port_name': module._port,
        'baudrate': '57600',
        'firmware_file': firmware_file_path
    }
    proc = await asyncio.create_subprocess_shell(
        'avrdude '
        '-C{config_file} '
        '-v -p{part_no} '
        '-c{programmer_id} '
        '-P{port_name} '
        '-b{baudrate} -D '
        '-Uflash:w:{firmware_file}:i'.format(**avrdude_cmd),
        stdout=asyncio.subprocess.PIPE, loop=loop)
    rd = await proc.stdout.read()
    res = rd.decode().strip()
    await proc.wait()

    print("Switching back to non-bootloader port")
    module._port = port_on_mode_switch(ports_before_update)

    if 'flash verified' in res:
        log.debug('Firmware uploaded successfully')
    else:
        log.debug('Firmware upload failed\n{}'.format(res))
    return res


# TODO: For all port polling, ensure that port state is stable before selecting
def port_on_mode_switch(ports_before_switch):
    ports_after_switch = discover_ports()
    new_port = ''
    # print("New ports: {}".format(ports_after_switch))
    if len(ports_after_switch) > 0 and \
            not set(ports_before_switch) == set(ports_after_switch):
        print("Old ports: {}, New ports: {}".format(
            ports_before_switch, ports_after_switch))
        new_ports = list(filter(
            lambda x: x not in ports_before_switch,
            ports_after_switch))
        print("Probable bootloader port: {}".format(new_ports[0]))
        # Ideally, should raise an error if len(new_ports) is > 1
        new_port = '/dev/modules/{}'.format(new_ports[0])
        print("Switching to new port: {}".format(new_port))
    return new_port


def port_poll(module, ports_before_switch=None):
    """
    Times out in PORT_SEARCH_TIMEOUT seconds
    """
    while True:
        if has_old_bootloader(module):
            new_port = port_on_mode_switch(ports_before_switch)
            if not new_port == '':
                module._port = new_port
                break   # else assume that the port stayed the same
            sleep(1)
        else:
            discovered_ports = list(filter(
                lambda x: x.endswith('bootloader'), discover_ports()))
            if len(discovered_ports) == 1:
                module._port = '/dev/modules/{}'.format(discovered_ports[0])
                break


def has_old_bootloader(module):
    return True if module.device_info.get('model') == 'temp_deck_v1' or \
                   module.device_info.get('model') == 'temp_deck_v2' else False


def discover_ports():
    devices = []
    if os.environ.get('RUNNING_ON_PI') and os.path.isdir('/dev/modules'):
        try:
            devices = os.listdir('/dev/modules')
        except FileNotFoundError:
            try:
                sleep(2)
                # Try again. Measure for race condition where port is being
                # switched in between isdir('/dev/modules') and
                # listdir('/dev/modules')
                devices = os.listdir('/dev/modules')
            except FileNotFoundError:
                raise Exception("No /dev/modules found. Try again")
    return devices
