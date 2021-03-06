"""
Routines for setting up network interfaces in a Docker container.

Exposes host interfaces to containers by setting up MACVLAN interfaces. 
These MACVLAN interfaces are passthru interfaces and thus have the same MAC
address as the interface on the host machine.

Also handles setting up a TAP interface for the OpenVPN server. MACVLAN
interfaces are then attached to this TAP interface, with each MACVLAN
interface representing a single upstream peer.
"""

import ipaddress
import logging
from pyroute2 import IPDB
from pyroute2.netlink.rtnl.ifinfmsg import IFT_TAP

from lib.namespaces import CONTAINER_NETNS_NAME, IPDB_DEFAULTS


class InterfaceSetupException(Exception):
    pass


def get_ifname_vlan(ifname):
    '''Split an interface's name into base and VLAN ID'''
    if '.' in ifname:
        base_ifname, vlan_id = ifname.split('.')
        try:
            vlan_id = int(vlan_id)
        except ValueError:
            raise InterfaceSetupException('Cannot parse interface name: %s',
                                          ifname)
        return base_ifname, vlan_id
    else:
        return ifname, None


def setup_interfaces(ipdbs, config):
    failures = 0

    host_interfaces = config.get("host_interfaces", [])
    if host_interfaces:
        logging.info("Processing host interfaces")
    else:
        logging.info("No host interfaces found in config")
    for interface_spec in host_interfaces:
        try:
            process_host_interface(ipdbs, interface_spec)
        except InterfaceSetupException:
            logging.exception(
                "An exception occurred while processing a host interface")
            failures += 1
            logging.warn("Will continue processing remaining interfaces")

    tap_interfaces = config.get("tap_interfaces", [])
    if tap_interfaces:
        logging.info("Processing TAP interfaces")
    else:
        logging.info("No TAP interfaces found in config")
    for interface_spec in tap_interfaces:
        try:
            process_tap_interface(ipdbs, interface_spec)
        except InterfaceSetupException:
            logging.exception(
                "An exception occurred while setting up a TAP interface")
            failures += 1
            logging.warn("Will continue processing remaining interfaces")

    virt_upstream_interfaces = config.get("virt_upstream_interfaces", [])
    if virt_upstream_interfaces:
        logging.info("Processing virtual upstream interfaces")
    else:
        logging.info("No virtual upstream interfaces found in config")
    for interface_spec in virt_upstream_interfaces:
        try:
            process_virt_upstream_interface(ipdbs, interface_spec)
        except InterfaceSetupException:
            logging.exception(
                "An exception occurred while setting up a upstream interface")
            failures += 1
            logging.warn("Will continue processing remaining interfaces")

    result_msg = "Finished setting up interfaces (%d failures)" % (failures)
    if failures:
        logging.warn(result_msg)
    else:
        logging.info(result_msg)
    return failures


def process_tap_interface(ipdbs, interface_spec):
    """Process / set up TAP interfaces for OpenVPN and other services.

    If an interface with the specified name already exists in the container,
    we check that it is a TAP interface -- if not, we destroy it. If the
    existing interface is a valid TAP interface, we update its addresses
    as needed.
    """

    tap_ifname = interface_spec.get('name')
    if tap_ifname is None:
        raise InterfaceSetupException("No interface name specified")

    inet_addr_ipv4 = interface_spec.get('inet_addr_ipv4')
    inet_addr_ipv6 = interface_spec.get('inet_addr_ipv6')
    addresses = set()
    if inet_addr_ipv4:
        addresses.add(interface_spec.get('inet_addr_ipv4'))
    if inet_addr_ipv6:
        addresses.add(interface_spec.get('inet_addr_ipv6'))

    # first, check if we have an existing interface with the same name
    # if we do and it isn't the correct type, remove it
    #
    # TODO(bschlinker): File bug report with pyroute2
    # despite how we use kind = 'tuntap' when setting up the interface,
    # the kind is reported as 'tun' and we must inspect the flags to see
    # if it is actually a 'tuntap' interface in 'tap' mode
    tap_if = ipdbs.container.interfaces.get(tap_ifname)
    if tap_if and (tap_if.kind != 'tun' or not (tap_if.flags & IFT_TAP)):
        logging.warn("Found existing interface %s with incorrect type",
                     tap_ifname)
        try:
            ipdbs.container.interfaces[tap_ifname].remove().commit()
        except Exception as e:
            raise InterfaceSetupException(
                'Unable to remove interface %s from container\n%s'
                % (tap_ifname, e))
        logging.warn("Removed interface %s from container", tap_ifname)

    # check again if we have the interface, if not create it
    # then add and remove interface addresses as needed
    tap_if = ipdbs.container.interfaces.get(tap_ifname)
    if tap_if is None:
        # create the interface
        tap_if = ipdbs.container.create(ifname=tap_ifname,
                                        kind='tuntap',
                                        mode='tap')
        try:
            tap_if.commit()
        except Exception as e:
            raise InterfaceSetupException(
                "Unable to create interface %s:\n%s" % (tap_ifname, e))
            tap_if.remove().commit()
        logging.info("Created TAP interface %s", tap_ifname)
    else:
        logging.info("Found existing TAP interface %s", tap_ifname)

    # bring the interface up (if needed) and set up its addresses
    _start_interface(tap_if)
    _setup_interface_addresses(tap_if, addresses)


