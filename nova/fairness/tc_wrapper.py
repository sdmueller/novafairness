from nova import utils
from nova.openstack.common import log as logging
from nova.openstack.common import processutils

"""Setting up tc with HFSC for proportional sharing

    Example for three hosts:
        tc qdisc add dev eth0 root handle 1: hfsc
        tc class add dev eth0 parent 1: classid 1:99 hfsc sc rate 80mbit \
                ul rate 80mbit
        tc class add dev eth0 parent 1:99 classid 1:3 hfsc ls rate 15mbit \
                ul rate 80mbit
        tc class add dev eth0 parent 1:99 classid 1:2 hfsc ls rate 26mbit \
                ul rate 80mbit
        tc class add dev eth0 parent 1:99 classid 1:1 hfsc ls rate 39mbit \
                ul rate 80mbit
        tc filter add dev eth0 parent 1: protocol ip prio 1 \
            u32 match ip src 10.0.0.4 flowid 1:3
        tc filter add dev eth0 parent 1: protocol ip prio 1 u32 \
            match ip src 10.0.0.3 flowid 1:2
        tc filter add dev eth0 parent 1: protocol ip prio 1 u32 \
            match ip src 10.0.0.2 flowid 1:1
    """

# TODO check if qdiscs not already the same, if yes don't delete and set up again

# TODO interface is hardcoded for now as resource_allocation method does not account for the specific configuration in use
def hfsc_proportional_share(interface, prios, upper_limit):
    """

    :rtype: bool
    """

    interface = 'eth0'

    result = True

    # add root qdisc
    try:
        utils.execute('tc', 'qdisc', 'add', 'dev', interface,
                      'root', 'handle', '1:', 'hfsc', run_as_root=True)
    except processutils.ProcessExecutionError:
        result = False

    # add root class
    # TODO add CONF.fairness.hfsc_rate
    try:
        utils.execute('tc', 'class', 'add', 'dev', interface,
                      'parent', '1:', 'classid', '1:99', 'hfsc', 'sc',
                      'rate', '%dmbit' % upper_limit, 'ul', 'rate',
                      '%dmbit' % upper_limit, run_as_root=True)
    except processutils.ProcessExecutionError:
        result = False

    prio_sum = 0
    for prio in prios:
        prio_sum += prio

    # create child classes
    for prio in sorted(prios):
        classid = '1:%s' % prio

        try:
            utils.execute('tc', 'class', 'add', 'dev', interface,
                          'parent', '1:99', 'classid', classid, 'hfsc', 'ls',
                          'rate', '%dmbit' % ((upper_limit * prio) /
                                              prio_sum),
                          'ul', 'rate', '%dmbit' % upper_limit,
                          run_as_root=True)
        except processutils.ProcessExecutionError:
            result = False

        # add filters
        for ip in prios[prio]:
            try:
                utils.execute('tc', 'filter', 'add', 'dev', interface,
                              'parent', '1:', 'protocol', 'ip', 'prio', '1',
                              'u32', 'match', 'ip', 'src', ip, 'flowid',
                              classid, run_as_root=True)
            except processutils.ProcessExecutionError:
                result = False

    return result

def reset_qdisc(interface):
    interface = 'eth0'
    
    try:
        utils.execute('tc', 'qdisc', 'del', 'dev', interface,
                      'root', run_as_root=True)
    except processutils.ProcessExecutionError:
        return False

