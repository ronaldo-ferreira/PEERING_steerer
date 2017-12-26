"""
Routines for managing / accessing network namespaces with pyroute2.
"""

import contextlib
from pyroute2 import IPDB, NetNS, netns
from lib import utils
from pyroute2.netlink.rtnl import RTNL_GROUPS, RTNLGRP_IPV4_ROUTE, RTNLGRP_IPV6_ROUTE

HOST_NETNS_NAME = 'host'
CONTAINER_NETNS_NAME = 'container'
IPDB_RTNL_GROUPS = RTNL_GROUPS & (~RTNLGRP_IPV4_ROUTE) & (~RTNLGRP_IPV6_ROUTE)

# Defaults for IPDB:
#  - restart_on_error: IPDB can crash if there's a broadcast storm from netlink
#    netlink will send to IPDB every network state change, such as routing
#    table updates, interface updates, etc., and IPDB may not be able to keep
#    up with the rate of these updates
#
#  - ignore_rtables: Attempts to reduce the amount of updates that IPDB needs
#    to process to reduce system load. utils.AlwaysContainsSet() is a set that
#    will always report that it contains any object. Thus, when IPDB checks if
#    a table is in this set (and thus should be ignored), it will always get
#    back a 'yes'. This allows us to avoid creating a set containing 2^32
#    tables numbers.

#  - nl_bind_groups: Prevents IPDB from receiving updates for IPv4 and
#    IPv6 routes, which can result in overload if BIRD is installing
#    many routes into the kernel (e.g., just after coming up at AMS-IX).

IPDB_DEFAULTS = {'restart_on_error': True,
                 'ignore_rtables': utils.AlwaysContainsSet(),
                 'nl_bind_groups':  IPDB_RTNL_GROUPS}


def _get_netns(name, create=False):
    if create is False:
        # verify that the namespace already exists
        assert(name in netns.listnetns())
    return NetNS(name)


def _get_host_netns():
    return _get_netns(HOST_NETNS_NAME)


def _get_container_netns():
    return _get_netns(CONTAINER_NETNS_NAME)


@contextlib.contextmanager
def _get_ns_ipdb(ns, **kwargs):
    ipdb_config = {}
    ipdb_config.update(IPDB_DEFAULTS)
    ipdb_config.update(kwargs)
    ipdb_config['nl'] = ns  # don't allow kwargs to override this...
    with IPDB(**ipdb_config) as ns_ipdb:
        yield ns_ipdb


@contextlib.contextmanager
def get_container_ipdb(**kwargs):
    with _get_ns_ipdb(ns=_get_container_netns(), **kwargs) as container_ipdb:
        yield container_ipdb


@contextlib.contextmanager
def get_host_ipdb(**kwargs):
    with _get_ns_ipdb(ns=_get_host_netns(), **kwargs) as host_ipdb:
        yield host_ipdb