def process_virt_upstream_interface(ipdbs, interface_spec):
    """Process / set up a virtual upstream interface using MACVLANs.

    If an interface with the specified name already exists in the container,
    we check that it is a valid virtual upstream interface (correct type and
    link) -- if not, we destroy it. If the existing interface is a valid TAP
    interface, we update its addresses as needed.
    """

    upstream_ifname = interface_spec.get('name')
    if upstream_ifname is None:
        raise InterfaceSetupException("No interface name specified")

    upstream_parent_ifname = interface_spec.get('parent_name')
    if upstream_parent_ifname is None:
        raise InterfaceSetupException("No parent interface specified for %s",
                                      upstream_ifname)

    upstream_macvlan_mode = interface_spec.get('macvlan_mode')
    if upstream_macvlan_mode is None:
        upstream_macvlan_mode="vepa"
        logging.info("No macvlan_mode specified, using default")
    
    inet_addr_ipv4 = interface_spec.get('inet_addr_ipv4')
    inet_addr_ipv6 = interface_spec.get('inet_addr_ipv6')
    addresses = set()
    if inet_addr_ipv4:
        addresses.add(interface_spec.get('inet_addr_ipv4'))
    if inet_addr_ipv6:
        addresses.add(interface_spec.get('inet_addr_ipv6'))

    address_objs = set()
    for address in addresses:
        address_objs.add(ipaddress.ip_interface(str(address)))

    logging.info("Setting up upstream interface %s in container "
                 "(parent interface = %s)" %
                 (upstream_ifname, upstream_parent_ifname))

    # try to find the parent interface in the container
    upstream_parent_if = ipdbs.container.interfaces.get(
        upstream_parent_ifname)
    if upstream_parent_if is None:
        raise InterfaceSetupException(
            "Unable to find parent interface %s in container netns\n"
            "Found the following interfaces %s"
            % (upstream_parent_ifname,
               ipdbs.container.interfaces.keys()))

    _create_and_configure_macvlan_interface(
        ipdbs.container, upstream_parent_if, upstream_ifname, addresses,
        macvlan_mode=upstream_macvlan_mode)


