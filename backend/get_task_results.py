import json
import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])
bucket_name = os.environ['RESULTS_BUCKET_NAME']

def lambda_handler(event, context):
    """Get task results presigned URL"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Get task_id from path parameters
        task_id = event.get('pathParameters', {}).get('task_id')
        
        if not task_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing task_id'})
            }
        
        # Get task metadata
        response = tasks_table.get_item(Key={'task_id': task_id})
        task = response.get('Item')
        
        if not task:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Task not found'})
            }
        
        status = task.get('status')
        s3_url = task.get('s3_url')
        
        if status != 'COMPLETED':
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Task not completed',
                    'status': status
                })
            }
        
        if not s3_url:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Results not found'})
            }
        
        # Generate presigned URL (6 hours)
        s3_key = s3_url.replace(f"s3://{bucket_name}/", "")
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=21600  # 6 hours
        )
        
        logger.info(f"Generated presigned URL for task {task_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'task_id': task_id,
                'status': status,
                's3_url': s3_url,
                'presigned_url': presigned_url,
                'expires_in': 21600
            })
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
