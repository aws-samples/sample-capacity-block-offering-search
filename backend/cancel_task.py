import json
import boto3
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')

tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
}

TERMINAL = ('COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED')


def _resp(status_code, body):
    return {'statusCode': status_code, 'headers': CORS_HEADERS, 'body': json.dumps(body)}


def lambda_handler(event, context):
    """Cancel (stop) a running task's Step Functions execution.

    Idempotent: cancelling an already-finished task is a no-op. Partial results
    already written to DynamoDB are kept; no CSV is generated for a cancelled task.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        task_id = event.get('pathParameters', {}).get('task_id')
        if not task_id:
            return _resp(400, {'error': 'Missing task_id'})

        response = tasks_table.get_item(Key={'task_id': task_id})
        task = response.get('Item')
        if not task:
            return _resp(404, {'error': 'Task not found'})

        status = task.get('status')
        if status in TERMINAL:
            # Already finished — nothing to cancel.
            return _resp(200, {'task_id': task_id, 'status': status, 'cancelled': False,
                               'message': f'Task already {status}'})

        execution_arn = task.get('execution_arn')
        if execution_arn:
            try:
                sfn.stop_execution(
                    executionArn=execution_arn,
                    cause='Cancelled by user',
                    error='UserCancelled'
                )
                logger.info(f"Stopped execution for task {task_id}")
            except sfn.exceptions.ExecutionDoesNotExist:
                logger.warning(f"Execution not found for task {task_id}; marking cancelled anyway")
            except Exception as e:
                # If the execution already stopped/completed, treat as best-effort
                logger.warning(f"stop_execution for task {task_id} returned: {str(e)}")

        tasks_table.update_item(
            Key={'task_id': task_id},
            UpdateExpression='SET #s = :s, cancelled_at = :t',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':s': 'CANCELLED',
                ':t': datetime.now(timezone.utc).isoformat()
            }
        )

        logger.info(f"Task {task_id} cancelled")
        return _resp(200, {'task_id': task_id, 'status': 'CANCELLED', 'cancelled': True})

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return _resp(500, {'error': str(e)})
