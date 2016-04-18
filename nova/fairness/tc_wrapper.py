from nova import utils
from nova.openstack.common import log as logging
from nova.openstack.common import processutils

# TODO interface is hardcoded in _find_bridge_interface() for now, as resource_allocation method does not account for the specific configuration in use
def hfsc_proportional_share(interface, prios, upper_limit):
    """
    Sets up the HFSC qdisc with the specified priorities for proportional sharing

    Example tc commands for three hosts:
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

    :param interface: interface on which to set the qdisc
    :param prios: instance priorities mapped to their ip
    :param upper_limit: upper limit for network bandwidth
    :return: boolean (false in case of error)
    """

    result = True

    #get default class
    default_class = max(prios)

    #calculate sum of all priorities
    prio_sum = 0
    for prio in prios:
        prio_sum += prio

    # add root qdisc
    try:
        utils.execute('tc', 'qdisc', 'add', 'dev', interface,
                      'root', 'handle', '1:', 'hfsc', 'default', default_class, run_as_root=True)
    except processutils.ProcessExecutionError:
        result = False

    # add root class
    try:
        utils.execute('tc', 'class', 'add', 'dev', interface,
                      'parent', '1:', 'classid', '1:99', 'hfsc', 'sc',
                      'rate', '%dmbit' % upper_limit, 'ul', 'rate',
                      '%dmbit' % upper_limit, run_as_root=True)
    except processutils.ProcessExecutionError:
        result = False

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
    """
    Resets the qdisc

    :param interface: interface on which to reset qdisc
    :return: false in case of error
    """
    
    try:
        utils.execute('tc', 'qdisc', 'del', 'dev', interface,
                      'root', run_as_root=True)
    except processutils.ProcessExecutionError:
        return False
