#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Fairness metrics metrics
"""

from nova import loadables
from numbers import Number


class BaseMetric(object):
    class ResourceInformation(object):
        def __init__(self, cpu_time, disk_bytes_read, disk_bytes_written,
                     network_bytes_received, network_bytes_transmitted,
                     memory_used, compute_host=None, user_id=None,
                     instance_name=None):
            self._cpu_time = cpu_time
            self._disk_bytes_read = disk_bytes_read
            self._disk_bytes_written = disk_bytes_written
            self._network_bytes_received = network_bytes_received
            self._network_bytes_transmitted = network_bytes_transmitted
            self._memory_used = memory_used
            self._compute_host = compute_host
            self._user_id = user_id
            self._instance_name = instance_name

        def __mul__(self, other):
            """ Overwrite the multiplication operator

            Possible divisions are:
                ResourceInformation * number or
                ResourceInformation * ResourceInformation

            :param other: Number, ResourceInformation
            :return: Multiplication result
            :rtype: nova.fairness.metrics.BaseMetric.ResourceInformation
            """
            if isinstance(other, Number):
                return type(self)(cpu_time=self.cpu_time * other,
                                  disk_bytes_read=self.disk_bytes_read * other,
                                  disk_bytes_written=
                                  self.disk_bytes_written * other,
                                  network_bytes_received=
                                  self.network_bytes_received * other,
                                  network_bytes_transmitted=
                                  self.network_bytes_transmitted * other,
                                  memory_used=self.memory_used*other,
                                  compute_host=self.compute_host,
                                  user_id=self.user_id,
                                  instance_name=self.instance_name)
            elif isinstance(other, type(self)):
                return type(self)(cpu_time=self.cpu_time * other.cpu_time,
                                  disk_bytes_read=
                                  self.disk_bytes_read * other.disk_bytes_read,
                                  disk_bytes_written=
                                  self.disk_bytes_written *
                                  other.disk_bytes_written,
                                  network_bytes_received=
                                  self.network_bytes_received *
                                  other.network_bytes_received,
                                  network_bytes_transmitted=
                                  self.network_bytes_transmitted *
                                  other.network_bytes_transmitted,
                                  memory_used=
                                  self.memory_used *
                                  other.memory_used,
                                  compute_host=self.compute_host,
                                  user_id=self.user_id,
                                  instance_name=self.instance_name)

        def __add__(self, other):
            """ Overwrite the addition operator

            Possible divisions are:
                ResourceInformation + number or
                ResourceInformation + ResourceInformation

            :param other: Number, ResourceInformation
            :return: Addition result
            :rtype: nova.fairness.metrics.BaseMetric.ResourceInformation
            """
            if isinstance(other, Number):
                return type(self)(cpu_time=self.cpu_time + other,
                                  disk_bytes_read=self.disk_bytes_read + other,
                                  disk_bytes_written=
                                  self.disk_bytes_written + other,
                                  network_bytes_received=
                                  self.network_bytes_received + other,
                                  network_bytes_transmitted=
                                  self.network_bytes_transmitted + other,
                                  memory_used=self.memory_used+other,
                                  compute_host=self.compute_host,
                                  user_id=self.user_id,
                                  instance_name=self.instance_name)
            elif isinstance(other, type(self)):
                return type(self)(cpu_time=self.cpu_time + other.cpu_time,
                                  disk_bytes_read=
                                  self.disk_bytes_read + other.disk_bytes_read,
                                  disk_bytes_written=
                                  self.disk_bytes_written +
                                  other.disk_bytes_written,
                                  network_bytes_received=
                                  self.network_bytes_received +
                                  other.network_bytes_received,
                                  network_bytes_transmitted=
                                  self.network_bytes_transmitted +
                                  other.network_bytes_transmitted,
                                  memory_used=
                                  self.memory_used +
                                  other.memory_used,
                                  compute_host=self.compute_host,
                                  user_id=self.user_id,
                                  instance_name=self.instance_name)

        def __div__(self, other):
            """ Overwrite the division operator

            Possible divisions are:
                ResourceInformation / number or
                ResourceInformation / ResourceInformation

            :param other: Number, ResourceInformation
            :return: Division result
            :rtype: nova.fairness.metrics.BaseMetric.ResourceInformation
            """
            if isinstance(other, Number):
                return type(self)(cpu_time=self.cpu_time / other,
                                  disk_bytes_read=self.disk_bytes_read / other,
                                  disk_bytes_written=
                                  self.disk_bytes_written / other,
                                  network_bytes_received=
                                  self.network_bytes_received / other,
                                  network_bytes_transmitted=
                                  self.network_bytes_transmitted / other,
                                  memory_used=self.memory_used/other,
                                  compute_host=self.compute_host,
                                  user_id=self.user_id,
                                  instance_name=self.instance_name)
            elif isinstance(other, type(self)):
                return type(self)(cpu_time=self.cpu_time / other.cpu_time,
                                  disk_bytes_read=
                                  self.disk_bytes_read / other.disk_bytes_read,
                                  disk_bytes_written=
                                  self.disk_bytes_written /
                                  other.disk_bytes_written,
                                  network_bytes_received=
                                  self.network_bytes_received /
                                  other.network_bytes_received,
                                  network_bytes_transmitted=
                                  self.network_bytes_transmitted /
                                  other.network_bytes_transmitted,
                                  memory_used=
                                  self.memory_used /
                                  other.memory_used,
                                  compute_host=self.compute_host,
                                  user_id=self.user_id,
                                  instance_name=self.instance_name)

        @property
        def compute_host(self):
            return self._compute_host

        @compute_host.setter
        def compute_host(self, value):
            self._compute_host = value

        @property
        def user_id(self):
            return self._user_id

        @user_id.setter
        def user_id(self, value):
            self._user_id = value

        @property
        def instance_name(self):
            return self._instance_name

        @instance_name.setter
        def instance_name(self, value):
            self._instance_name = value

        @property
        def cpu_time(self):
            return self._cpu_time

        @cpu_time.setter
        def cpu_time(self, value):
            self._cpu_time = value

        @property
        def disk_bytes_written(self):
            return self._disk_bytes_written

        @disk_bytes_written.setter
        def disk_bytes_written(self, value):
            self._disk_bytes_written = value

        @property
        def disk_bytes_read(self):
            return self._disk_bytes_read

        @disk_bytes_read.setter
        def disk_bytes_read(self, value):
            self._disk_bytes_read = value

        @property
        def network_bytes_received(self):
            return self._network_bytes_received

        @network_bytes_received.setter
        def network_bytes_received(self, value):
            self._network_bytes_received = value

        @property
        def network_bytes_transmitted(self):
            return self._network_bytes_transmitted

        @network_bytes_transmitted.setter
        def network_bytes_transmitted(self, value):
            self._network_bytes_transmitted = value

        @property
        def memory_used(self):
            return self._memory_used

        @memory_used.setter
        def memory_used(self, value):
            self._memory_used = value

    _description = "This is the Base class for all metrics."

    def __init__(self):
        pass

    def get_description(self):
        return self._description

    def map(self, supply, demands, endowments, user_count):
        pass


class MetricsLoader(loadables.BaseLoader):
    def __init__(self):
        super(MetricsLoader, self).__init__(BaseMetric)


def all_metrics():
    """  Return a list of fairness metrics classes found in this directory.

    This method is used as a configuration entry to allow easier adding
    of additional metrics

    :return: List of metrics classes
    :rtype: list
    """
    return MetricsLoader().get_all_classes()
