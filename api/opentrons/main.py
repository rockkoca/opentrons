import os
import logging
import server
from server import main as serverMain
from argparse import ArgumentParser
from opentrons import robot, __version__
from config import feature_flags as ff
from logging.config import dictConfig
from util import environment
from system import udev
from system import resin


log = logging.getLogger(__name__)
log_file_path = environment.get_path('LOG_DIR')


# TODO: move to system/


def log_init():
    """
    Function that sets log levels and format strings. Checks for the
    OT_LOG_LEVEL environment variable otherwise defaults to DEBUG.
    """
    fallback_log_level = 'INFO'
    ot_log_level = robot.config.log_level
    if ot_log_level not in logging._nameToLevel:
        log.info("OT Log Level {} not found. Defaulting to {}".format(
            ot_log_level, fallback_log_level))
        ot_log_level = fallback_log_level

    level_value = logging._nameToLevel[ot_log_level]

    serial_log_filename = environment.get_path('SERIAL_LOG_FILE')
    api_log_filename = environment.get_path('LOG_FILE')

    logging_config = dict(
        version=1,
        formatters={
            'basic': {
                'format':
                '%(asctime)s %(name)s %(levelname)s [Line %(lineno)s] %(message)s'  # noqa: E501
            }
        },
        handlers={
            'debug': {
                'class': 'logging.StreamHandler',
                'formatter': 'basic',
                'level': level_value
            },
            'serial': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'basic',
                'filename': serial_log_filename,
                'maxBytes': 5000000,
                'level': logging.DEBUG,
                'backupCount': 3
            },
            'api': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'basic',
                'filename': api_log_filename,
                'maxBytes': 1000000,
                'level': logging.DEBUG,
                'backupCount': 5
            }

        },
        loggers={
            '__main__': {
                'handlers': ['debug', 'api'],
                'level': logging.INFO
            },
            'opentrons.server': {
                'handlers': ['debug', 'api'],
                'level': level_value
            },
            'opentrons.api': {
                'handlers': ['debug', 'api'],
                'level': level_value
            },
            'opentrons.instruments': {
                'handlers': ['debug', 'api'],
                'level': level_value
            },
            'opentrons.robot.robot_configs': {
                'handlers': ['debug', 'api'],
                'level': level_value
            },
            'opentrons.drivers.smoothie_drivers.driver_3_0': {
                'handlers': ['debug', 'api'],
                'level': level_value
            },
            'opentrons.drivers.serial_communication': {
                'handlers': ['serial'],
                'level': logging.DEBUG
            }
        }
    )
    dictConfig(logging_config)


def main():
    """This application creates and starts the server for both the RPC routes
    handled by opentrons.server.rpc and HTTP endpoints defined here
    """

    log_init()

    arg_parser = ArgumentParser(
        description="Opentrons robot software",
        parents=[serverMain.server_arg_parser()])
    args = arg_parser.parse_args()

    if args.path:
        log.debug("Starting Opentrons server application on {}".format(
            args.path))
    else:
        log.debug("Starting Opentrons server application on {}:{}".format(
            args.hostname, args.port))

    try:
        robot.connect()
    except Exception as e:
        log.exception("Error while connecting to motor-driver: {}".format(e))

    log.info("API server version:  {}".format(__version__))
    log.info("Smoothie FW version: {}".format(robot.fw_version))

    if not ff.disable_home_on_boot():
        log.info("Homing Z axes")
        robot.home_z()

    server.run(args.hostname, args.port, args.path)

    if not os.environ.get("ENABLE_VIRTUAL_SMOOTHIE"):
        udev.setup_rules_file()
    # Explicitly unlock resin updates in case a prior server left them locked
    resin.unlock_updates()

    arg_parser.exit(message="Stopped\n")


if __name__ == "__main__":
    main()
