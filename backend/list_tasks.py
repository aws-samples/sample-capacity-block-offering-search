import json
import boto3
import logging
import base64
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])

def lambda_handler(event, context):
    """List all tasks with pagination"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        limit = int(query_params.get('limit', 20))
        next_token = query_params.get('next_token')
        
        # Decode next_token if provided
        exclusive_start_key = None
        if next_token:
            try:
                exclusive_start_key = json.loads(base64.b64decode(next_token).decode('utf-8'))
            except Exception as e:
                logger.warning(f"Invalid next_token: {str(e)}")
        
        # Query using GSI
        query_params = {
            'IndexName': 'CreatedAtIndex',
            'KeyConditionExpression': 'partition_key = :pk',
            'ExpressionAttributeValues': {':pk': 'TASK'},
            'ScanIndexForward': False,  # Descending order (newest first)
            'Limit': limit
        }
        
        if exclusive_start_key:
            query_params['ExclusiveStartKey'] = exclusive_start_key
        
        response = tasks_table.query(**query_params)
        
        tasks = response.get('Items', [])
        last_evaluated_key = response.get('LastEvaluatedKey')
        
        # Encode next_token
        next_token_response = None
        if last_evaluated_key:
            next_token_response = base64.b64encode(
                json.dumps(last_evaluated_key).encode('utf-8')
            ).decode('utf-8')
        
        logger.info(f"Retrieved {len(tasks)} tasks")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'tasks': tasks,
                'next_token': next_token_response,
                'has_more': last_evaluated_key is not None
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