def process_host_interface(ipdbs, interface_spec):
    """Process each host interface and expose in the container as requested.

    For each host interface to be exposed in the container, set up a parallel
    MACVLAN interface and bind it to the host interface using passthru mode.

    If a MACVLAN interface already exists in the container for the host
    interface, the interface will be removed and re-created to ensure that
    addresses are configured correctly.
    """

    ifname = interface_spec.get('name')
    if ifname is None:
        raise InterfaceSetupException("No interface name specified")
    base_ifname, vlan_id = get_ifname_vlan(ifname)

    if interface_spec.get('create_in_ctr') is not True:
        logging.info('Ignoring interface %s (create_in_ctr != True)', ifname)
        return
    ctr_ifname = "host_%s" % ifname  # the corresponding name in container
    logging.info("Setting up %s as %s in container" % (ifname, ctr_ifname))

    inet_addr_ipv4 = interface_spec.get('inet_addr_ipv4')
    inet_addr_ipv6 = interface_spec.get('inet_addr_ipv6')
    addresses = []
    if inet_addr_ipv4:
        addresses.append(interface_spec.get('inet_addr_ipv4'))
    if inet_addr_ipv6:
        addresses.append(interface_spec.get('inet_addr_ipv6'))

    # sanity checks / supportability checks on the interface
    if interface_spec.get('use_dhcp') is True:
        raise InterfaceSetupException(
            'Cannot support interface %s, use_dhcp == True', ifname)
    if not addresses:
        raise InterfaceSetupException('Interface %s has no addresses', ifname)

    # check if base interface exists on the host (w/o VLAN)
    if ipdbs.host.interfaces.get(base_ifname) is None:
        raise InterfaceSetupException(
            "Interface %s was not found in host netns\n"
            "Found the following interfaces %s"
            % (base_ifname, ipdbs.host.interfaces.keys()))
    logging.info("Found interface %s in host namespace" % base_ifname)

    # if this is a VLAN interface, check if that exists on the host too
    if vlan_id:
        # it's a VLAN interface
        if ipdbs.host.interfaces.get(ifname) is None:
            logging.warn("VLAN interface %s was not found in host netns",
                         ifname)
            logging.warn("Creating VLAN interface %s", ifname)
            try:
                ipdbs.host.create(ifname=ifname,
                                  kind='vlan',
                                  link=ipdbs.host.interfaces.get(
                                      base_ifname),
                                  vlan_id=vlan_id).commit()
            except Exception as e:
                raise InterfaceSetupException(
                    'Unable to create VLAN interface %s on host\n%s'
                    % (ifname, e))
            logging.warn("Created VLAN interface %s", ifname)
        else:
            logging.info("Found existing VLAN interface %s in "
                         "host namespace", ifname)

    # at this point, ifname should correspond with either an existing
    # host interface, or an existing/created host VLAN interface
    host_if = ipdbs.host.interfaces.get(ifname)

#         # make sure that the interface isn't the default route for the host
#         default_if = host_ipdb.interfaces[host_ipdb.routes['default']['oif']]
#         default_ifname = default_if['ifname']
#         if default_ifname == ifname:
#             raise InterfaceSetupException(
#                 "Interface %s is the host's default interface" % (ifname))

    # check if the host interface is online
    if host_if.operstate != 'UP':
        logging.warn("Interface %s not up on host, bringing up", ifname)
        try:
            host_if.up().commit()
        except Exception as e:
            raise InterfaceSetupException(
                "Unable to start interface %s on host:\n%s" % (
                    ifname, e))
    logging.info("Interface %s is online on host", ifname)

    # make sure the addresses we're adding aren't bound to the host
    for addr in addresses:
        for existing_addr_tuple in host_if.ipaddr:
            # use ipaddress.ip_interface to ensure a fair comparison
            existing_addr = "%s/%s" % existing_addr_tuple
            if (ipaddress.ip_interface(str(existing_addr)) ==
                    ipaddress.ip_interface(addr)):
                raise InterfaceSetupException(
                    "Address %s already bound to host interface %s",
                    addr, ifname)

    # handle setting up a corresponding interface in the container
    _create_and_configure_macvlan_interface(
        ipdbs.host, host_if, ctr_ifname, addresses, ipdbs.container,
        CONTAINER_NETNS_NAME, passthru=True)

    logging.info("Interface %s is connected to container namespace as %s",
                 ifname, ctr_ifname)

    
