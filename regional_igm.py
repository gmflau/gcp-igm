# Copyright 2019 DataStax, Inc. All rights reserved.

import yaml
import random
import string

URL_BASE = 'https://www.googleapis.com/compute/v1/projects/'

def GenerateConfig(context):
  """Generates the configuration."""

  config = {'resources': []}

  deployment = context.env['deployment']
  dse_seed_0_it = deployment + '-dse-seed-0-it'
  dse_seed_1_it = deployment + '-dse-seed-1-it'
  dse_non_seed_it = deployment + '-dse-non-seed-it'
  dev_ops_it = deployment + '-dev-ops-it'
  dse_seed_0_igm = deployment + '-dse-seed-0-igm'
  dse_seed_1_igm = deployment + '-dse-seed-1-igm'
  dse_non_seed_pool_igm = deployment + '-dse-non-seed-pool-igm'
  dev_ops_igm = deployment + '-dev-ops-igm'
  region = context.properties['region']
  dse_subnet = deployment + '-dse-subnet-' + region
  network = URL_BASE + context.env['project'] + '/global/networks/' + context.properties['network']
  cidr = context.properties['subnetCIDR']
  int_ip_octet = cidr.split(".")
  dse_seed_0_ip_addr = int_ip_octet[0] + "."  + int_ip_octet[1] + "." + int_ip_octet[2] + ".2"
  dse_seed_1_ip_addr = int_ip_octet[0] + "."  + int_ip_octet[1] + "." + int_ip_octet[2] + ".3"

  # Generate a random bucket name
  bucket_suffix = ''.join([random.choice(string.ascii_lowercase + string.digits) for n in xrange(10)])
  deployment_bucket = context.env['deployment'] + '-deployment-bucket-' + bucket_suffix

  # DSE seed node startup script
  dse_seed_0_script = '''
      #!/usr/bin/env bash

      # Install and configure the dse seed 0

      sleep 180
      pushd ~ubuntu
      deployment_bucket=''' + deployment_bucket + '''
      echo seed_0 > seed_0
      gsutil cp ./seed_0 gs://$deployment_bucket/
      popd

      '''

  dse_seed_1_script = '''

      pushd ~ubuntu
      deployment_bucket=''' + deployment_bucket + '''
      gsutil cp gs://$deployment_bucket/seed_0 .
      while [ $? -ne 0 ]
      do
          sleep 10s
          gsutil cp gs://$deployment_bucket/seed_0 . 
      done

      # Install and configure the dse seed 1

      sleep 180
      echo seed_1 > seed_1
      gsutil cp ./seed_1 gs://$deployment_bucket/

      # To Do:
      # Check using nodetool status to ensure all DSE nodes are up and joined the DSE cluster
      # Once all up and joined the cluster, do the following:
      # echo dev_ops > dev_ops
      # gsutil cp ./dev_ops gs://$deployment_bucket/

      popd
       
      '''

  dse_non_seed_script = '''
      #!/usr/bin/env bash

      pushd ~ubuntu
      deployment_bucket=''' + deployment_bucket + '''
      gsutil cp gs://$deployment_bucket/seed_1 .
      while [ $? -ne 0 ]
      do
          sleep 10s
          gsutil cp gs://$deployment_bucket/seed_1 .        
      done


      # Install and conifgure non-seed node


      file=`date +'%Y-%m-%d-%HH%MM%SS'`
      echo time > $file
      gsutil cp $file gs://$deployment_bucket/      
      popd

      '''

  dev_ops_script = '''
      #!/usr/bin/env bash

      pushd ~ubuntu
      deployment_bucket=''' + deployment_bucket + '''

      #gsutil cp gs://$deployment_bucket/dev_ops .
      #while [ $? -ne 0 ]
      #do
      #    sleep 10s
      #    gsutil cp gs://$deployment_bucket/dev_ops .
      #done

      # install and configure the dev ops vm below

      gsutil rm gs://$deployment_bucket/*

      popd

      '''
 
  # Create a dictionary which represents the resources
  # (Intstance Template, IGM, etc.)
  resources = [
      {
        'name': deployment_bucket,
        'type': 'storage.v1.bucket',
        'properties': {
            'name': deployment_bucket,
            'lifecycle': {
          	"rule": [ {
      		    "action": {"type": "Delete"},
      		    "condition": {  "age": 1 }
                }]
            }
        }
      },
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
          'name': dse_seed_0_it,
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
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': dse_seed_0_script
                      }]
                  }
              }
          }
      },
      {
          # Create the Instance Template
          'name': dse_seed_1_it,
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
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': dse_seed_1_script
                      }]
                  }
              }
          }
      },
      {
          # Create the Instance Template
          'name': dse_non_seed_it,
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
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': dse_non_seed_script
                      }]
                  }
              }
          }
      },
      {   
          # Create the Instance Template
          'name': dev_ops_it,
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
                  'serviceAccounts': [{
                     'email': 'default',
                     'scopes': ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/cloudruntimeconfig', 'https://www.googleapis.com/auth/devstorage.full_control']
                  }],
                  'metadata': {
                      'dependsOn': [
                          dse_subnet,
                      ],
                      'items': [ {
                          'key': 'startup-script',
                          'value': dev_ops_script
                      }]
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
              'baseInstanceName': deployment + '-dse',
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_seed_0_it,
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
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_seed_1_it,
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
              'instanceTemplate': '$(ref.%s.selfLink)' % dse_non_seed_it,
              'targetSize': 3
          },
          'metadata': {
              'dependsOn': [
                   dse_seed_1_igm,
              ]
          }
      },
      {
          # Instance Group Manager
          'name': dev_ops_igm,
          'type': 'compute.v1.regionInstanceGroupManager',
          'properties': {
              'region': region,
              'baseInstanceName': deployment + '-instance',
              'instanceTemplate': '$(ref.%s.selfLink)' % dev_ops_it,
              'targetSize': 1
          },
          'metadata': {
              'dependsOn': [
                   dse_non_seed_pool_igm,
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
        },
        {
            'name': 'dse_seed_0_ip_addr',
            'value': dse_seed_0_ip_addr
	},
        {
            'name': 'dse_seed_1_ip_addr',
            'value': dse_seed_1_ip_addr
        }
  ]
  config['outputs'] = outputs

  return yaml.dump(config)

