import json
import re
import time
import boto3
import logging
import os
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm = boto3.client('ssm')

instance_types_parameter = os.environ['INSTANCE_TYPES_PARAMETER']

# Capacity Blocks are only offered for accelerated families (P = GPU, Trn = Trainium).
# Match families like p4d / p5 / p5e / p6-b200 / trn1 / trn2.
TARGET_FAMILY_RE = re.compile(r'^(p\d|trn\d)')


def is_target_family(instance_type):
    """Return True for P/Trn accelerated families that support Capacity Blocks."""
    family = instance_type.split('.')[0]
    return bool(TARGET_FAMILY_RE.match(family))


def extract_specs(instance_type_info):
    """Extract accelerator type/count from a describe_instance_types entry.

    Returns None when the instance type has no GPU/Neuron accelerator.
    """
    gpu = instance_type_info.get('GpuInfo')
    if gpu and gpu.get('Gpus'):
        count = sum(g.get('Count', 0) for g in gpu['Gpus'])
        name = gpu['Gpus'][0].get('Name', '')
        return {'acceleratorType': name, 'acceleratorCount': count}

    neuron = instance_type_info.get('NeuronInfo')
    if neuron and neuron.get('NeuronDevices'):
        count = sum(d.get('Count', 0) for d in neuron['NeuronDevices'])
        name = neuron['NeuronDevices'][0].get('Name', '')
        return {'acceleratorType': name, 'acceleratorCount': count}

    return None


def probe_capacity_block(ec2, instance_type):
    """Classify whether an instance type is Capacity-Block-purchasable in this region.

    Being in a P/Trn family with accelerators is NOT sufficient, and CB support
    is region-specific:
      - p3dn / trn1.2xlarge / trn1n.32xlarge are rejected in every region
        ("... is not supported ...").
      - p4d supports CB only in us-east-1/us-east-2/us-west-2, even though the
        instance type is *offered* for normal launch in ~13 regions.
      - Some regions have no CB API at all ("The action ... is not valid ...").

    The authoritative signal is describe_capacity_block_offerings itself.

    Returns one of:
      'supported'          - CB works for this (type, region)
      'unsupported_type'   - this type is not CB-eligible in this region
      'region_unavailable' - the CB API is not available in this region
      'transient'          - throttled/unknown error; skip for now, retry next run
    """
    now = datetime.now(timezone.utc)
    for attempt in range(3):
        try:
            # A valid near-future window (the CB API only allows ~8 days ahead)
            ec2.describe_capacity_block_offerings(
                InstanceType=instance_type,
                InstanceCount=1,
                StartDateRange=now + timedelta(days=1),
                EndDateRange=now + timedelta(days=6),
                CapacityDurationHours=24
            )
            return 'supported'
        except ClientError as e:
            error = e.response.get('Error', {})
            code = error.get('Code', '')
            message = error.get('Message', '').lower()

            if code in ('RequestLimitExceeded', 'CapacityBlockDescribeLimitExceeded'):
                time.sleep(5)
                continue
            if 'is not valid' in message or code in ('UnsupportedOperation', 'InvalidAction'):
                return 'region_unavailable'
            if 'not supported' in message:
                return 'unsupported_type'
            logger.warning(f"CB probe inconclusive for {instance_type}: {code} {message}")
            return 'transient'

    return 'transient'


def get_enabled_regions():
    """List regions enabled for this account."""
    ec2 = boto3.client('ec2')
    response = ec2.describe_regions()
    return sorted(r['RegionName'] for r in response['Regions'])


def get_offered_target_types(ec2):
    """Return the set of P/Trn instance types offered in the region of this client."""
    offered = set()
    paginator = ec2.get_paginator('describe_instance_type_offerings')
    for page in paginator.paginate(LocationType='region'):
        for offering in page['InstanceTypeOfferings']:
            instance_type = offering['InstanceType']
            if is_target_family(instance_type):
                offered.add(instance_type)
    return offered


