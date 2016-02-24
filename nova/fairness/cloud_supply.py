from datetime import datetime
import multiprocessing
import re
import time

from oslo.config import cfg

from nova import context
from nova import exception
from nova import servicegroup
from nova import utils
from nova.fairness import metrics
from nova.objects import instance as instance_objects
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import processutils


cloud_supply_opts = [
    cfg.IntOpt('max_network_throughput',
               default=1000,
               help='Maximum network throughput available to the instances.'
                    'The unit is Mbit/s.'),
    ]

CONF = cfg.CONF
fairness_group = cfg.OptGroup("fairness", "Fairness configuration options")
CONF.import_opt('host', 'nova.netconf')
CONF.import_opt('cpu_allocation_ratio', 'nova.scheduler.filters.core_filter')
CONF.import_opt('ram_allocation_ratio', 'nova.scheduler.filters.ram_filter')
CONF.import_opt('disk_allocation_ratio', 'nova.scheduler.filters.disk_filter')
CONF.register_group(fairness_group)
CONF.register_opts(cloud_supply_opts, fairness_group)
LOG = logging.getLogger(__name__)


class CloudSupply(object):

    class HostSupply(object):

        def __init__(self, compute_host=None, host_boottime=None,
                     cpu_cores_weighted=None, disk_speeds=None,
                     network_throughput=None, memory_used=None,
                     supply_created_at=None):
            self._compute_host = compute_host
            self._host_boottime = host_boottime
            self._cpu_cores_weighted = cpu_cores_weighted
            self._disk_speeds = disk_speeds
            self._network_throughput = network_throughput
            self._memory_used = memory_used
            self._supply_created_at = supply_created_at

        def _to_dict(self):
            result = dict()
            result['compute_host'] = self._compute_host
            result['host_boottime'] = self._host_boottime
            result['cpu_cores_weighted'] = self._cpu_cores_weighted
            result['disk_speeds'] = self._disk_speeds
            result['network_throughput'] = self._network_throughput
            result['memory_used'] = self._memory_used
            result['supply_created_at'] = self._supply_created_at
            return result

        def to_json(self):
            return jsonutils.dumps(self._to_dict())

        @classmethod
        def _from_dict(cls, data):
            """ Create a HostSupply object from a dict

            :param data: The host supply data stored in a dict
            :type data: dict
            :return: A HostSupply object
            :rtype: nova.fairness.cloud_supply.CloudSupply.HostSupply
            """
            return cls(data['compute_host'], data['host_boottime'],
                       data['cpu_cores_weighted'], data['disk_speeds'],
                       data['network_throughput'], data['memory_used'],
                       data['supply_created_at'])

        @classmethod
        def from_json(cls, json_string):
            """ Create a HostSupply object from a JSON string

            The JSON string is first converted into a dict

            :param json_string: The host supply data stored in a JSON string
            :type json_string: str
            :return: A HostSupply object
            :rtype: nova.fairness.cloud_supply.CloudSupply.HostSupply
            """
            return cls._from_dict(jsonutils.loads(json_string))

        @property
        def compute_host(self):
            return self._compute_host

        @compute_host.setter
        def compute_host(self, value):
            self._compute_host = value

        @property
        def host_boottime(self):
            return self._host_boottime

        @host_boottime.setter
        def host_boottime(self, value):
            self._host_boottime = value

        @property
        def cpu_cores_weighted(self):
            return self._cpu_cores_weighted

        @cpu_cores_weighted.setter
        def cpu_cores_weighted(self, value):
            self._cpu_cores_weighted = value

        @property
        def disk_speeds(self):
            return self._disk_speeds

        @disk_speeds.setter
        def disk_speeds(self, value):
            self._disk_speeds = value

        @property
        def network_throughput(self):
            return self._network_throughput

        @network_throughput.setter
        def network_throughput(self, value):
            self._network_throughput = value

        @property
        def memory_used(self):
            return self._memory_used

        @memory_used.setter
        def memory_used(self, value):
            self._memory_used = value

        @property
        def supply_created_at(self):
            return self._supply_created_at

        @supply_created_at.setter
        def supply_created_at(self, value):
            self._supply_created_at = value

    def __init__(self):
        self.host = CONF.host
        self.ready = False
        self.servicegroup_api = servicegroup.API()
        self._local_supply = self.HostSupply()
        self._bogo_mips = self._get_bogomips()
        self._boot_time = self._get_boottime()
        self._calculate_local_host_supply()
        self._remote_supplies = dict()
        self.add_supply(self._local_supply)

    @property
    def local_bogo_mips(self):
        return self._bogo_mips

    @property
    def local_boot_time(self):
        return self._boot_time

    @property
    def local_supply(self):
        return self._local_supply

    @property
    def user_count(self):
        """ Return number of users running instances in the cloud

        :return: Number of users
        :rtype: int
        """
        fairness_hosts = self.servicegroup_api.get_all("fairness")
        user_ids = set()
        if not isinstance(fairness_hosts, exception.ServiceGroupUnavailable):
            for host in fairness_hosts:
                ctxt = context.RequestContext(None, None, is_admin=True)
                instances = instance_objects.InstanceList().\
                    get_by_host(ctxt, host)
                for instance in instances:
                    user_ids.add(instance.user_id)
        return len(user_ids)

    @property
    def missing_hosts(self):
        """ Return list of hosts still needed to complete the cloud supply

        :return: List of missing hosts
        :rtype: list
        """
        missing_hosts = list()
        fairness_hosts = self.servicegroup_api.get_all("fairness")
        if not isinstance(fairness_hosts, exception.ServiceGroupUnavailable):
            for host in fairness_hosts:
                if host not in self._remote_supplies:
                    missing_hosts.append(host)
        return missing_hosts

    @property
    def cloud_host_count(self):
        if len(self._remote_supplies) > 0:
            return len(self._remote_supplies)
        else:
            return 1

    @staticmethod
    def _get_bogomips():
        """ Get the BogoMIPS of the machine from /proc/cpuinfo

        BogoMIPS values are available for each core, so the average
        value is returned to get an overall rating of the host's performance.
        It is however important to note that BogoMIPS, as the name implies, is
        a completely unscientific measurement of host performance and is only
        used to get an approximate idea of the performance

        :return: BogoMIPS average of the host
        :rtype: int
        """
        bogomips = 1
        try:
            output, error = utils.execute('cat', '/proc/cpuinfo',
                                          run_as_root=True)
            if output is not None:
                m = re.findall(r'bogomips\t:\s(\d+\.\d+)', output)
                if m is not None:
                    bogomips = 0
                    for value in m:
                        bogomips += float(value)
                    bogomips = int(bogomips / len(m))
        except processutils.ProcessExecutionError:
            pass
        return bogomips

    @staticmethod
    def _get_disk_speeds():
        """ Returns the sum of all disk speeds in bytes/s

        :return: Combined disk speeds in bytes/s
        :rtype: int
        """
        speeds = 0
        try:
            disks = list()
            output, error = utils.execute('lsblk', '-io', 'KNAME,TYPE',
                                          run_as_root=True)
            if output is not None:
                for line in output.splitlines():
                    line_segments = line.split(' ')
                    if line_segments[len(line_segments)-1] == 'disk':
                        disks.append(line_segments[0])
            for disk in disks:
                output, error = utils.execute('hdparm', '-t', '/dev/'+disk,
                                              run_as_root=True)
                if output is not None:
                    lines = output.splitlines()
                    line_segments = lines[2].split(' ')
                    speed_in_mbs = line_segments[len(line_segments)-2]
                    speed_in_bytes = float(speed_in_mbs) * 1000000
                    speeds += int(speed_in_bytes)
        except processutils.ProcessExecutionError:
            pass
        return speeds

    @staticmethod
    def _get_installed_memory():
        """ Get the amount of installed memory in kilobytes

        :return: Installed memory in kilobytes
        :rtype: int
        """
        try:
            output, error = utils.execute('free', '-k',
                                          run_as_root=True)
            if output is not None:
                memory = int(output.splitlines()[1].strip().split()[1])
                return memory
            return None
        except processutils.ProcessExecutionError:
            pass
        return None

    @staticmethod
    def _get_boottime():
        """ Reads /proc/stat for the exact boot time

        The boot time is converted to UTC for compatibility with other
        time measurements throughout the service

        :return: Exact date and time of the last boot
        :rtype: datetime
        """
        try:
            output, error = utils.execute('cat', '/proc/stat',
                                          run_as_root=True)
            if output is not None:
                btime = output.split('\n')[5].split(' ')
                assert btime[0] == "btime",\
                    "This system does not allow the read-out of boot time."
                timestamp = btime[1]
                return datetime.utcfromtimestamp(int(timestamp))
        except processutils.ProcessExecutionError:
            pass
        return None

    def _calculate_local_host_supply(self):
        """ Gets local resources available on host

        Local host supply information consists of the resource information
        available on the host. These data-points get sent along with the boot
        time to allow calculation of maximum possible resource consumption
        on the other compute nodes for a given interval as follows:
            - CPU is weighted number of cores * interval in seconds
            - Disk read and write is disk speed in bytes/s * interval in seconds
            - Network tx and rx are network speed in bytes/s * interval in s
            - Used memory is the amount of memory installed in kilobytes
        """
        assert isinstance(self._local_supply, self.HostSupply),\
            "The variable _local_supply must be of type HostSupply"

        self._local_supply.compute_host = self.host
        self._local_supply.host_boottime = self._boot_time

        # CPU cores already multiplied with bogomips to represent
        # the weight of the host's CPU
        self._local_supply.cpu_cores_weighted = (multiprocessing.cpu_count() *
                                                 self._bogo_mips)

        # Combined speeds of all disks in bytes/s
        self._local_supply.disk_speeds = self._get_disk_speeds()

        # Network throughput in bytes/s
        self._local_supply.network_throughput = \
            CONF.fairness.max_network_throughput * 125000

        # Installed memory in kilobytes
        self._local_supply.memory_used = self._get_installed_memory()

        # Set timestamp for creation date of local supply
        self._local_supply.supply_created_at = time.time()

    def get_host_supply(self, interval):
        """ Produce the ResourceInformation object for the local host

        :param interval: Interval for the host supply
        :type interval: int
        :return: Host supply for the local host
        :rtype: nova.fairness.metrics.BaseMetric.ResourceInformation
        """
        host_supply = metrics.BaseMetric.ResourceInformation(
            cpu_time=int(self._local_supply.cpu_cores_weighted * interval),
            disk_bytes_read=int(self._local_supply.disk_speeds * interval),
            disk_bytes_written=int(self._local_supply.disk_speeds * interval),
            network_bytes_received=
            int(self._local_supply.network_throughput * interval),
            network_bytes_transmitted=
            int(self._local_supply.network_throughput * interval),
            memory_used=self._local_supply.memory_used,
            compute_host=self.host)

        return host_supply

    def get_cloud_supply(self, interval):
        """ Produce a combined supply ResourceInformation object for the cloud

        :param interval: Interval for the cloud supply
        :type interval: int
        :return: Host supplies of all hosts in the cloud combined
        :rtype: nova.fairness.metrics.BaseMetric.ResourceInformation
        """
        cloud_supply = metrics.BaseMetric.ResourceInformation(0, 0, 0, 0, 0, 0)
        cloud_supply.compute_host = self.host
        self._filter_offline_hosts()

        for host, supply in self._remote_supplies.iteritems():
            assert isinstance(supply, self.HostSupply),\
                "Host supplies need to be HostSupply objects"

            cloud_supply.cpu_time += \
                int(supply.cpu_cores_weighted * interval)
            cloud_supply.disk_bytes_read += \
                int(supply.disk_speeds * interval)
            cloud_supply.disk_bytes_written += \
                int(supply.disk_speeds * interval)
            cloud_supply.network_bytes_received += \
                int(supply.network_throughput * interval)
            cloud_supply.network_bytes_transmitted += \
                int(supply.network_throughput * interval)
            cloud_supply.memory_used += supply.memory_used

        return cloud_supply

    @staticmethod
    def get_overcommitment():
        """ Get a ResourceInfomration object with the overcommitment ratios

        The ratios are stored in a ResourceInformation object to simplify the
        application of the ratios to a different ResourceInformation object
        like the cloud supply

        :return: Overcommitment ratios
        :rtype: nova.fairness.metrics.BaseMetric.ResourceInformation
        """
        overcommitment = metrics.BaseMetric.ResourceInformation(
                0, 0, 0, 0, 0, 0)

        overcommitment.cpu_time = CONF.cpu_allocation_ratio
        overcommitment.disk_bytes_read = CONF.disk_allocation_ratio
        overcommitment.disk_bytes_written = CONF.disk_allocation_ratio
        overcommitment.network_bytes_received = 1
        overcommitment.network_bytes_transmitted = 1
        overcommitment.memory_used = CONF.ram_allocation_ratio

        return overcommitment

    def _filter_offline_hosts(self):
        """ Remove hosts which no longer run the fairness service

        All hosts running the fairness service are queried through the nova
        conductor and hosts, which are in self._remote_supplies but not in the
        queried list are removed from self._remote_supplies
        """
        fairness_hosts = self.servicegroup_api.get_all("fairness")
        if not isinstance(fairness_hosts, exception.ServiceGroupUnavailable):
            remote_supplies = dict.copy(self._remote_supplies)
            for host, supply in remote_supplies.iteritems():
                if host not in fairness_hosts and not host == self.host:
                    del self._remote_supplies[host]

    def _all_host_supplies_collected(self):
        """ Check if host supplies for all online hosts exist

        All hosts running the fairness service are queried through the nova
        conductor and True is returned, if all hosts are present in
        self._remote_supplies, False otherwise

        :return: True if host supplies for all online hosts exist
        :rtype: bool
        """
        fairness_hosts = self.servicegroup_api.get_all("fairness")
        if not isinstance(fairness_hosts, exception.ServiceGroupUnavailable):
            # Check if all hosts are present in the self._remote_supplies
            # dictionary.
            for host in fairness_hosts:
                if host not in self._remote_supplies:
                    return False
            return True
        else:
            return False

    def check_readiness(self):
        if self._all_host_supplies_collected():
            self.ready = True
        else:
            self.ready = False

    def add_supply(self, supply):
        """ Adds the host supply information received from a compute node

        If supply information for an already stored host is received, the
        creation timestamps of the information are compared and the supply
        information is overwritten if the received information is newer

        :param supply: Raw host supply information
        :type supply: CloudSupply.HostSupply
        """
        assert isinstance(supply, CloudSupply.HostSupply),\
            "Supply must be a HostSupply object."

        if isinstance(supply.host_boottime, unicode):
                supply.host_boottime = datetime.strptime(
                                        supply.host_boottime,
                                        "%Y-%m-%dT%H:%M:%S.000000")
        if supply.compute_host not in self._remote_supplies:
            self._remote_supplies[supply.compute_host] = supply
        else:
            old_timestamp = float(self._remote_supplies[supply.compute_host]
                                  .supply_created_at)
            new_timestamp = float(supply.supply_created_at)
            if new_timestamp > old_timestamp:
                self._remote_supplies[supply.compute_host] = supply
                LOG.debug("Updated host supply for host " +
                          supply.compute_host + ".")
        self.check_readiness()