def _create_and_configure_macvlan_interface(parent_ipdb, parent_if,
                                            child_ifname, child_addresses,
                                            child_ipdb=None,
                                            child_net_ns_fd=None,
                                            passthru=False,
                                            macvlan_mode="vepa"):
    """Create and configure (enable + setup IPs) a MACVLAN interface.

    If a child interface with the same name already exists, we inspect it and
    use it if it matches the spec. Otherwise, it will be destroyed.

    If child_ipdb and child_net_ns_fd is specified, the interface will be moved
    from the parent namespace to the child namespace. 
    
    If parent interface use a specific macvlan_mode, set up it.
    """
    # pass to our create handler
    child_if = _create_macvlan_interface(parent_ipdb, parent_if, child_ifname,
                                         child_ipdb, child_net_ns_fd, passthru,
                                         macvlan=macvlan_mode)

    # configure the interface
    if child_ipdb and child_ipdb != parent_ipdb:
        # To avoid a possible race with netlink broadcast messages, we must
        # get a new child IPDB object. This is because the passed child IPDB
        # object may have not yet processed the new interface update.
        #
        # We must clone the underlying Netlink object, as the IPDB context
        # manager will close it during return (giving as an FB closed message).
        with IPDB(nl=child_ipdb.nl.clone(), **IPDB_DEFAULTS) as child_ipdb:
            # the child interface should exist now
            child_if = child_ipdb.interfaces.get(child_ifname, None)
            if not child_if:
                raise InterfaceSetupException(
                    "Newly created child interface %s not found "
                    "in child namespace", child_ifname)
            # bring the interface up (if needed) and set up its addresses
            _start_interface(child_if)
            _setup_interface_addresses(child_if, child_addresses)
    else:
        # bring the interface up (if needed) and set up its addresses
        _start_interface(child_if)
        _setup_interface_addresses(child_if, child_addresses)


def _create_macvlan_interface(parent_ipdb, parent_if, child_ifname,
                              child_ipdb=None, child_net_ns_fd=None,
                              passthru=False, destroy_stale_ifs=True,
                              macvlan="vepa"):
    """Create a MACVLAN interface using parent_ifname as the base interface.

    If a child interface with the same name already exists, we inspect it and
    use it if it matches the spec.

    If `destroy_stale_ifs` is set, any existing child interface with the same
    name but incorrect spec will be destroyed. Otherwise, an exception will be
    raised if there is an existing child interface with an incorrect spec.   

    If child_ipdb and child_net_ns_fd is specified, the interface will be moved
    from the parent namespace to the child namespace. 
    """

    if ((child_net_ns_fd and not child_ipdb) or
            (not child_net_ns_fd and child_ipdb)):
        raise InterfaceSetupException(
            "Must provide child network namespace FD and IPDB")
    if not child_ipdb:
        child_ipdb = parent_ipdb

    # handle any existing interface
    child_if = child_ipdb.interfaces.get(child_ifname, None)
    if child_if:
        logging.info("Found an existing interface named %s", child_ifname)

        # check if it's set up properly
        child_if_setup_properly = _is_existing_macvlan_interface(
            parent_if, child_if, passthru=passthru)

        # remove the interface if it isn't setup properly
        if child_if_setup_properly is False:
            if destroy_stale_ifs:
                _remove_interface(child_if)
                child_if = None
            else:
                raise InterfaceSetupException(
                    "Existing child interface %s has incorrect specification")

    # at this point, child_if is either set and valid, or set to None
    # in which case, we need to create the interface
    if child_if:
        return child_if

    # handle extra config parameters
    extra_create_params = {}

    # activate macvlan_mode if not specified to passthru
    if passthru:
        extra_create_params['macvlan_mode'] = 'passthru'
    else:
        extra_create_params['macvlan_mode'] = macvlan

    # create the interface at the parent's IPDB
    child_if = parent_ipdb.create(ifname=child_ifname,
                                  kind='macvlan',
                                  link=parent_if,
                                  **extra_create_params)
    if child_net_ns_fd:
        child_if.net_ns_fd = child_net_ns_fd

    # commit it
    try:
        child_if.commit()
    except Exception as e:
        raise InterfaceSetupException(
            "Unable to create interface %s:\n%s" % (child_ifname, e))

    # check our work
    # if passthru enabled, check the MAC addresses
    if passthru and parent_if.address != child_if.address:
        raise InterfaceSetupException(
            "Passthru enabled but new child MAC != parent MAC")

    # we're done
    return child_if


