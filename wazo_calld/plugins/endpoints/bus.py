# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


class EventHandler:
    def __init__(self, endpoint_status_cache, confd_cache):
        self._endpoint_status_cache = endpoint_status_cache
        self._confd_cache = confd_cache

    def subscribe(self, consumer):
        consumer.on_ami_event('Hangup', self.on_hangup)
        consumer.on_ami_event('Newchannel', self.on_new_channel)
        consumer.on_ami_event('PeerStatus', self.on_peer_status)
        consumer.on_ami_event('Registry', self.on_registry)
        consumer.on_event('trunk_endpoint_associated', self.on_trunk_endpoint_associated)
        consumer.on_event('trunk_updated', self.on_trunk_updated)
        consumer.on_event('trunk_deleted', self.on_trunk_deleted)

    def on_hangup(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            endpoint.remove_call(unique_id)

    def on_new_channel(self, event):
        techno, name = self._techno_name_from_channel(event['Channel'])
        unique_id = event['Uniqueid']

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            endpoint.add_call(unique_id)

    def on_peer_status(self, event):
        techno, name = event['Peer'].split('/', 1)
        status = event['PeerStatus']

        with self._endpoint_status_cache.update(techno, name) as endpoint:
            if techno == 'PJSIP' and status == 'Reachable':
                endpoint.registered = True
            elif techno == 'PJSIP' and status == 'Unreachable':
                endpoint.registered = False

    def on_registry(self, event):
        techno = event['ChannelType']
        begin, _ = event['Username'].split('@', 1)
        _, username = begin.split(':', 1)

        trunk = self._confd_cache.get_trunk_by_username(techno, username)
        with self._endpoint_status_cache.update(techno, trunk['name']) as endpoint:
            endpoint.registered = event['Status'] == 'Registered'

    def on_trunk_endpoint_associated(self, event):
        self._confd_cache.add_trunk(event['trunk_id'])

    def on_trunk_updated(self, event):
        self._confd_cache.update_trunk(event['id'])

    def on_trunk_deleted(self, event):
        self._confd_cache.delete_trunk(event['id'])

    def _techno_name_from_channel(self, channel):
        techno, end = channel.split('/', 1)
        name, _ = end.rsplit('-', 1)
        return techno, name
