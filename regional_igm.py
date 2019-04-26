# Copyright 2017 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and

# limitations under the License.
"""Creates an autoscaled managed instance group."""
# This consists of multiple resources:
# - Instance Template to define the properties for each VM
#      The image and machine size are hardcoded. They could be parameterized
# - Instance Group Manager
# - Autoscaler to grow and shrink the size of the the Instance Group
# - Load Balancer to distribute traffice to the VMs.

import yaml

URL_BASE = 'https://www.googleapis.com/compute/v1/projects/'

# Every Python Template needs to have the GenerateConfig() or generate_config()
# method
# This method is called by DM in expansion and must return either:
#    - the yaml format required by DM
#    - a python dictionary representing the yaml (this is more efficient)


def GenerateConfig(context):
  """Generates the configuration."""

  config = {'resources': []}

  deployment = context.env['deployment']
  dse_it = deployment + 'dse-it'
  dse_seed_0_igm = deployment + 'dse-seed-0-igm'
  dse_seed_1_igm = deployment + 'dse-seed-1-igm'
  dse_non_seed_pool_igm = deployment + 'dse-non-seed-pool-igm'
  region = context.properties['region']
  dse_subnet = deployment + '-dse-subnet-' + region
  network = URL_BASE + context.env['project'] + '/global/networks/default'
  cidr = '10.8.0.0/16'

  # Create a dictionary which represents the resources
  # (Intstance Template, IGM, etc.)
  resources = [
      {
          'name': dse_subnet,
          'type': 'compute.v1.subnetwork',
          'properties': {
                'name': dse_subnet,
                'description': 'Subnetwork of %s in %s' % (network, dse_subnet),
                'ipCidrRange': cidr,
                'region': region,
                'network': network
          }
      },
      {
          # Create the Instance Template
          'name': dse_it,
          'type': 'compute.v1.instanceTemplate',
          'properties': {
              'properties': {
                  'machineType':
                      context.properties['machineType'],
                  'networkInterfaces': [{
                      'network': network,
                      'subnetwork': '$(ref.%s.selfLink)' % dse_subnet,
                      'accessConfigs': [{
                          'name': 'External NAT',
                          'type': 'ONE_TO_ONE_NAT'
                      }]
                  }],
                  'disks': [{
                      'deviceName': 'boot-disk',
                      'type': 'PERSISTENT',
                      'boot': True,
                      'autoDelete': True, 
                      'initializeParams': {
                          'sourceImage':
                            URL_BASE + 'datastax-public/global/images/datastax-enterprise-ubuntu-1604-xenial-v20180424', 
                          'diskType': context.properties['dataDiskType'],
                          'diskSizeGb': context.properties['diskSize']
                      }
                    }, 
		    {
                      'deviceName': 'vm-data-disk',
                      'type': 'PERSISTENT',
                      'boot': False,
                      'autoDelete': True,
                      'initializeParams': {
                          'diskType': 'pd-standard',
                          'diskSizeGb':'20' 
                      }
                    }
                  ],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ]
                  }
              }
          }
      },
      {
          # Instance Group Manager
          'name': dse_seed_0_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-instance',
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_it,
              'targetSize': 1
          }
      },
      {   
          # Instance Group Manager
          'name': dse_seed_1_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-instance',
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_it,
              'targetSize': 1
          },
          'metadata': {
              'dependsOn': [
                   dse_seed_0_igm,
              ]
          }
      },
      {
          # Instance Group Manager
          'name': dse_non_seed_pool_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-instance',
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_it,
              'targetSize': 3
          },
          'metadata': {
              'dependsOn': [
                   dse_seed_1_igm,
              ]
          }
      }
  ]

  config['resources'] = resources
  outputs = [
        {
            'name': 'project',
            'value': context.env['project']
        },
        {
            'name': 'IG region',
            'value': '$(ref.' + dse_seed_0_igm + '.region)'
        }
  ]
  config['outputs'] = outputs

  return yaml.dump(config)

