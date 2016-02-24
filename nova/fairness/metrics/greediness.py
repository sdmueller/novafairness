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

import numpy as np

from nova.fairness.metrics import BaseMetric


class GreedinessMetric(BaseMetric):

    _description = "The Greediness metric as developed at CSG UZH."

    def __init__(self):
        super(GreedinessMetric, self).__init__()
        self.floating_error = 0.00000000001
        self.normalizer = 1.0

    @staticmethod
    def _greediness_raw(endowments, demands, factor, discount):
        """ Calculate greediness costs for all instances

        :param endowments: Instance endowment information
        :type endowments: numpy.array
        :param demands: Instance demand information
        :type demands: numpy.array
        :param factor: Global norm based on the cloud supply
        :type factor: numpy.array
        :param discount: Discount factor
        :param discount: float
        :return: NP array with a metric for each instance
        """
        def gez(a):
            if a > 0:
                return a * 1.
            return 0.

        def lez(a):
            if a < 0:
                return a * 1.
            return 0.

        def duc(a):
            if a > -1:
                return a * 1.
            return -1.

        def not_zero(a):
            if a != 0:
                return a * 1.
            return -1.

        diff_to_equal_share = demands - endowments
        maxi = np.vectorize(gez)
        mini = np.vectorize(lez)
        make_at_least_minus_one = np.vectorize(duc)
        make_not_zero = np.vectorize(not_zero)
        pos_dem = maxi(diff_to_equal_share)
        neg_dem = mini(diff_to_equal_share)
        ratio = np.divide(np.sum(pos_dem, axis=0),
                          make_not_zero(np.sum(neg_dem, axis=0)))
        return np.sum((pos_dem - (discount *
                                  neg_dem *
                                  make_at_least_minus_one(ratio))) *
                      factor, axis=1)

    def _initialize_raw(self, supply, demands, endowments, user_count):
        """ Initialize all input parameters and calculate the global norm

        :param supply: Cloud supply
        :type supply: numpy.array
        :param demands: Instance demand information
        :type demands: numpy.array
        :param endowments: Instance endowment information
        :type endowments: numpy.array
        :param user_count: Amount of users with active instances
        :type user_count: int
        :return: Global norm
        :rtype: numpy.array
        """

        assert isinstance(supply, np.ndarray), \
            'First parameter must be np.array'

        assert isinstance(demands, np.ndarray), \
            'Second parameter must be np.array'

        assert isinstance(endowments, np.ndarray), \
            'Third parameter must be np.array'

        assert isinstance(user_count, int), \
            'Fourth parameter must be int'

        assert len(supply) == demands.shape[1],\
            'Supply and demands must have same length'

        assert (demands >= 0).all(),\
            'Demands cannot be negative'

        assert endowments.shape == demands.shape,\
            'Demands and endowments must have same shape'
        assert (endowments >= 0).all(),\
            'Endowments cannot be negative'
        assert (np.sum(endowments, axis=0) <=
                supply + self.floating_error).all(), \
            'Endowments exceed supply'

        norm = np.divide(user_count * self.normalizer / (1.0 * len(supply)),
                         supply)

        return {
            'norm': norm,
        }

    def map(self, supply, demands, endowments, user_count):
        """ Map a cost to each instance

        :param supply: Cloud supply
        :type supply: nova.fairness.metrics.BaseMetric.ResourceInformation
        :param demands: Instance demand information
        :type demands: nova.fairness.metrics.BaseMetric.ResourceInformation
        :param endowments: Instance endowment information
        :type endowments: nova.fairness.metrics.BaseMetric.ResourceInformation
        :param user_count: Amount of users with active instances
        :type user_count: int
        :return: List with costs for the instances
        :rtype: list
        """
        assert isinstance(supply, BaseMetric.ResourceInformation),\
            "Supply must be a ResourceInformation object"
        assert isinstance(demands, dict),\
            "Demands must be a dictionary."
        assert isinstance(endowments, dict),\
            "Endowments must be a dictionary."
        assert isinstance(user_count, int),\
            "user_count must be an int."

        supply_array = np.array([supply.cpu_time,
                                 supply.disk_bytes_read,
                                 supply.disk_bytes_written,
                                 supply.network_bytes_received,
                                 supply.network_bytes_transmitted,
                                 supply.memory_used])
        demand_arrays = np.array([])
        endowment_arrays = np.array([])
        instance_infos = list()
        for instance_name, demand in demands.iteritems():
            demand_item = np.array([demand.cpu_time,
                                    demand.disk_bytes_read,
                                    demand.disk_bytes_written,
                                    demand.network_bytes_received,
                                    demand.network_bytes_transmitted,
                                    demand.memory_used])
            endowment = endowments[instance_name]
            endowment_item = np.array([endowment.cpu_time,
                                       endowment.disk_bytes_read,
                                       endowment.disk_bytes_written,
                                       endowment.network_bytes_received,
                                       endowment.network_bytes_transmitted,
                                       endowment.memory_used])
            if demand_arrays.shape[0] == 0:
                demand_arrays = np.vstack([demand_item])
            else:
                demand_arrays = np.vstack([demand_arrays, demand_item])
            if endowment_arrays.shape[0] == 0:
                endowment_arrays = np.vstack([endowment_item])
            else:
                endowment_arrays = np.vstack([endowment_arrays, endowment_item])

            instance_info = dict()
            instance_info['instance_name'] = demand.instance_name
            instance_info['compute_host'] = demand.compute_host
            instance_info['user_id'] = demand.user_id
            instance_infos.append(instance_info)

        init = self._initialize_raw(supply_array, demand_arrays,
                                    endowment_arrays, user_count)
        greediness_array = self._greediness_raw(endowment_arrays,
                                                demand_arrays,
                                                init['norm'],
                                                discount=1.0)
        result = dict()
        result['compute_host'] = supply.compute_host
        result['global_norm'] = init['norm'].tolist()

        for counter in range(len(greediness_array)):
            instance = dict()
            normalized_endowment = np.sum(endowment_arrays[counter] *
                                          init['norm'])
            instance['compute_host'] = instance_infos[counter]['compute_host']
            instance['user_id'] = instance_infos[counter]['user_id']
            instance['normalized_endowment'] = normalized_endowment
            instance['heaviness'] = float(greediness_array[counter])
            result[instance_infos[counter]['instance_name']] = instance

        return result
