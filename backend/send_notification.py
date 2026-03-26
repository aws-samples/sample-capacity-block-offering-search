import json
import boto3
import logging
from datetime import datetime
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
s3 = boto3.client('s3')

tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])
sns_topic_arn = os.environ['SNS_TOPIC_ARN']
bucket_name = os.environ['RESULTS_BUCKET_NAME']

def lambda_handler(event, context):
    """Send notification email via SNS"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        task_id = event['task_id']
        
        # Get task metadata
        response = tasks_table.get_item(Key={'task_id': task_id})
        task = response.get('Item')
        
        if not task:
            raise Exception(f"Task {task_id} not found")
        
        parameters = task.get('parameters', {})
        s3_url = task.get('s3_url', '')
        created_at = task.get('created_at', '')
        completed_at = datetime.utcnow().isoformat()
        total_subtasks = task.get('total_subtasks', 0)
        completed_subtasks = task.get('completed_subtasks', 0)
        
        # Generate presigned URL (6 hours)
        s3_key = s3_url.replace(f"s3://{bucket_name}/", "")
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=21600  # 6 hours
        )
        
        # Count results by status
        # For simplicity, we'll use completed_subtasks as a proxy
        found_capacity = completed_subtasks  # Simplified
        no_capacity = 0
        failed = total_subtasks - completed_subtasks
        
        # Build email message
        instances = parameters.get('instances', [])
        instance_types_str = ', '.join([inst.get('type', '') for inst in instances])
        all_regions = set()
        for inst in instances:
            all_regions.update(inst.get('regions', []))
        regions_str = ', '.join(sorted(all_regions))
        
        subject = "EC2 Capacity Block 查询完成"
        
        message = f"""您好，

您提交的容量查询任务已完成。

任务 ID: {task_id}
提交时间: {created_at}
完成时间: {completed_at}

查询参数：
- 实例类型: {instance_types_str}
- 持续时间: {parameters.get('duration')} 天
- 开始日期: {parameters.get('start_date')}
- 预测天数: {parameters.get('forecast_days')}
- 区域: {regions_str}

结果摘要：
- 总查询数: {total_subtasks} 个
- 已完成: {completed_subtasks} 个
- 失败: {failed} 个

下载结果 CSV：
{presigned_url}
(链接有效期 6 小时)

---
EC2 Capacity Block Search
"""
        
        # Publish to SNS
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        
        # Update task status to COMPLETED
        tasks_table.update_item(
            Key={'task_id': task_id},
            UpdateExpression='SET #status = :status, completed_at = :completed_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':completed_at': completed_at
            }
        )
        
        logger.info(f"Notification sent for task {task_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'task_id': task_id,
                'status': 'COMPLETED',
                'notification_sent': True
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
