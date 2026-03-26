import json
import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])

def lambda_handler(event, context):
    """Update task status"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        task_id = event['task_id']
        status = event['status']
        
        tasks_table.update_item(
            Key={'task_id': task_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': status}
        )
        
        logger.info(f"Task {task_id} status updated to {status}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'task_id': task_id,
                'status': status
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
