import json
import boto3
import logging
import uuid
from datetime import datetime, timedelta
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')

tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])
state_machine_arn = os.environ['STATE_MACHINE_ARN']

def lambda_handler(event, context):
    """Submit a new capacity search task"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
        
        instances = body.get('instances', [])
        duration = body.get('duration')
        start_date_str = body.get('start_date')
        forecast_days = body.get('forecast_days', 0)
        
        if not all([instances, duration, start_date_str]):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Missing required parameters'})
            }
        
        # Generate task_id
        task_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        
        # Generate all search dates
        search_dates = []
        for i in range(forecast_days + 1):
            search_dates.append(start_date + timedelta(days=i))
        
        # Build region-to-subtasks mapping
        region_subtasks_map = {}
        total_subtasks = 0
        
        for instance in instances:
            instance_type = instance.get('type')
            regions = instance.get('regions', [])
            
            for region in regions:
                if region not in region_subtasks_map:
                    region_subtasks_map[region] = []
                
                for search_date in search_dates:
                    end_date = search_date + timedelta(days=duration + 1)
                    region_subtasks_map[region].append({
                        'region': region,
                        'instance_type': instance_type,
                        'search_date': search_date.strftime('%Y-%m-%d'),
                        'start_date': search_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'duration_hours': duration * 24
                    })
                    total_subtasks += 1
        
        # Convert to list format for Step Functions
        regions_with_subtasks = [
            {'region': region, 'subtasks': subtasks}
            for region, subtasks in region_subtasks_map.items()
        ]
        
        # Save task metadata to DynamoDB
        tasks_table.put_item(Item={
            'task_id': task_id,
            'partition_key': 'TASK',
            'status': 'PENDING',
            'parameters': {
                'instances': instances,
                'duration': duration,
                'start_date': start_date_str,
                'forecast_days': forecast_days
            },
            'created_at': created_at,
            'total_subtasks': total_subtasks,
            'completed_subtasks': 0
        })
        
        # Start Step Functions execution
        execution_response = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"task-{task_id}",
            input=json.dumps({
                'task_id': task_id,
                'regions_with_subtasks': regions_with_subtasks
            })
        )
        
        # Update with execution ARN
        tasks_table.update_item(
            Key={'task_id': task_id},
            UpdateExpression='SET execution_arn = :arn',
            ExpressionAttributeValues={':arn': execution_response['executionArn']}
        )
        
        logger.info(f"Task {task_id} submitted successfully")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'task_id': task_id,
                'status': 'PENDING',
                'created_at': created_at,
                'total_subtasks': total_subtasks,
                'parameters': {
                    'instances': instances,
                    'duration': duration,
                    'start_date': start_date_str,
                    'forecast_days': forecast_days
                }
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
