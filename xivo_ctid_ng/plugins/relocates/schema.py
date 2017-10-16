# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields
from marshmallow.validate import OneOf, Length, Range


class LineLocationSchema(Schema):
    line_id = fields.Integer(validate=Range(min=1), required=True)


class LocationField(fields.Field):

    _locations = {
        'line': fields.Nested(LineLocationSchema),
    }

    def _deserialize(self, value, attr, data):
        method = data.get('destination')
        concrete_location = self._locations.get(method)
        if not concrete_location:
            return {}
        return concrete_location._deserialize(value, attr, data)


class UserRelocateRequestSchema(Schema):
    initiator_call = fields.Str(validate=Length(min=1), required=True)
    destination = fields.Str(validate=OneOf('line'))
    location = LocationField(missing=dict)


user_relocate_request_schema = UserRelocateRequestSchema(strict=True)


class RelocateSchema(Schema):
    uuid = fields.Str(validate=Length(equal=36), required=True)
    relocated_call = fields.Str(validate=Length(min=1), required=True, attribute='relocated_channel')
    initiator_call = fields.Str(validate=Length(min=1), required=True, attribute='initiator_channel')
    recipient_call = fields.Str(validate=Length(min=1), required=True, attribute='recipient_channel')

    class Meta:
        strict = True


relocate_schema = RelocateSchema()
