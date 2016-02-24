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
Client side of the fairness RPC API.
"""

from oslo.config import cfg
from oslo import messaging

from nova import rpc

rpcapi_opts = [
    cfg.StrOpt("fairness_topic",
               default="fairness",
               help="The topic fairness proxy nodes listen on"),
]

CONF = cfg.CONF
CONF.register_opts(rpcapi_opts)

rpcapi_cap_opt = cfg.StrOpt('fairness',
                            help="Set a version cap for messages \
                            sent to fairness services")
CONF.register_opt(rpcapi_cap_opt, 'upgrade_levels')


class FairnessAPI(object):
    """Client side of the fairness rpc API.

    API version history:

        1.0 - Initial version.

    """

    VERSION_ALIASES = {
        'juno': '1.0',
    }

    def __init__(self, topic=None, server=None):
        super(FairnessAPI, self).__init__()
        topic = topic if topic else CONF.fairness_topic
        target = messaging.Target(topic=topic, server=server, version='2.0')
        version_cap = self.VERSION_ALIASES.get(CONF.upgrade_levels.fairness,
                                               CONF.upgrade_levels.fairness)
        self.client = rpc.get_client(target, version_cap=version_cap)

    def set_metric_on_host(self, context, metric_name, host):
        """ Call the 'set_metric' method on a specific host

        :param context: Request context
        :type context: nova.context.RequestContext
        :param metric_name: Name of the metric class
        :type metric_name: str
        :param host: Host to call through RPC
        :type host: str
        :return: Success or failure from RPC
        :rtype: dict
        """
        version = '1.0'
        callcontext = self.client.prepare(server=host, version=version)
        return callcontext.call(context, 'set_metric',
                                metric_name=metric_name)
