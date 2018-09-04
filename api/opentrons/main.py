import os
import logging
from aiohttp import web
from opentrons import robot, __version__
from config import feature_flags as ff
from logging.config import dictConfig
from util import environment
from server import init
from argparse import ArgumentParser
from system import udev

log = logging.getLogger(__name__)
lock_file_path = '/tmp/resin/resin-updates.lock'
log_file_path = environment.get_path('LOG_DIR')


def lock_resin_updates():
    if os.environ.get('RUNNING_ON_PI'):
        import fcntl

        try:
            with open(lock_file_path, 'w') as fd:
                fd.write('a')
                fcntl.flock(fd, fcntl.LOCK_EX)
                fd.close()
        except OSError:
            log.warning('Unable to create resin-update lock file')


def unlock_resin_updates():
    if os.environ.get('RUNNING_ON_PI') and os.path.exists(lock_file_path):
        os.remove(lock_file_path)


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
        description="Opentrons application server",
        prog="opentrons.server.main"
    )
    arg_parser.add_argument(
        "-H", "--hostname",
        help="TCP/IP hostname to serve on (default: %(default)r)",
        default="localhost"
    )
    arg_parser.add_argument(
        "-P", "--port",
        help="TCP/IP port to serve on (default: %(default)r)",
        type=int,
        default="8080"
    )
    arg_parser.add_argument(
        "-U", "--path",
        help="Unix file system path to serve on. Specifying a path will cause "
             "hostname and port arguments to be ignored.",
    )
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

    # TODO: set up udev in a better location
    if not os.environ.get("ENABLE_VIRTUAL_SMOOTHIE"):
        udev.setup_rules_file()
    # Explicitly unlock resin updates in case a prior server left them locked
    unlock_resin_updates()
    web.run_app(init(log_file_path),
                host=args.hostname, port=args.port, path=args.path)
    arg_parser.exit(message="Stopped\n")


if __name__ == "__main__":
    main()
