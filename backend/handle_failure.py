import json
import boto3
import logging
from datetime import datetime, timezone
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])
sns_topic_arn = os.environ['SNS_TOPIC_ARN']

def lambda_handler(event, context):
    """Handle task failure"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        task_id = event['task_id']
        error = event.get('error', {})
        
        # Get task metadata
        response = tasks_table.get_item(Key={'task_id': task_id})
        task = response.get('Item')
        
        if not task:
            raise Exception(f"Task {task_id} not found")
        
        parameters = task.get('parameters', {})
        created_at = task.get('created_at', '')
        failed_at = datetime.now(timezone.utc).isoformat()
        
        # Update task status to FAILED
        tasks_table.update_item(
            Key={'task_id': task_id},
            UpdateExpression='SET #status = :status, completed_at = :completed_at, error_message = :error',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'FAILED',
                ':completed_at': failed_at,
                ':error': json.dumps(error)
            }
        )
        
        # Build failure email
        instances = parameters.get('instances', [])
        instance_types_str = ', '.join([inst.get('type', '') for inst in instances])
        all_regions = set()
        for inst in instances:
            all_regions.update(inst.get('regions', []))
        regions_str = ', '.join(sorted(all_regions))
        
        subject = "EC2 Capacity Block 查询失败"
        
        message = f"""您好，

您提交的容量查询任务执行失败。

任务 ID: {task_id}
提交时间: {created_at}
失败时间: {failed_at}

查询参数：
- 实例类型: {instance_types_str}
- 持续时间: {parameters.get('duration')} 天
- 开始日期: {parameters.get('start_date')}
- 预测天数: {parameters.get('forecast_days')}
- 区域: {regions_str}

错误信息：
{json.dumps(error, indent=2)}

请检查参数或稍后重试。

---
EC2 Capacity Block Search
"""
        
        # Publish to SNS
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info(f"Failure notification sent for task {task_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'task_id': task_id,
                'status': 'FAILED',
                'notification_sent': True
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
