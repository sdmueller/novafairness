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

"""Handles Fairness API requests."""

import inspect
from oslo.config import cfg

from nova.fairness import metrics
from nova.fairness import rpcapi
from nova.db import base

CONF = cfg.CONF
CONF.import_opt('fairness_topic', 'nova.fairness.rpcapi')


class API(base.Base):
    """API for the fairness service """

    def __init__(self, **kwargs):
        super(API, self).__init__(**kwargs)
        self._rpcapi = rpcapi.FairnessAPI()

    @staticmethod
    def get_metrics():
        """ Go through the metrics dir and get all metrics classes

        Metrics classes inherit from the BaseMetric class

        :return: Dictionary with all metrics classes
        :rtype: dict
        """
        metrics_classes = metrics.all_metrics()
        metrics_classes_dict = {'metrics': []}
        for metric_class in metrics_classes:
            metric_class_dict = {'metric': {}}
            metric_class_name = metric_class.__name__
            if (hasattr(metric_class(), 'get_description') and
                    inspect.ismethod(metric_class.get_description)):
                metric_class_description = metric_class().get_description()
            else:
                metric_class_description = ""
            if metric_class_name is not 'BaseMetric':
                metric_class_dict['metric']['name'] = metric_class_name
                metric_class_dict['metric']['description'] = \
                    metric_class_description
                metrics_classes_dict['metrics'].append(metric_class_dict)

        return metrics_classes_dict

    def set_metric_on_host(self, context, metric_name, host):
        """ Set the active metric on a specific host

        This method calls the RPC API and makes a call to the specified host
        to trigger the "set_metric" method of the FairnessManager class

        :param context: Request context
        :type context: context.RequestContext
        :param metric_name: Metric class name
        :type metric_name: str
        :param host: Host to be called
        :type host: str
        :return: RPC result
        :rtype: dict
        """
        return self._rpcapi.set_metric_on_host(context, metric_name, host)
