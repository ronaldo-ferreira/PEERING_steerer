"""
Routines for setting up network rules in a Docker container.
"""

import logging
from socket import AF_INET
from socket import AF_INET6
from pyroute2 import IPDB
from pyroute2.netlink.rtnl.fibmsg import FR_ACT_NAMES

from lib.namespaces import get_container_ipdb
from pyroute2.ipdb.rules import Rule

# List of fields our rules must contain (IPDB requirement):
REQUIRED_RULE_FIELDS = ['priority', 'table', 'action']


def _rulekey_to_str(rulekey):
    """Returns a clean string representing a RuleKey (removes unused fields)"""
    base_rule = list("%s=%s" % (k, v)
                     for k, v in rulekey._asdict().items() if v)
    return "RuleKey(%s)" % (", ".join(base_rule))


def check_rule(rulespec):
    for field in REQUIRED_RULE_FIELDS:
        if field not in rulespec:
            raise ValueError('Rule specification must contain field %s', field)


def get_default_rules():
    """Returns RuleKeys for rules that the kernel installs by default."""
    default_rulekeys = [
        # This key only has a default for IPv4
        # RuleKey(action=1, table=253, priority=32767, iifname='',
        # oifname='', fwmark=0, fwmask=0, goto=0, tun_id=0),
        {'table': 253, 'priority': 32767, 'action': 1, 'family': AF_INET},

        # Remaining two rules have defaults for v4 and v6
        # RuleKey(action=1, table=254, priority=32766, iifname='',
        # oifname='', fwmark=0, fwmask=0, goto=0, tun_id=0),
        {'table': 254, 'priority': 32766, 'action': 1, 'family': AF_INET},
        {'table': 254, 'priority': 32766, 'action': 1, 'family': AF_INET6},

        # RuleKey(action=1, table=255, priority=0, iifname='',
        # oifname='', fwmark=0, fwmask=0, goto=0, tun_id=0)
        {'table': 255, 'priority': 0, 'action': 1, 'family': AF_INET},
        {'table': 255, 'priority': 0, 'action': 1, 'family': AF_INET6}
    ]
    return default_rulekeys


def get_config_rules(config, rule_class):
    """Returns RuleKeys for downstream rules specified in config."""
    ip_rules = config.get("ip_rules", {})
    rule_specs = ip_rules.get(rule_class, [])
    generated_rule_specs = []
    for spec in rule_specs:
        # action and priority are parts of the key, so they must be specified
        if 'priority' not in spec:
            spec['priority'] = 32000
        if 'table' in spec and 'action' not in spec:
            spec['action'] = FR_ACT_NAMES['FR_ACT_TO_TBL']
        elif 'goto' in spec and 'action' not in spec:
            spec['action'] = FR_ACT_NAMES['FR_ACT_GOTO']

        if 'family' not in spec:
            for family in [AF_INET, AF_INET6]:
                family_spec = spec.copy()
                family_spec['family'] = family
                check_rule(family_spec)
                generated_rule_specs.append(family_spec)
        else:
            check_rule(spec)
            generated_rule_specs.append(spec)
    return generated_rule_specs


def setup_rules(ipdbs, config):
    """Adds / removes rules so that container ip rules matches config."""
    logging.info("Processing network rules")

    config_rules = []
    config_rules.extend(get_config_rules(config, "downstream"))
    config_rules.extend(get_config_rules(config, "upstream"))
    logging.info("Configuration contains %d rules", len(config_rules))
    config_rules.extend(get_default_rules())
    logging.info("Configuration + default kernel rules = %d rules:",
                 len(config_rules))

    key2spec = dict((Rule.make_key(spec), spec) for spec in config_rules)
    desired_rulekeys = set(key2spec.keys())
    for rule in desired_rulekeys:
        logging.info(_rulekey_to_str(rule))

    failures = 0
    existing_rulekeys = set(ipdbs.container.rules.keys())
    logging.info("Found %d rules installed:", len(existing_rulekeys))
    for rule in ipdbs.container.rules.keys():
        logging.info(_rulekey_to_str(rule))

    to_add = desired_rulekeys.difference(existing_rulekeys)
    to_remove = existing_rulekeys.difference(desired_rulekeys)

    if not to_remove and not to_add:
        logging.info(
            "Rules are up-to-date (current state = desired state)")

    removed = 0
    if to_remove:
        logging.warn("Removing %d stale rules", len(to_remove))
    for rule_to_remove in to_remove:
        logging.warn("Removing %s", _rulekey_to_str(rule_to_remove))
        ipdbs.container.rules[rule_to_remove].remove().commit()
        removed += 1

    added = 0
    if to_add:
        logging.info("Installing %d new rules", len(to_add))
    for rule_to_add in to_add:
        try:
            logging.info("Installing %s", _rulekey_to_str(rule_to_add))
            spec = key2spec[rule_to_add]
            ipdbs.container.rules.add(spec).commit()
            added += 1
        except Exception:
            logging.exception(
                "Failure while installing rule %s",
                (_rulekey_to_str(rule_to_add)))
            failures += 1

    if added or removed:
        logging.info("Currently installed rules:")
        for rule in ipdbs.container.rules.keys():
            logging.info(_rulekey_to_str(rule))

    result_msg = (
        "Finished setting up rules (%d added, %d removed, %d failures)"
        % (added, removed, failures))
    if failures:
        logging.warn(result_msg)
    else:
        logging.info(result_msg)
    return failures
