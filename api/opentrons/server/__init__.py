#!/usr/bin/env python

import logging
import traceback
from util import environment
from aiohttp import web
from .rpc import RPCServer
from .http import HTTPServer

log = logging.getLogger(__name__)
log_file_path = environment.get_path('LOG_DIR')

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
    Builds an application and sets up RPC and HTTP servers with it
    """

    app = web.Application(loop=loop, middlewares=[error_middleware])
    app['opentronsRpc'] = RPCServer(app)
    app['opentronsHttp'] = HTTPServer(app, log_file_path)

    return app


def run(hostname, port, path):
    web.run_app(init(log_file_path), host=hostname, port=port, path=path)
