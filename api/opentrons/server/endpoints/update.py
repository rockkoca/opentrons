import logging
import asyncio
import os
from aiohttp import web
from opentrons import robot

log = logging.getLogger(__name__)


async def _update_firmware(filename, loop):
    """
    This method remains in the API currently because of its use of the robot
    singleton's copy of the driver. This should move to the server lib project
    eventually and use its own driver object (preferably involving moving the
    drivers themselves to the serverlib)
    """
    # ensure there is a reference to the port
    if not robot.is_connected():
        robot.connect()

    # get port name
    port = str(robot._driver.port)
    # set smoothieware into programming mode
    robot._driver._smoothie_programming_mode()
    # close the port so other application can access it
    robot._driver._connection.close()

    # run lpc21isp, THIS WILL TAKE AROUND 1 MINUTE TO COMPLETE
    update_cmd = 'lpc21isp -wipe -donotstart {0} {1} {2} 12000'.format(
        filename, port, robot.config.serial_speed)
    proc = await asyncio.create_subprocess_shell(
        update_cmd,
        stdout=asyncio.subprocess.PIPE,
        loop=loop)
    rd = await proc.stdout.read()
    res = rd.decode().strip()
    await proc.wait()

    # re-open the port
    robot._driver._connection.open()
    # reset smoothieware
    robot._driver._smoothie_reset()
    # run setup gcodes
    robot._driver._setup()

    return res


async def update_module_firmware(request):
    """
     This handler accepts a POST request with Content-Type: multipart/form-data
     and a file field in the body named "module_firmware". The file should
     be a valid HEX image to be flashed to the atmega32u4. The received file is
     sent via USB to the board and flashed by the avr109 bootloader. The file
     is then deleted and a success code is returned
    """
    log.debug('Update Firmware request received')
    data = await request.post()
    module_serial = request.match_info['serial']
    try:
        res = await _update_module_firmware(module_serial,
                                            data['module_firmware'],
                                            request.loop)
        status = 200
    except Exception as e:
        log.exception("Exception during firmware update:")
        res = {'message': 'Exception {} raised by update of {}: {}'.format(
            type(e), data, e.__traceback__)}
        status = 500
    return web.json_response(res, status=status)


async def _update_module_firmware(module_serial, data, loop=None):
    import opentrons

    fw_filename = data.filename
    log.info('Flashing image "{}", this will take about a minute'.format(
        fw_filename))
    content = data.file.read()

    with open(fw_filename, 'wb') as wf:
        wf.write(content)

    config_file_path = os.path.join(
        os.path.abspath(os.path.dirname(opentrons.__file__)),
        'config', 'modules', 'avrdude.conf')

    msg = await _upload_to_module(module_serial, fw_filename,
                                  config_file_path, loop=loop)
    log.debug('Firmware update complete')
    try:
        os.remove(fw_filename)
    except OSError:
        pass
    log.debug("Result: {}".format(msg))
    return {'message': msg, 'filename': fw_filename}


async def _upload_to_module(serialnum, fw_filename, config_file_path, loop):
    """
    This method remains in the API currently because of its use of the robot
    singleton's copy of the api object & driver. This should move to the server
    lib project eventually and use its own driver object (preferably involving
    moving the drivers themselves to the serverlib)
    """
    from opentrons import modules

    # ensure there is a reference to the port
    if not robot.is_connected():
        robot.connect()
    for module in robot.modules:
        module.disconnect()
    robot.modules = modules.discover_and_connect()
    res = ''
    for module in robot.modules:
        if module.device_info.get('serial') == serialnum:
            print("Module with serial found")
            modules.enter_bootloader(module)
            res = await modules.update_firmware(
                module, fw_filename, config_file_path, loop)
            break
    if not res:
        res = 'Module {} not found'.format(serialnum)
    return res