def _is_existing_macvlan_interface(parent_if, child_if, passthru=False):
    """Returns if a valid MACVLAN interface is already set up.

    Requires the (expected) child interface and parent interface objects.
    """
    # check if existing child interface is a MACVLAN interface
    if getattr(child_if, 'kind', None) != 'macvlan':
        logging.warn(
            "Existing child interface %s is not a MACVLAN interface",
            child_if.ifname)
        return False

    # check if existing interface is connected to the expected parent interface
    parent_if_index = getattr(parent_if, 'index', None)
    child_if_link = getattr(child_if, 'link', None)
    if not parent_if_index or parent_if_index != child_if_link:
        logging.warn(
            "Existing child interface %s is not connected to "
            "parent interface %s",
            child_if.ifname, parent_if.ifname)
        return False

    # run additional checks for passthru mode
    if passthru:
        # check if existing interface is in passthru mode
        if getattr(child_if, 'macvlan_mode', None) != 'passthru':
            logging.warn(
                "Existing child interface %s is not in passthru mode",
                child_if.ifname)
            return False

        # check if existing interface has the same MAC address
        parent_if_address = getattr(parent_if, 'address', None)
        child_if_address = getattr(child_if, 'address', None)
        if not parent_if_address or parent_if_address != child_if_address:
            logging.warn(
                "Existing child interface %s does not have same MAC address "
                "as parent interface %s despite being in passthru mode",
                child_if.ifname, parent_if.ifname)
            return False

    # we're all good! the interface matches the specs
    return True


def _start_interface(interface):
    """Starts an interface if it's not currently up."""
    if interface.operstate != 'UP':
        try:
            interface.up().commit()
        except Exception as e:
            raise InterfaceSetupException(
                "Failure when starting interface %s:\n%s" %
                (interface.ifname, e))
        logging.info("Started interface %s", interface.ifname)


def _remove_interface(interface):
    """Removes an interface."""
    ifname = interface.ifname
    try:
        interface.remove().commit()
    except Exception as e:
        raise InterfaceSetupException(
            'Unable to remove interface %s\n%s'
            % (ifname, e))
    logging.warn("Removed interface %s", ifname)


def _setup_interface_addresses(interface, addresses):
    """Process / set up addresses for an interface object.

    Adds any addresses that are currently missing from the interface. In
    addition, removes (stale) addresses that are bound to the interface
    (except link-local addresses).
    """

    address_objs = set()
    for address in addresses:
        address_objs.add(ipaddress.ip_interface(str(address)))

    # record stale addresses and determine addresses already added
    stale_addresses = []
    for existing_addr_tuple in interface.ipaddr:
        # ignore the address if it is a link-local address
        if ((existing_addr_tuple[0][:4] == 'fe80') and
                (existing_addr_tuple[1] == 64)):
            continue

        # use ipaddress.ip_interface to ensure a fair comparison
        existing_addr = "%s/%s" % existing_addr_tuple
        existing_addr_obj = ipaddress.ip_interface(str(existing_addr))

        # check if the existing address is one to be added
        if existing_addr_obj in address_objs:
            logging.info("Address %s is bound to interface %s",
                         existing_addr,
                         interface.ifname)
            continue

        # if we're here, the address is stale
        stale_addresses.append(existing_addr)

    # remove stale addresses
    for stale_addr in stale_addresses:
        try:
            interface.del_ip(stale_addr).commit()
        except Exception as e:
            raise InterfaceSetupException(
                "Failure when removing stale address %s from %s:\n%s"
                % (stale_addr, interface.ifname, e))
        logging.info("Removed stale address %s from interface %s",
                     stale_addr,
                     interface.ifname)

    # build a set of existing address objects (following purge of stales)
    existing_addr_objs = set()
    for existing_addr_tuple in interface.ipaddr:
        existing_addr = "%s/%s" % existing_addr_tuple
        existing_addr_obj = ipaddress.ip_interface(str(existing_addr))
        existing_addr_objs.add(existing_addr_obj)

    # add new addresses
    for addr in addresses:
        # use ipaddress.ip_interface to ensure a fair comparison
        if ipaddress.ip_interface(addr) in existing_addr_objs:
            # address is already added
            continue
        try:
            interface.add_ip(addr).commit()
        except Exception as e:
            raise InterfaceSetupException(
                "Failure when adding address %s to %s:\n%s"
                % (addr, interface.ifname, e))
        logging.info(
            "Added address %s to interface %s", addr, interface.ifname)
