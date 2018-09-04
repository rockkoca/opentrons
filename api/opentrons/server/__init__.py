#!/usr/bin/env python

import logging
import traceback
from aiohttp import web
from opentrons.api import MainRouter
from .rpc import Server
from . import endpoints as endp
from .endpoints import (wifi, control, settings)
from opentrons.deck_calibration import endpoints as dc_endp

try:
    from ot2serverlib import endpoints
except ModuleNotFoundError:
    print("Module ot2serverlib not found--using fallback implementation")
    from opentrons.server.endpoints import serverlib_fallback as endpoints


log = logging.getLogger(__name__)


@web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
    except web.HTTPNotFound:
        log.exception("Exception handler for request {}".format(request))
        data = {
            'message': 'File was not found at {}'.format(request)
        }
        response = web.json_response(data, status=404)
    except Exception as e:
        log.exception("Exception in handler for request {}".format(request))
        data = {
            'message': 'An unexpected error occured - {}'.format(e),
            'traceback': traceback.format_exc()
        }
        response = web.json_response(data, status=500)

    return response


# Support for running using aiohttp CLI.
# See: https://docs.aiohttp.org/en/stable/web.html#command-line-interface-cli  # NOQA
def init(log_file_path, loop=None):
    """
    Builds an application including the RPC server, and also configures HTTP
    routes for methods defined in opentrons.server.endpoints
    """
    server = Server(MainRouter(), loop=loop, middlewares=[error_middleware])

    server.app.router.add_get(
        '/health', endp.health)
    server.app.router.add_get(
        '/wifi/list', wifi.list_networks)
    server.app.router.add_post(
        '/wifi/configure', wifi.configure)
    server.app.router.add_get(
        '/wifi/status', wifi.status)
    server.app.router.add_post(
        '/identify', control.identify)
    server.app.router.add_get(
        '/modules', control.get_attached_modules)
    server.app.router.add_get(
        '/modules/{serial}/data', control.get_module_data)
    server.app.router.add_post(
        '/camera/picture', control.take_picture)
    server.app.router.add_post(
        '/server/update', endpoints.update_api)
    server.app.router.add_post(
        '/server/update/firmware', endpoints.update_firmware)
    server.app.router.add_get(
        '/server/update/ignore', endpoints.get_ignore_version)
    server.app.router.add_post(
        '/server/update/ignore', endpoints.set_ignore_version)
    server.app.router.add_static(
        '/logs', log_file_path, show_index=True)
    server.app.router.add_post(
        '/server/restart', endpoints.restart)
    server.app.router.add_post(
        '/calibration/deck/start', dc_endp.start)
    server.app.router.add_post(
        '/calibration/deck', dc_endp.dispatch)
    server.app.router.add_get(
        '/pipettes', control.get_attached_pipettes)
    server.app.router.add_get(
        '/motors/engaged', control.get_engaged_axes)
    server.app.router.add_post(
        '/motors/disengage', control.disengage_axes)
    server.app.router.add_get(
        '/robot/positions', control.position_info)
    server.app.router.add_post(
        '/robot/move', control.move)
    server.app.router.add_post(
        '/robot/home', control.home)
    server.app.router.add_get(
        '/robot/lights', control.get_rail_lights)
    server.app.router.add_post(
        '/robot/lights', control.set_rail_lights)
    server.app.router.add_get(
        '/settings', settings.get_advanced_settings)
    server.app.router.add_post(
        '/settings', settings.set_advanced_setting)
    server.app.router.add_post(
        '/settings/reset', settings.reset)
    server.app.router.add_get(
        '/settings/reset/options', settings.available_resets)

    return server.app
