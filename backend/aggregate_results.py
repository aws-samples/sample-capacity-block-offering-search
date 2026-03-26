import json
import boto3
import logging
import csv
import io
from datetime import datetime, timezone, timedelta
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
ssm = boto3.client('ssm')

results_table = dynamodb.Table(os.environ['RESULTS_TABLE_NAME'])
tasks_table = dynamodb.Table(os.environ['TASKS_TABLE_NAME'])
bucket_name = os.environ['RESULTS_BUCKET_NAME']
instance_types_parameter = os.environ['INSTANCE_TYPES_PARAMETER']

def lambda_handler(event, context):
    """Aggregate results and generate CSV"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        task_id = event['task_id']
        
        # Load instance types config
        param_response = ssm.get_parameter(Name=instance_types_parameter)
        instance_types_config = json.loads(param_response['Parameter']['Value'])
        
        # Query all results for this task
        response = results_table.query(
            KeyConditionExpression='task_id = :tid',
            ExpressionAttributeValues={':tid': task_id}
        )
        
        results = response['Items']
        logger.info(f"Found {len(results)} results for task {task_id}")
        
        # Generate CSV
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        
        # CSV Headers
        headers = [
            'Region',
            'Searched Instance Type',
            'Search Date',
            'Instance Count',
            'Rate per Accelerator (USD)',
            'Accelerator Type',
            'Accelerator Count',
            'Total Accelerator Count',
            'Capacity Block ID',
            'Actual Instance Type',
            'Start Date (Beijing Time)',
            'End Date (Beijing Time)',
            'Duration (hours)',
            'Availability Zone',
            'Upfront Fee',
            'Currency Code',
            'Status'
        ]
        csv_writer.writerow(headers)
        
        # Write data rows (only results with offerings)
        for result in results:
            offerings = result.get('offerings', [])
            
            # Skip results with no offerings
            if not offerings:
                continue
            
            region = result.get('region', '')
            instance_type = result.get('instance_type', '')
            search_date = result.get('search_date', '')
            max_count = result.get('max_instance_count', 0)
            error = result.get('error')
            
            # Get instance info
            instance_info = instance_types_config.get(instance_type, {})
            rate_per_accelerator = instance_info.get('regions', {}).get(region, {}).get('ratePerAccelerator', '')
            accelerator_type = instance_info.get('acceleratorType', '')
            accelerator_count = instance_info.get('acceleratorCount', '')
            
            # Calculate total accelerator count
            try:
                total_accelerator_count = int(max_count) * int(accelerator_count) if accelerator_count else ''
            except (ValueError, TypeError):
                total_accelerator_count = ''
            
            # Write a row for each offering
            for offering in offerings:
                # Convert UTC to Beijing time (UTC+8)
                start_date_str = offering.get('StartDate', '')
                end_date_str = offering.get('EndDate', '')
                
                if start_date_str:
                    start_dt = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                    start_date_beijing = (start_dt + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    start_date_beijing = ''
                
                if end_date_str:
                    end_dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    end_date_beijing = (end_dt + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    end_date_beijing = ''
                
                row = [
                    region,
                    instance_type,
                    search_date,
                    max_count,
                    rate_per_accelerator,
                    accelerator_type,
                    accelerator_count,
                    total_accelerator_count,
                    offering.get('CapacityBlockOfferingId', ''),
                    offering.get('InstanceType', ''),
                    start_date_beijing,
                    end_date_beijing,
                    offering.get('CapacityBlockDurationHours', ''),
                    offering.get('AvailabilityZone', ''),
                    offering.get('UpfrontFee', ''),
                    offering.get('CurrencyCode', ''),
                    'Available'
                ]
                csv_writer.writerow(row)
        
        # Upload to S3
        csv_content = csv_buffer.getvalue()
        s3_key = f"results/{task_id}.csv"
        
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=csv_content.encode('utf-8'),
            ContentType='text/csv'
        )
        
        s3_url = f"s3://{bucket_name}/{s3_key}"
        logger.info(f"CSV uploaded to {s3_url}")
        
        # Update task metadata
        tasks_table.update_item(
            Key={'task_id': task_id},
            UpdateExpression='SET s3_url = :url',
            ExpressionAttributeValues={':url': s3_url}
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'task_id': task_id,
                's3_url': s3_url,
                'results_count': len(results)
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
