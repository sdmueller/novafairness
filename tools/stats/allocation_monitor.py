# coding=utf-8
import binascii
import curses
import datetime
import libvirt
from subprocess import check_output
import re
import socket
import sys
import time
import xml.etree.ElementTree


class StatisticsScreen(object):

    def __init__(self):
        self._window = curses.initscr()
        self._line = 1
        self.blank = ' ' * 100
        self._running = True

    def output(self, text):
        self._window.addstr(self._line, 0, self.blank)
        self._window.addstr(self._line, 0, text)
        self._line += 1

    def refresh(self):
        self._line = 1
        self._window.refresh()
        now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        self._window.addstr(1, 100, now)

    def running(self):
        return self._running

    def shutdown(self):
        self._running = False
        curses.endwin()


def _convert_value_range(value, old_minimum, old_maximum,
                         new_minimum, new_maximum):
        old_range = old_maximum - old_minimum
        new_range = new_maximum - new_minimum
        new_value = (((value-old_minimum)*new_range)/old_range) + new_minimum
        if new_value < new_minimum:
            return new_minimum
        if new_value > new_maximum:
            return new_maximum
        return new_value


def _make_bar(value, minimum, maximum, label, statscreen):
    tick = "#"
    bar = label
    bar += ' ' * (5-len(label))
    converted_value = _convert_value_range(value, minimum, maximum, 1, 50)
    bar += tick * converted_value
    if not 50-converted_value < len(str(value))+2:
        bar += ' ' + str(value) + ' '
        bar += ' ' * (50-converted_value-(len(str(value))+2))
    else:
        bar += ' ' * (50-converted_value)
    bar += '| ' + str(maximum) + '\r'
    assert isinstance(statscreen, StatisticsScreen),\
        "statscreen has to be of type StatisticsScreen"
    statscreen.output(bar)


def _find_bridge_interface():
    """ Find virtual ethernet interface belonging to the
        software bridge br100
    """

    brctl = check_output(['brctl', 'show'])
    iface = None
    if brctl is not None:
        m = re.search(r'br100\s+.+?\s+(yes|no)\s+(eth\d)', brctl)
        if m:
            iface = m.group(2)

    return iface


def main():
    conn = libvirt.open()
    domains = conn.listAllDomains()
    domains = [domain for domain in domains if domain.isActive()]
    bridge_interface = _find_bridge_interface()
    statscreen = StatisticsScreen()
    while statscreen.running():
        try:
            statscreen.refresh()
            for domain in domains:
                domain_xml = check_output(['virsh', 'dumpxml', domain.name()])
                root = xml.etree.ElementTree.fromstring(domain_xml)
                vm_name = root.find('metadata').find(
                    '{http://openstack.org/xmlns/libvirt/nova/1.0}instance')\
                    .find('{http://openstack.org/xmlns/libvirt/nova/1.0}name')\
                    .text
                statscreen.output("Resource allocation for " + vm_name + ":")
                # CPU shares
                if root.find('cputune') is not None:
                    shares = domain.schedulerParameters()['cpu_shares']
                    _make_bar(int(shares), 1, 100, 'CPU', statscreen)
                # Memory soft-limit
                if root.find('memtune') is not None:
                    mem_limit = domain.memoryParameters()['soft_limit']
                    max_memory = domain.maxMemory()
                    _make_bar(int(mem_limit), 1, int(max_memory), 'MEM',
                              statscreen)
                # Disk weight
                weight = domain.blkioParameters()['weight']
                _make_bar(weight, 100, 1000, 'DISK', statscreen)
                # Net priority
                mac_address = root.find('devices/interface')[0]\
                    .attrib['address']
                arp = check_output(['arp', '-an'])
                m_ip_address = re.search(r'([0-9.]*).\sat\s'+mac_address, arp)
                if m_ip_address:
                    ip_address = m_ip_address.group(1)
                    ip_address_hex = binascii.hexlify(
                            socket.inet_aton(ip_address))
                    tc_output = check_output(['tc', 'filter', 'list',
                                              'dev', bridge_interface])
                    m_flowid = re.search(r'flowid\s1:(\d+)\s*match\s' +
                                         ip_address_hex + '/ffffffff\sat',
                                         tc_output)
                    if m_flowid:
                        flowid = int(m_flowid.group(1))
                        _make_bar(flowid, 1, 98, 'NET', statscreen)
                time.sleep(1)
        except KeyboardInterrupt:
            statscreen.shutdown()

if __name__ == '__main__':
    sys.exit(main())
