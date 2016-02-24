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
:mod:`nova.fairness` -- Module to enforce cloud-wide multi-resource fairness
=====================================================

.. automodule:: nova.fairness
   :platform: Unix
   :synopsis: Module to collect RUI, compute a fairness scalar based on
              these metrics and enforce fairness on compute host.
"""

import nova.openstack.common.importutils


FAIRNESS_API = 'nova.fairness.api.API'


def API(*args, **kwargs):
    importutils = nova.openstack.common.importutils
    class_name = FAIRNESS_API
    return importutils.import_object(class_name, *args, **kwargs)
