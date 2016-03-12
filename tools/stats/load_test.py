import csv
import libvirt
import os.path
import re
from subprocess import call
from subprocess import check_output
from subprocess import Popen
import sys
import time
from xml.dom import minidom


csv_path = '/var/log/nova/fairness/'
# interval length in seconds
experiment_duration = 15


def _find_domain_ip(domain):
    """ Find IP address of libvirt domain

    :param domain: The instance domain
    :type domain: libvirt.virDomain
    """

    # find mac address of domain
    out = domain.XMLDesc()
    xml_desc = minidom.parseString(out)
    mac = xml_desc.getElementsByTagName('mac')[0]\
        .attributes['address'].value

    # find ip address of domain
    arp = check_output(['arp', '-an'])
    if arp is not None:
        m = re.search(r'\((.+)\) at ' + re.escape(mac), arp)

        if m:
            return m.group(1)
    else:
        # instance not ready;
        # <incomplete>, mac not found
        return False


def _write_results(load, interval, instances, services):
    filename = str(len(instances)) + "VM"
    with open(csv_path + filename, 'a') as csv_file:
        csv_writer = csv.writer(csv_file)
        row = str(load) + "," + str(interval) + ","
        for instance in instances.iteritems():
            cpu_time = int(instance['cpu_stop_time']) - int(instance['cpu_start_time'])
            row += str(cpu_time) + ","
        if 'nova-compute' in services:
            row += str(services['nova-compute']['cpu_stop_time'] - services['nova-compute']['cpu_start_time']) + ","
        if 'nova-network' in services:
            row += str(services['nova-network']['cpu_stop_time'] - services['nova-network']['cpu_start_time']) + ","
        if 'nova-api-metadata' in services:
            row += str(services['nova-api-metadata']['cpu_stop_time'] -
                       services['nova-api-metadata']['cpu_start_time']) + ","
        if 'nova-fairness' in services:
            row += str(services['nova-fairness']['cpu_stop_time'] - services['nova-fairness']['cpu_start_time']) + ","
        csv_writer.writerow(row)
        csv_file.close()


def _get_cpu_time(pid):
    stats = check_output(['cat', '/proc/' + pid + '/stat'])
    stats_array = stats.split(' ')
    return (float(stats_array[13]) + float(stats_array[14])) / 100


def main():
    params = sys.argv
    if len(params) <= 1:
        print "Usage python load_test.py LOAD(True/False)"
        exit(1)
    conn = libvirt.open()
    domains = conn.listAllDomains()
    instances = dict()
    load = bool(params[1])

    for domain in domains:
        if domain.isActive():
            instances[domain.name()] = dict()
            instances[domain.name()]['name'] = domain.name()
            pid = check_output(['cat', '/var/run/libvirt/qemu/' + domain.name() + '.pid'])
            instances[domain.name()]['pid'] = pid
            ip = _find_domain_ip(domain)
            instances[domain.name()]['ip'] = ip

    if not os.path.isfile(csv_path + str(len(instances)) + "VM"):
        with open(csv_path + str(len(instances)) + "VM", 'w') as csv_file:
            csv_writer = csv.writer(csv_file)
            instances_string = ""
            for instance_name, instance in instances:
                instances_string += instance_name + ","
            csv_writer.writerow("LOAD", "INTERVAL_LENGTH," + instances_string + "NOVA_COMPUTE",
                                "NOVA_NETWORK", "NOVA_API_METADATA", "NOVA_FAIRNESS")

    # Get PIDs of nova services
    services = dict()
    ps = check_output(['ps', '-aux'])
    compute_match = re.search(r'nova\s*(\d+).*/usr/bin/python /usr/bin/nova-compute', ps)
    if compute_match:
        services['nova-compute'] = dict()
        services['nova-compute']['pid'] = int(compute_match.group(1))
    network_match = re.search(r'nova\s*(\d+).*/usr/bin/python /usr/bin/nova-network', ps)
    if network_match:
        services['nova-network'] = dict()
        services['nova-network']['pid'] = int(network_match.group(1))
    api_metadata_match = re.search(r'nova\s*(\d+).*/usr/bin/python /usr/bin/nova-api-metadata', ps)
    if api_metadata_match:
        services['nova-api-metadata'] = dict()
        services['nova-api-metadata']['pid'] = int(api_metadata_match.group(1))
    fairness_match = re.search(r'nova\s*(\d+).*/usr/bin/python /usr/bin/nova-fairness', ps)
    if fairness_match:
        services['nova-fairness'] = dict()
        services['nova-fairness']['pid'] = int(fairness_match.group(1))

    intervals = [0, 1, 2, 4, 8, 16]

    for interval in intervals:
        call(["sed", "-i", "s/rui_collection_interval=.*/rui_collection_interval=" + str(interval) + "/g",
              "/etc/nova/nova.conf"])
        for service_name, service in services:
            service['cpu_start_time'] = _get_cpu_time(service['pid'])
        for instance_name, instance in instances.iteritems():
            instance['cpu_start_time'] = _get_cpu_time(instance['pid'])
            if load:
                Popen(["ssh", "-l", "ubuntu", instance['ip'], "stress", "--cpu", "2", "-t", "5s"])
        time.sleep(experiment_duration)
        for service_name, service in services:
            service['cpu_stop_time'] = _get_cpu_time(service['pid'])
        for instance in instances:
            instance['cpu_stop_time'] = _get_cpu_time(instance['pid'])
        _write_results(load, interval, instances, services)

if __name__ == '__main__':
    sys.exit(main())
