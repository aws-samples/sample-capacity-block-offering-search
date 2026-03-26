import json
import boto3
import logging
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
results_table = dynamodb.Table(os.environ['RESULTS_TABLE_NAME'])
tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])

def get_state(task_id, state_key):
    """Get current state for region+instance_type combination"""
    try:
        response = results_table.get_item(
            Key={
                'task_id': task_id,
                'result_key': f'STATE#{state_key}'
            }
        )
        return response.get('Item', {})
    except Exception as e:
        logger.warning(f"Failed to get state for {state_key}: {str(e)}")
        return {}

def update_state(task_id, state_key, max_capacity, search_date):
    """Update state with new max capacity and search date"""
    try:
        results_table.put_item(Item={
            'task_id': task_id,
            'result_key': f'STATE#{state_key}',
            'max_capacity': max_capacity,
            'last_search_date': search_date,
            'updated_at': datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Updated state for {state_key}: max_capacity={max_capacity}, search_date={search_date}")
    except Exception as e:
        logger.error(f"Failed to update state for {state_key}: {str(e)}")

def binary_search_capacity(region, instance_type, start_date, end_date, duration_hours, min_capacity=1):
    """Binary search for maximum available capacity
    
    Args:
        min_capacity: Starting point for binary search (default 1)
    """
    ec2 = boto3.client('ec2', region_name=region)
    
    left = min_capacity
    right = 64
    max_available = 0
    best_offerings = []
    
    while left <= right:
        mid = (left + right) // 2
        retry_count = 0
        
        while retry_count < 3:
            try:
                logger.info(f"{region}: Checking capacity for count={mid}")
                response = ec2.describe_capacity_block_offerings(
                    InstanceType=instance_type,
                    InstanceCount=mid,
                    StartDateRange=start_date,
                    EndDateRange=end_date,
                    CapacityDurationHours=duration_hours
                )
                
                if response['CapacityBlockOfferings']:
                    max_available = mid
                    best_offerings = [
                        {
                            **offering,
                            'StartDate': offering['StartDate'].isoformat() if isinstance(offering.get('StartDate'), datetime) else offering.get('StartDate'),
                            'EndDate': offering['EndDate'].isoformat() if isinstance(offering.get('EndDate'), datetime) else offering.get('EndDate')
                        }
                        for offering in response['CapacityBlockOfferings']
                    ]
                    logger.info(f"{region}: Found capacity at count={mid}")
                    left = mid + 1
                else:
                    logger.info(f"{region}: No capacity at count={mid}")
                    right = mid - 1
                break
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code in ['RequestLimitExceeded', 'CapacityBlockDescribeLimitExceeded']:
                    retry_count += 1
                    if retry_count >= 3:
                        logger.error(f"{region}: Max retries reached for count={mid}, error={error_code}")
                        raise
                    
                    # CapacityBlockDescribeLimitExceeded needs longer wait
                    wait_time = 20 if error_code == 'CapacityBlockDescribeLimitExceeded' else 10
                    logger.warning(f"{region}: {error_code} at count={mid}, retry {retry_count}/3, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    raise
    
    return max_available, best_offerings

def lambda_handler(event, context):
    """Handle single subtask query"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        task_id = event['task_id']
        subtask = event['subtask']
        
        region = subtask['region']
        instance_type = subtask['instance_type']
        search_date = subtask['search_date']
        start_date = datetime.fromisoformat(subtask['start_date'].replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(subtask['end_date'].replace('Z', '+00:00'))
        duration_hours = subtask['duration_hours']
        
        logger.info(f"Processing: {region}, {instance_type}, {search_date}")
        
        # Get current state for this region+instance_type
        state_key = f"{region}#{instance_type}"
        state = get_state(task_id, state_key)
        max_capacity_so_far = int(state.get('max_capacity', 0))  # Convert Decimal to int
        
        # Check if already maxed out
        if max_capacity_so_far == 64:
            skip_reason = f"Skipping {search_date}: already maxed out at 64"
            logger.info(skip_reason)
            
            # Save skipped result to DynamoDB
            result_key = f"{region}#{instance_type}#{search_date}"
            results_table.put_item(Item={
                'task_id': task_id,
                'result_key': result_key,
                'region': region,
                'instance_type': instance_type,
                'search_date': search_date,
                'max_instance_count': 64,
                'offerings': [],
                'error': skip_reason,
                'created_at': datetime.now(timezone.utc).isoformat()
            })
            
            # Update counter
            tasks_table.update_item(
                Key={'task_id': task_id},
                UpdateExpression='ADD completed_subtasks :inc',
                ExpressionAttributeValues={':inc': 1}
            )
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'task_id': task_id,
                    'skipped': True,
                    'reason': 'maxed_out'
                })
            }
        
        # Binary search with optimized starting point
        min_capacity = max(max_capacity_so_far, 1)
        logger.info(f"Binary search range: [{min_capacity}, 64]")
        
        max_count, offerings = binary_search_capacity(
            region, instance_type, start_date, end_date, duration_hours, min_capacity
        )
        
        # Check if capacity decreased
        if max_count < max_capacity_so_far:
            skip_reason = f"Skipping {search_date}: capacity {max_count} < max {max_capacity_so_far}"
            logger.info(skip_reason)
            
            # Save skipped result to DynamoDB
            result_key = f"{region}#{instance_type}#{search_date}"
            results_table.put_item(Item={
                'task_id': task_id,
                'result_key': result_key,
                'region': region,
                'instance_type': instance_type,
                'search_date': search_date,
                'max_instance_count': max_count,
                'offerings': [],
                'error': skip_reason,
                'created_at': datetime.now(timezone.utc).isoformat()
            })
            
            # Update counter
            tasks_table.update_item(
                Key={'task_id': task_id},
                UpdateExpression='ADD completed_subtasks :inc',
                ExpressionAttributeValues={':inc': 1}
            )
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'task_id': task_id,
                    'skipped': True,
                    'reason': 'capacity_decreased',
                    'current_capacity': max_count,
                    'max_capacity_so_far': max_capacity_so_far
                })
            }
        
        # Update state with new max capacity
        if max_count > max_capacity_so_far:
            update_state(task_id, state_key, max_count, search_date)
        
        # Save result to DynamoDB
        result_key = f"{region}#{instance_type}#{search_date}"
        results_table.put_item(Item={
            'task_id': task_id,
            'result_key': result_key,
            'region': region,
            'instance_type': instance_type,
            'search_date': search_date,
            'max_instance_count': max_count,
            'offerings': offerings,
            'error': None,
            'created_at': datetime.now(timezone.utc).isoformat()
        })
        
        # Update completed_subtasks counter
        tasks_table.update_item(
            Key={'task_id': task_id},
            UpdateExpression='ADD completed_subtasks :inc',
            ExpressionAttributeValues={':inc': 1}
        )
        
        logger.info(f"Completed: {region}, {instance_type}, {search_date}, max_count={max_count}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'task_id': task_id,
                'result_key': result_key,
                'max_instance_count': max_count
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        
        # Save error to DynamoDB
        try:
            result_key = f"{region}#{instance_type}#{search_date}"
            results_table.put_item(Item={
                'task_id': task_id,
                'result_key': result_key,
                'region': region,
                'instance_type': instance_type,
                'search_date': search_date,
                'max_instance_count': 0,
                'offerings': [],
                'error': str(e),
                'created_at': datetime.now(timezone.utc).isoformat()
            })
            
            # Still update counter
            tasks_table.update_item(
                Key={'task_id': task_id},
                UpdateExpression='ADD completed_subtasks :inc',
                ExpressionAttributeValues={':inc': 1}
            )
        except Exception as save_error:
            logger.error(f"Failed to save error: {str(save_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
