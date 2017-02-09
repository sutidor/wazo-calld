# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from ari.exceptions import ARINotFound
from xivo_ctid_ng.core.ari_ import APPLICATION_NAME

from .exceptions import NoSuchSwitchboard

logger = logging.getLogger(__name__)


class SwitchboardsStasis(object):

    def __init__(self, ari, confd, switchboard_notifier, switchboard_service):
        self._ari = ari
        self._confd = confd
        self._notifier = switchboard_notifier
        self._service = switchboard_service

    def subscribe(self):
        self._ari.on_application_registered(APPLICATION_NAME, self.notify_all_switchboard_queues)
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('ChannelLeftBridge', self.unqueue)

    def notify_all_switchboard_queues(self):
        for switchboard in self._confd.switchboards.list()['items']:
            queued_calls = self._service.queued_calls(switchboard['uuid'])
            self._notifier.queued_calls(switchboard['uuid'], queued_calls)

    def stasis_start(self, event_objects, event):
        if len(event['args']) < 2:
            return
        # app_instance = event['args'][0]
        if event['args'][1] == 'switchboard_queue':
            self._stasis_start_queue(event_objects, event)
        elif event['args'][1] == 'switchboard_answer':
            self._stasis_start_answer(event_objects, event)

    def _stasis_start_queue(self, event_objects, event):
        try:
            switchboard_uuid = event['args'][2]
        except IndexError:
            logger.warning('Ignoring invalid StasisStart event %s', event)
            return
        channel = event_objects['channel']
        self._service.new_queued_call(switchboard_uuid, channel.id)

    def _stasis_start_answer(self, event_objects, event):
        try:
            switchboard_uuid = event['args'][2]
            queued_channel_id = event['args'][3]
        except IndexError:
            logger.warning('Ignoring invalid StasisStart event %s', event)
            return
        operator_channel = event_objects['channel']

        try:
            self._ari.channels.get(channelId=queued_channel_id)
        except ARINotFound:
            logger.warning('queued call %s hung up, cancelling answer from switchboard %s',
                           queued_channel_id,
                           switchboard_uuid)
            operator_channel.hangup()
            return

        operator_channel.answer()
        try:
            operator_original_caller_id = operator_channel.getChannelVar(variable='XIVO_ORIGINAL_CALLER_ID')['value'].encode('utf-8')
            operator_channel.setChannelVar(variable='CALLERID(all)', value=operator_original_caller_id)
        except ARINotFound:
            pass

        bridge = self._ari.bridges.create(type='mixing')
        bridge.addChannel(channel=queued_channel_id)
        bridge.addChannel(channel=operator_channel.id)

        self._notifier.queued_call_answered(switchboard_uuid, operator_channel.id, queued_channel_id)

    def unqueue(self, channel, event):
        switchboard_uuid = channel.json['channelvars']['WAZO_SWITCHBOARD_QUEUE']

        try:
            queued_calls = self._service.queued_calls(switchboard_uuid)
        except NoSuchSwitchboard:
            return

        self._notifier.queued_calls(switchboard_uuid, queued_calls)
