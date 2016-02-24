import csv
import libvirt
from lxml import etree
import sys
import time

csv_path = '/var/log/nova/fairness/'


def _get_io_devices(xml_doc):
    """get the list of io devices from the xml document."""
    result = {"volumes": [], "ifaces": []}
    try:
        doc = etree.fromstring(xml_doc)
    except Exception:
        return result
    blocks = [('./devices/disk', 'volumes'),
        ('./devices/interface', 'ifaces')]
    for block, key in blocks:
        section = doc.findall(block)
        for node in section:
            for child in node.getchildren():
                if child.tag == 'target' and child.get('dev'):
                    result[key].append(child.get('dev'))
    return result


def get_disk_bytes_transferred(domain, dom_io):
    total_bytes = 0
    for guest_disk in dom_io["volumes"]:
        try:
            stats = domain.blockStats(guest_disk)
            total_bytes += stats[1]
            total_bytes += stats[3]
        except libvirt.libvirtError:
            pass
    return total_bytes


def write_iousage(filename, instance_name, iousage):
    with open(csv_path + filename, 'a') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            (str(time.time()), str(instance_name), str(iousage)))
        csv_file.close()


def main():
    params = sys.argv
    if len(params) <= 1:
        print "Usage: python disk_logger.py INSTANCE_NAME"
        exit(1)
    filename = params[1] + '-disk.csv'
    conn = libvirt.open()
    domain = conn.lookupByName(params[1])
    xml = domain.XMLDesc(0)
    dom_io = _get_io_devices(xml)

    with open(csv_path + filename, 'w') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(('TIMESTAMP', 'INSTANCE_NAME', 'I/O_USAGE'))
        csv_file.close()
    last_iousage = None
    while True:
        iousage = get_disk_bytes_transferred(domain, dom_io)
        if last_iousage is not None:
            write_iousage(filename, params[1], iousage - last_iousage)
            last_iousage = iousage
        else:
            last_iousage = iousage
        time.sleep(10)

if __name__ == '__main__':
    sys.exit(main())
