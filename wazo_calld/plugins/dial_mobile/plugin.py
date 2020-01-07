# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.pubsub import CallbackCollector

from .stasis import DialMobileStasis
from .service import DialMobileService


class Plugin:

    def load(self, dependencies):
        ari = dependencies['ari']
        pubsub = dependencies['pubsub']

        service = DialMobileService(ari)
        pubsub.subscribe('stopping', lambda _: service.on_calld_stopping())

        stasis = DialMobileStasis(ari, service)

        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(stasis.initialize)
