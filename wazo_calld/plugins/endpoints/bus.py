# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


class EventHandler:
    def __init__(self, endpoints_service):
        self._endpoints_service = endpoints_service

    def subscribe(self, consumer):
        consumer.on_ami_event('Hangup', self.on_hangup)
        consumer.on_ami_event('Newchannel', self.on_new_channel)
        consumer.on_ami_event('PeerStatus', self.on_peer_status)

    def on_hangup(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        self._endpoints_service.remove_call(techno, name, unique_id)

    def on_new_channel(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        self._endpoints_service.add_call(techno, name, unique_id)

    def on_peer_status(self, event):
        techno, name = event['Peer'].split('/', 1)
        status = event['PeerStatus']

        kwargs = {}
        if techno == 'PJSIP' and status == 'Reachable':
            kwargs['registered'] = True
        elif techno == 'PJSIP' and status == 'Unreachable':
            kwargs['registered'] = False

        self._endpoints_service.update_endpoint(techno, name, **kwargs)

    def _techno_name_from_channel(self, channel):
        techno, end = channel.split('/', 1)
        name, _ = end.rsplit('-', 1)
        return techno, name
