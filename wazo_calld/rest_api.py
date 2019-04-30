# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import cherrypy
import logging
import os

from ari.exceptions import ARIException
from ari.exceptions import ARIHTTPError
from cherrypy.process.wspbus import states
from cherrypy.process.servers import ServerAdapter
from cheroot import wsgi
from datetime import timedelta
from flask import Flask, request
from flask_restful import Api
from flask_restful import Resource
from flask_cors import CORS
from functools import wraps
from werkzeug.contrib.fixers import ProxyFix
from xivo.auth_verifier import AuthVerifier
from xivo import http_helpers
from xivo import mallow_helpers
from xivo import rest_api_helpers
from xivo.http_helpers import ReverseProxied

from .exceptions import AsteriskARIUnreachable
from .exceptions import AsteriskARIError

VERSION = 1.0

logger = logging.getLogger(__name__)
app = Flask('wazo_calld')
adapter_app = Flask('wazo_calld_adapter')
api = Api(app, prefix='/{}'.format(VERSION))
auth_verifier = AuthVerifier()


def log_request_params(response):
    http_helpers.log_request_hide_token(response)
    logger.debug('request data: %s', request.data or '""')
    logger.debug('response body: %s', response.data.strip() if response.data else '""')
    return response


class CoreRestApi:

    def __init__(self, global_config):
        self.config = global_config['rest_api']
        http_helpers.add_logger(app, logger)
        http_helpers.add_logger(adapter_app, logger)
        app.before_request(http_helpers.log_before_request)
        app.after_request(log_request_params)
        app.secret_key = os.urandom(24)
        app.permanent_session_lifetime = timedelta(minutes=5)
        app.config['auth'] = global_config['auth']
        adapter_app.after_request(log_request_params)
        adapter_app.permanent_session_lifetime = timedelta(minutes=5)
        auth_verifier.set_config(global_config['auth'])
        self._load_cors()
        self.server = None

    def _load_cors(self):
        cors_config = dict(self.config.get('cors', {}))
        enabled = cors_config.pop('enabled', False)
        if enabled:
            CORS(app, **cors_config)

    def run(self):
        wsgi_app_https = ReverseProxied(ProxyFix(wsgi.WSGIPathInfoDispatcher({'/': app})))
        cherrypy.server.unsubscribe()
        cherrypy.config.update({'environment': 'production'})

        bind_addr = (self.config['listen'], self.config['port'])

        server_https = wsgi.WSGIServer(bind_addr=bind_addr,
                                       wsgi_app=wsgi_app_https)
        server_https.ssl_adapter = http_helpers.ssl_adapter(self.config['certificate'],
                                                            self.config['private_key'])
        ServerAdapter(cherrypy.engine, server_https).subscribe()
        logger.debug('WSGIServer starting... uid: %s, listen: %s:%s',
                     os.getuid(), bind_addr[0], bind_addr[1])

        for route in http_helpers.list_routes(app):
            logger.debug(route)

        try:
            cherrypy.engine.start()
            cherrypy.engine.wait(states.EXITING)
        except KeyboardInterrupt:
            logger.warning('Stopping wazo-calld: KeyboardInterrupt')
            cherrypy.engine.exit()

    def stop(self):
        cherrypy.engine.exit()

    def join(self):
        if cherrypy.engine.state == states.EXITING:
            cherrypy.engine.block()


def handle_ari_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ARIHTTPError as e:
            raise AsteriskARIError({'base_url': e.client.base_url}, e.original_error)
        except ARIException as e:
            raise AsteriskARIUnreachable({'base_url': e.client.base_url}, e.original_error)
    return wrapper


class ErrorCatchingResource(Resource):
    method_decorators = ([mallow_helpers.handle_validation_exception,
                          handle_ari_exception,
                          rest_api_helpers.handle_api_exception] +
                         Resource.method_decorators)


class AuthResource(ErrorCatchingResource):
    method_decorators = [auth_verifier.verify_token] + ErrorCatchingResource.method_decorators