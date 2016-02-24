# Copyright 2011 OpenStack Foundation
# All Rights Reserved.
#
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

from webob import exc

import nova
from nova.api.openstack import common
from nova import fairness
from nova import compute
from nova import exception
from nova.api.openstack.compute.views import addresses as view_addresses
from nova.api.openstack import wsgi
from nova.api.openstack import xmlutil
from nova.i18n import _


class ActionDeserializer(wsgi.MetadataXMLDeserializer):
    """Deserializer to handle xml-formatted server action requests.

    Handles standard server attributes as well as optional metadata
    and personality attributes
    """

    def default(self, string):
        dom = xmlutil.safe_minidom_parse_string(string)
        action_node = dom.childNodes[0]
        action_name = action_node.tagName

        return {'body': {action_name: 'null'}}


class MappersTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('metrics')
        elem = xmlutil.SubTemplateElement(root, 'mapper', selector='metrics')
        elem.set('name')
        elem.set('description')
        return xmlutil.MasterTemplate(root, 1, nsmap=mapper_nsmap)

    mapper_nsmap = {None: xmlutil.XMLNS_V11, 'atom': xmlutil.XMLNS_ATOM}


class Controller(wsgi.Controller):
    """The nova fairness API controller"""

    _view_builder_class = view_addresses.ViewBuilder

    def __init__(self, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self._fairness_api = fairness.API()
        self._compute_api = compute.API()

    def _get_metrics(self):
        return self._fairness_api.get_metrics()

    def _check_metric_exists(self, metric_name):
        metrics_dict = self._get_metrics()
        for metric in metrics_dict['metrics']:
            if metric['metric']['name'] == metric_name:
                return True
        return False

    @wsgi.serializers(xml=MappersTemplate)
    def index(self, req):
        """ List possible fairness metrics that can be used.

        The list serves as an orientation for users of the API
        to manually set the metric through the API
        """
        context = req.environ["nova.context"]
        try:
            metrics = self._get_metrics()
        except exception.Invalid as err:
            raise exc.HTTPBadRequest(explanation=err.format_message())
        return metrics

    @wsgi.response(202)
    @wsgi.serializers(xml=MappersTemplate)
    @wsgi.deserializers(xml=ActionDeserializer)
    @wsgi.action('set-metric')
    def _set_metric(self, req, id, body):
        """ Set the metric for a specific compute host

        The WSGI action method gets mapped to fairness/{host_name}/action
        with a POST body containing for example
        {"set-metric":{"name":"GreedinessMetric"}} to set the
        GreedinessMetric for host {host_name}
        """
        context = req.environ['nova.context']
        metric_name = body['set-metric']['name']
        if self._check_metric_exists(metric_name):
            result = self._fairness_api.set_metric_on_host(context,
                                                           metric_name,
                                                           id)
            return result
        return "{'status':'fail'}"


def create_resource():
    return wsgi.Resource(Controller())
