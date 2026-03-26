from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_sns as sns,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_iam as iam,
    aws_ssm as ssm,
)
from constructs import Construct
import json

class CapacityBlockAsyncStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Load instance types configuration
        with open('../frontend/src/data/instanceTypes.json', 'r') as f:
            instance_types_config = json.load(f)
        
        # SSM Parameter for instance types configuration
        instance_types_parameter = ssm.StringParameter(
            self, "InstanceTypesConfig",
            parameter_name="/capacity-block-search/instance-types",
            string_value=json.dumps(instance_types_config),
            description="Instance types configuration with pricing and regions",
            tier=ssm.ParameterTier.STANDARD
        )

        # DynamoDB Table 1: Tasks Metadata
        tasks_table = dynamodb.Table(
            self, "CapacitySearchTasks",
            partition_key=dynamodb.Attribute(
                name="task_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            )
        )
        
        # GSI for listing all tasks
        tasks_table.add_global_secondary_index(
            index_name="CreatedAtIndex",
            partition_key=dynamodb.Attribute(
                name="partition_key",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # DynamoDB Table 2: Results
        results_table = dynamodb.Table(
            self, "CapacitySearchResults",
            partition_key=dynamodb.Attribute(
                name="task_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="result_key",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            )
        )

        # S3 Bucket for CSV results
        results_bucket = s3.Bucket(
            self, "ResultsBucket",
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
            versioned=True,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.GET],
                allowed_origins=["*"],
                allowed_headers=["*"],
                max_age=3000
            )]
        )

        # SNS Topic for notifications
        notification_topic = sns.Topic(
            self, "NotificationTopic",
            display_name="Capacity Block Search Notifications"
        )

        # Lambda: Query Capacity (二分查找)
        query_capacity_lambda = lambda_.Function(
            self, "QueryCapacityLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="query_capacity.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "RESULTS_TABLE_NAME": results_table.table_name,
                "TASKS_TABLE_NAME": tasks_table.table_name,
            }
        )
        
        results_table.grant_read_write_data(query_capacity_lambda)
        tasks_table.grant_read_write_data(query_capacity_lambda)
        query_capacity_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ec2:DescribeCapacityBlockOfferings"],
                resources=["*"]
            )
        )

        # Lambda: Aggregate Results
        aggregate_results_lambda = lambda_.Function(
            self, "AggregateResultsLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="aggregate_results.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment={
                "RESULTS_TABLE_NAME": results_table.table_name,
                "TASKS_TABLE_NAME": tasks_table.table_name,
                "RESULTS_BUCKET_NAME": results_bucket.bucket_name,
                "INSTANCE_TYPES_PARAMETER": instance_types_parameter.parameter_name,
            }
        )
        
        results_table.grant_read_data(aggregate_results_lambda)
        tasks_table.grant_read_write_data(aggregate_results_lambda)
        results_bucket.grant_put(aggregate_results_lambda)
        instance_types_parameter.grant_read(aggregate_results_lambda)

        # Lambda: Send Notification
        send_notification_lambda = lambda_.Function(
            self, "SendNotificationLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="send_notification.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "TASKS_TABLE_NAME": tasks_table.table_name,
                "SNS_TOPIC_ARN": notification_topic.topic_arn,
                "RESULTS_BUCKET_NAME": results_bucket.bucket_name,
            }
        )
        
        tasks_table.grant_read_write_data(send_notification_lambda)
        notification_topic.grant_publish(send_notification_lambda)
        results_bucket.grant_read(send_notification_lambda)

        # Lambda: Update Task Status
        update_status_lambda = lambda_.Function(
            self, "UpdateTaskStatusLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="update_task_status.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "TASKS_TABLE_NAME": tasks_table.table_name,
            }
        )
        
        tasks_table.grant_read_write_data(update_status_lambda)

        # Lambda: Handle Failure
        handle_failure_lambda = lambda_.Function(
            self, "HandleFailureLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="handle_failure.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "TASKS_TABLE_NAME": tasks_table.table_name,
                "SNS_TOPIC_ARN": notification_topic.topic_arn,
            }
        )
        
        tasks_table.grant_read_write_data(handle_failure_lambda)
        notification_topic.grant_publish(handle_failure_lambda)

        # Step Functions State Machine
        update_status_running = tasks.LambdaInvoke(
            self, "UpdateStatusRunning",
            lambda_function=update_status_lambda,
            payload=sfn.TaskInput.from_object({
                "task_id": sfn.JsonPath.string_at("$.task_id"),
                "status": "RUNNING"
            }),
            result_path="$.update_result"
        )

        query_capacity_task = tasks.LambdaInvoke(
            self, "QueryCapacityTask",
            lambda_function=query_capacity_lambda,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path=sfn.JsonPath.DISCARD
        )

        wait_10_seconds = sfn.Wait(
            self, "Wait15Seconds",
            time=sfn.WaitTime.duration(Duration.seconds(15))
        )

        # Sequential subtasks per region
        subtask_iterator = sfn.Map(
            self, "SubtaskIterator",
            max_concurrency=1,
            items_path=sfn.JsonPath.string_at("$.subtasks"),
            item_selector={
                "task_id": sfn.JsonPath.string_at("$.task_id"),
                "subtask": sfn.JsonPath.string_at("$$.Map.Item.Value")
            },
            result_path=sfn.JsonPath.DISCARD
        )
        subtask_iterator.item_processor(query_capacity_task.next(wait_10_seconds))

        # Parallel regions
        region_iterator = sfn.Map(
            self, "RegionIterator",
            max_concurrency=0,
            items_path=sfn.JsonPath.string_at("$.regions_with_subtasks"),
            item_selector={
                "task_id": sfn.JsonPath.string_at("$.task_id"),
                "region": sfn.JsonPath.string_at("$$.Map.Item.Value.region"),
                "subtasks": sfn.JsonPath.string_at("$$.Map.Item.Value.subtasks")
            },
            result_path=sfn.JsonPath.DISCARD
        )
        region_iterator.item_processor(subtask_iterator)

        handle_failure_task = tasks.LambdaInvoke(
            self, "HandleFailureTask",
            lambda_function=handle_failure_lambda,
            payload=sfn.TaskInput.from_object({
                "task_id": sfn.JsonPath.string_at("$.task_id"),
                "error": sfn.JsonPath.string_at("$.error")
            })
        )

        # Define workflow with error handling
        workflow = update_status_running \
            .next(region_iterator)
        
        # Add aggregate and notification tasks
        aggregate_task_with_input = tasks.LambdaInvoke(
            self, "AggregateTaskWithInput",
            lambda_function=aggregate_results_lambda,
            payload=sfn.TaskInput.from_object({
                "task_id": sfn.JsonPath.string_at("$$.Execution.Input.task_id")
            }),
            result_path=sfn.JsonPath.DISCARD
        )
        
        send_notification_task_with_input = tasks.LambdaInvoke(
            self, "SendNotificationTaskWithInput",
            lambda_function=send_notification_lambda,
            payload=sfn.TaskInput.from_object({
                "task_id": sfn.JsonPath.string_at("$$.Execution.Input.task_id")
            }),
            result_path=sfn.JsonPath.DISCARD
        )
        
        workflow = workflow.next(aggregate_task_with_input).next(send_notification_task_with_input)
        
        # Wrap in Parallel to add catch
        definition = sfn.Parallel(
            self, "WorkflowWithErrorHandling",
            result_path="$.workflow_result"
        )
        definition.branch(workflow)
        definition.add_catch(handle_failure_task, result_path="$.error")

        state_machine = sfn.StateMachine(
            self, "CapacitySearchWorkflow",
            definition=definition,
            timeout=Duration.hours(2)
        )

        # Lambda: Submit Task
        submit_task_lambda = lambda_.Function(
            self, "SubmitTaskLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="submit_task.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "TASKS_TABLE_NAME": tasks_table.table_name,
                "STATE_MACHINE_ARN": state_machine.state_machine_arn,
            }
        )
        
        tasks_table.grant_write_data(submit_task_lambda)
        state_machine.grant_start_execution(submit_task_lambda)

        # Lambda: List Tasks
        list_tasks_lambda = lambda_.Function(
            self, "ListTasksLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="list_tasks.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "TASKS_TABLE_NAME": tasks_table.table_name,
            }
        )
        
        tasks_table.grant_read_data(list_tasks_lambda)

        # Lambda: Get Task Results
        get_results_lambda = lambda_.Function(
            self, "GetTaskResultsLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="get_task_results.lambda_handler",
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "TASKS_TABLE_NAME": tasks_table.table_name,
                "RESULTS_BUCKET_NAME": results_bucket.bucket_name,
            }
        )
        
        tasks_table.grant_read_data(get_results_lambda)
        results_bucket.grant_read(get_results_lambda)

        # Lambda: Config (reuse from original)
        config_lambda = lambda_.Function(
            self, "ConfigLambda",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="index.lambda_handler",
            code=lambda_.Code.from_inline("""
import json
import boto3

ssm = boto3.client('ssm')

def lambda_handler(event, context):
    try:
        response = ssm.get_parameter(
            Name='/capacity-block-search/instance-types'
        )
        config = json.loads(response['Parameter']['Value'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps(config)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
"""),
            timeout=Duration.seconds(30)
        )
        
        instance_types_parameter.grant_read(config_lambda)

        # API Gateway
        api = apigw.RestApi(
            self, "CapacityBlockAsyncApi",
            rest_api_name="Capacity Block Search Async API",
            description="Async API for searching EC2 capacity block offerings",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Api-Key"]
            )
        )

        # API Key
        api_key = api.add_api_key(
            "CapacityBlockAsyncApiKey",
            api_key_name="capacity-block-search-async-key"
        )

        # Usage Plan
        usage_plan = api.add_usage_plan(
            "CapacityBlockAsyncUsagePlan",
            name="Standard Usage Plan",
            throttle=apigw.ThrottleSettings(
                rate_limit=100,
                burst_limit=200
            )
        )
        usage_plan.add_api_key(api_key)
        usage_plan.add_api_stage(stage=api.deployment_stage)

        # API Resources and Methods
        tasks_resource = api.root.add_resource("tasks")
        tasks_resource.add_method(
            "POST",
            apigw.LambdaIntegration(submit_task_lambda),
            api_key_required=True
        )
        tasks_resource.add_method(
            "GET",
            apigw.LambdaIntegration(list_tasks_lambda),
            api_key_required=True
        )

        task_resource = tasks_resource.add_resource("{task_id}")
        results_resource = task_resource.add_resource("results")
        results_resource.add_method(
            "GET",
            apigw.LambdaIntegration(get_results_lambda),
            api_key_required=True
        )

        config_resource = api.root.add_resource("config")
        config_resource.add_method(
            "GET",
            apigw.LambdaIntegration(config_lambda),
            api_key_required=True
        )

        # Outputs
        CfnOutput(self, "ApiEndpoint", value=api.url)
        CfnOutput(self, "ApiKeyId", value=api_key.key_id)
        CfnOutput(self, "TasksTableName", value=tasks_table.table_name)
        CfnOutput(self, "ResultsTableName", value=results_table.table_name)
        CfnOutput(self, "ResultsBucketName", value=results_bucket.bucket_name)
        CfnOutput(self, "SnsTopicArn", value=notification_topic.topic_arn)
        CfnOutput(self, "StateMachineArn", value=state_machine.state_machine_arn)
