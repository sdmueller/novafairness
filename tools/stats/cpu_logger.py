import csv
import os
from subprocess import check_output
import sys
import time

csv_path = '/var/log/nova/fairness/'


def get_cputime(hz, pid):
    stats = check_output(['cat', '/proc/' + pid + '/stat'])
    stats_array = stats.split(' ')
    return 10*((float(stats_array[13]) + float(stats_array[14]))/hz)


def write_cputime(filename, process_name, cputime):
    with open(csv_path + filename, 'a') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow((str(time.time()), str(process_name), str(cputime)))
        csv_file.close()


def main():
    params = sys.argv
    if len(params) <= 1:
        print "Usage: python cpu_logger.py INSTANCE_NAME"
        exit(1)
    filename = params[1] + '-cpu.csv'
    pid = check_output(['cat', '/var/run/libvirt/qemu/' + params[1] + '.pid'])
    hz = os.sysconf(2)
    with open(csv_path + filename, 'w') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(('TIMESTAMP', 'INSTANCE_NAME', 'CPU_TIME'))
        csv_file.close()
    last_cputime = None
    while True:
        cputime = get_cputime(hz, pid)
        if last_cputime is not None:
            write_cputime(filename, params[1], cputime - last_cputime)
            last_cputime = cputime
        else:
            last_cputime = cputime
        time.sleep(10)

if __name__ == '__main__':
    sys.exit(main())