def get_specs_for_types(ec2, instance_types):
    """Fetch accelerator specs for the given instance types (known in this region)."""
    specs = {}
    types = list(instance_types)
    # describe_instance_types accepts up to 100 instance types per call
    for i in range(0, len(types), 100):
        chunk = types[i:i + 100]
        paginator = ec2.get_paginator('describe_instance_types')
        for page in paginator.paginate(InstanceTypes=chunk):
            for info in page['InstanceTypes']:
                spec = extract_specs(info)
                if spec:
                    specs[info['InstanceType']] = spec
    return specs


def discover_instance_types():
    """Build the instance-types config by querying EC2 across all enabled regions.

    Schema matches the frontend/aggregate expectations:
        {
          "<instance_type>": {
            "name": "<instance_type>",
            "acceleratorType": "H200",
            "acceleratorCount": 8,
            "regions": { "us-east-1": {}, ... }
          }, ...
        }

    Pricing is intentionally NOT included here; the per-accelerator rate is
    derived at aggregation time from the real UpfrontFee returned by the
    describe_capacity_block_offerings API.
    """
    config = {}
    specs_cache = {}

    for region in get_enabled_regions():
        try:
            ec2 = boto3.client('ec2', region_name=region)
            offered = get_offered_target_types(ec2)
            if not offered:
                continue

            missing = [t for t in offered if t not in specs_cache]
            if missing:
                specs_cache.update(get_specs_for_types(ec2, missing))

            supported_here = 0
            for instance_type in sorted(offered):
                spec = specs_cache.get(instance_type)
                if not spec:
                    # Offered but not an accelerator instance (no GPU/Neuron info)
                    continue

                status = probe_capacity_block(ec2, instance_type)
                if status == 'region_unavailable':
                    # The CB API is not available in this region at all; stop probing it
                    logger.info(f"{region}: Capacity Block API unavailable, skipping region")
                    break
                if status != 'supported':
                    # 'unsupported_type' (e.g. p3dn / trn1.2xlarge / p4d in this
                    # region) or 'transient' — do not list this (type, region)
                    continue

                entry = config.setdefault(instance_type, {
                    'name': instance_type,
                    'acceleratorType': spec['acceleratorType'],
                    'acceleratorCount': spec['acceleratorCount'],
                    'regions': {}
                })
                entry['regions'][region] = {}
                supported_here += 1

            logger.info(f"{region}: {supported_here} Capacity-Block-supported instance types")
        except Exception as e:
            # Never let a single region failure abort the whole refresh
            logger.warning(f"Failed to scan region {region}: {str(e)}")

    return config


def lambda_handler(event, context):
    """Discover accelerated instance types via EC2 API and refresh the SSM parameter.

    Invoked on deploy (CDK Trigger) and on a daily schedule (EventBridge).
    Defensive by design: partial failures are logged, and if discovery yields
    nothing the existing SSM value (deploy-time seed) is left untouched.
    """
    logger.info(f"Received event: {json.dumps(event) if event else '{}'}")

    try:
        config = discover_instance_types()

        if not config:
            logger.warning("Discovery returned no instance types; keeping existing SSM value")
            return {'statusCode': 200, 'body': json.dumps({'updated': False, 'reason': 'no_data'})}

        ssm.put_parameter(
            Name=instance_types_parameter,
            Value=json.dumps(config),
            Type='String',
            Overwrite=True,
            Tier='Intelligent-Tiering'
        )

        logger.info(f"Updated {instance_types_parameter} with {len(config)} instance types")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'updated': True,
                'instance_type_count': len(config),
                'instance_types': sorted(config.keys())
            })
        }
    except Exception as e:
        logger.error(f"Error refreshing instance types: {str(e)}", exc_info=True)
        # Do not raise: on deploy this runs inside a CDK Trigger and a raise
        # would fail the deployment. The seed/previous SSM value remains valid.
        return {'statusCode': 500, 'body': json.dumps({'updated': False, 'error': str(e)})}
