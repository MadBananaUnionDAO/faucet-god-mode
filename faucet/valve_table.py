"""Abstraction of an OF table."""

# Copyright (C) 2015 Brad Cowie, Christopher Lorier and Joe Stringer.
# Copyright (C) 2015 Research and Education Advanced Network New Zealand Ltd.
# Copyright (C) 2015--2017 The Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import zlib

from ryu.ofproto import ofproto_v1_3 as ofp

try:
    import valve_of
except ImportError:
    from faucet import valve_of


class ValveTable(object):
    """Wrapper for an OpenFlow table."""

    def __init__(self, table_id, name, restricted_match_types, flow_cookie, notify_flow_removed=False):
        self.table_id = table_id
        self.name = name
        self.restricted_match_types = None
        if restricted_match_types:
            self.restricted_match_types = set(restricted_match_types)
        self.flow_cookie = flow_cookie
        self.notify_flow_removed = notify_flow_removed

    def match(self, in_port=None, vlan=None,
              eth_type=None, eth_src=None,
              eth_dst=None, eth_dst_mask=None,
              ipv6_nd_target=None, icmpv6_type=None,
              nw_proto=None, nw_src=None, nw_dst=None):
        """Compose an OpenFlow match rule."""
        match_dict = valve_of.build_match_dict(
            in_port, vlan, eth_type, eth_src,
            eth_dst, eth_dst_mask, ipv6_nd_target, icmpv6_type,
            nw_proto, nw_src, nw_dst)
        match = valve_of.match(match_dict)
        if self.restricted_match_types is not None:
            for match_type in match_dict:
                assert match_type in self.restricted_match_types, '%s match in table %s' % (
                    match_type, self.name)
        return match

    def flowmod(self, match=None, priority=None,
                inst=None, command=ofp.OFPFC_ADD, out_port=0,
                out_group=0, hard_timeout=0, idle_timeout=0):
        """Helper function to construct a flow mod message with cookie."""
        if match is None:
            match = self.match()
        if priority is None:
            priority = 0 # self.dp.lowest_priority
        if inst is None:
            inst = []
        flags = 0
        if self.notify_flow_removed:
            flags = ofp.OFPFF_SEND_FLOW_REM
        return valve_of.flowmod(
            self.flow_cookie,
            command,
            self.table_id,
            priority,
            out_port,
            out_group,
            match,
            inst,
            hard_timeout,
            idle_timeout,
            flags)

    def flowdel(self, match=None, priority=None, out_port=ofp.OFPP_ANY, strict=False):
        """Delete matching flows from a table."""
        command = ofp.OFPFC_DELETE
        if strict:
            command = ofp.OFPFC_DELETE_STRICT
        return [
            self.flowmod(
                match=match,
                priority=priority,
                command=command,
                out_port=out_port,
                out_group=ofp.OFPG_ANY)]

    def flowdrop(self, match=None, priority=None, hard_timeout=0):
        """Add drop matching flow to a table."""
        return self.flowmod(
            match=match,
            priority=priority,
            hard_timeout=hard_timeout,
            inst=[])

    def flowcontroller(self, match=None, priority=None, inst=None, max_len=96):
        """Add flow outputting to controller."""
        if inst is None:
            inst = []
        return self.flowmod(
            match=match,
            priority=priority,
            inst=[valve_of.apply_actions(
                [valve_of.output_controller(max_len)])] + inst)


class ValveGroupTable(object):
    """Wrap access to group table."""
    # TODO: manage group_ids to prevent conflicts.

    def groupid_from_buckets(self, buckets):
        return zlib.adler32(bytes(str(buckets), encoding='UTF-8'))

    def groupadd(self, group_id, buckets):
        return valve_of.groupadd(group_id=group_id, buckets=buckets)

    def groupmod(self, group_id, buckets):
        return valve_of.groupmod(group_id=group_id, buckets=buckets)

    def groupdel(self, group_id):
        return valve_of.groupdel(group_id=group_id)

    def delete_all(self):
        return valve_of.groupdel()
