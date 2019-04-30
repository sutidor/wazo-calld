# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from requests import HTTPError
from requests import RequestException

from wazo_calld.exceptions import XiVOConfdUnreachable
from wazo_calld.helpers.confd import not_found


class Switchboard:
    def __init__(self, uuid, confd_client):
        self.uuid = uuid
        self._confd = confd_client

    def exists(self):
        try:
            self._confd.switchboards.get(self.uuid)
        except HTTPError as e:
            if not_found(e):
                return False
            raise
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)
        else:
            return True