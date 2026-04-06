# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from cdk_nag import NagPackSuppression, NagSuppressions
from constructs import Construct


class MessageBufferingConstruct(Construct):
    """
    CDK construct that implements Step Functions-based message buffering.

    This construct creates a complete message buffering infrastructure including:
    - DynamoDB table for message buffer with TTL
    - Message Handler Lambda (triggered by SNS)
    - Mark Messages As Processing Lambda
    - Delete Processed Messages Lambda
    - Invoke AgentCore Lambda
    - Handle Failure Lambda
    - Step Functions state machine for orchestration
    - Dead letter queues for error handling
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agentcore_runtime_arn: str,
        environment_variables: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the MessageBufferingConstruct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            agentcore_runtime_arn: ARN of the AgentCore runtime to invoke
            environment_variables: Optional environment variables for Lambda functions
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Get stack name for resource naming
        stack_name = Stack.of(self).stack_name

        # Merge default environment variables with provided ones
        default_env_vars = {
            "AGENTCORE_RUNTIME_ARN": agentcore_runtime_arn,
            "LOG_LEVEL": "INFO",
            "POWERTOOLS_LOG_LEVEL": "INFO",
        }

        if environment_variables:
            default_env_vars.update(environment_variables)

        #######################
        ### DYNAMODB TABLE ####
        #######################

        # Create DynamoDB message buffer table
        self.message_buffer_table = dynamodb.Table(
            self,
            "MessageBufferTable",
            table_name=f"{stack_name}-message-buffer",
            partition_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,  # For development - change for production
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
        )

        # Add table name to environment variables
        env_with_table = {**default_env_vars, "MESSAGE_BUFFER_TABLE": self.message_buffer_table.table_name}

        #######################
        ### LAMBDA FUNCTIONS ##
        #######################

        # Get Lambda package path
        lambda_package_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "virtual-assistant",
            "virtual-assistant-messaging-lambda",
            "dist",
            "lambda",
            "message-buffering",
            "lambda.zip",
        )

        # Create dead letter queue for Lambda functions
        self.lambda_dlq = sqs.Queue(
            self,
            "LambdaDLQ",
            queue_name=f"{stack_name}-message-buffering-lambda-dlq",
            retention_period=Duration.days(14),
            enforce_ssl=True,
        )

        # 1. Message Handler Lambda (triggered by SNS)
        self.message_handler_lambda = _lambda.Function(
            self,
            "MessageHandlerLambda",
            function_name=f"{stack_name}-message-handler",
            description="Handle incoming messages from SNS and initiate Step Functions workflow",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="virtual_assistant_messaging_lambda.handlers.message_buffer_handler.lambda_handler",
            code=_lambda.Code.from_asset(lambda_package_path),
            memory_size=128,
            timeout=Duration.seconds(30),
            environment=env_with_table,
            dead_letter_queue_enabled=True,
            dead_letter_queue=self.lambda_dlq,
            retry_attempts=2,
        )

        # 2. Prepare Processing Lambda (marks messages as processing)
        # NOTE: Does NOT clear waiting_state - that's handled by ClearWaitingState state
        self.prepare_processing_lambda = _lambda.Function(
            self,
            "PrepareProcessingLambda",
            function_name=f"{stack_name}-prepare-processing",
            description="Atomically clear waiting state and mark messages as processing",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="virtual_assistant_messaging_lambda.handlers.prepare_processing.lambda_handler",
            code=_lambda.Code.from_asset(lambda_package_path),
            memory_size=128,
            timeout=Duration.seconds(30),
            environment=env_with_table,
        )

        # 3. Delete Processed Messages Lambda
        self.delete_processed_lambda = _lambda.Function(
            self,
            "DeleteProcessedLambda",
            function_name=f"{stack_name}-delete-processed-messages",
            description="Delete messages marked as processing after successful AgentCore invocation",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="virtual_assistant_messaging_lambda.handlers.delete_processed_messages.lambda_handler",
            code=_lambda.Code.from_asset(lambda_package_path),
            memory_size=128,
            timeout=Duration.seconds(30),
            environment=env_with_table,
        )

        # 4. Invoke AgentCore Lambda
        self.invoke_agentcore_lambda = _lambda.Function(
            self,
            "InvokeAgentCoreLambda",
            function_name=f"{stack_name}-invoke-agentcore",
            description="Invoke AgentCore Runtime with combined message content",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="virtual_assistant_messaging_lambda.handlers.invoke_agentcore.lambda_handler",
            code=_lambda.Code.from_asset(lambda_package_path),
            memory_size=128,
            timeout=Duration.seconds(60),
            environment=env_with_table,
        )

        # 5. Handle Failure Lambda
        self.handle_failure_lambda = _lambda.Function(
            self,
            "HandleFailureLambda",
            function_name=f"{stack_name}-handle-failure",
            description="Handle workflow failures and mark messages as failed",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="virtual_assistant_messaging_lambda.handlers.handle_failure.lambda_handler",
            code=_lambda.Code.from_asset(lambda_package_path),
            memory_size=128,
            timeout=Duration.seconds(30),
            environment=env_with_table,
        )

        # 6. Prepare Retry Lambda
        self.prepare_retry_lambda = _lambda.Function(
            self,
            "PrepareRetryLambda",
            function_name=f"{stack_name}-prepare-retry",
            description="Unmark messages and reset waiting state before retry",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="virtual_assistant_messaging_lambda.handlers.prepare_retry.lambda_handler",
            code=_lambda.Code.from_asset(lambda_package_path),
            memory_size=128,
            timeout=Duration.seconds(30),
            environment=env_with_table,
        )

        #######################
        ### IAM PERMISSIONS ###
        #######################

        # Grant DynamoDB permissions to all Lambda functions
        self.message_buffer_table.grant_read_write_data(self.message_handler_lambda)
        self.message_buffer_table.grant_read_write_data(self.prepare_processing_lambda)
        self.message_buffer_table.grant_read_write_data(self.delete_processed_lambda)
        self.message_buffer_table.grant_read_data(self.invoke_agentcore_lambda)
        self.message_buffer_table.grant_read_write_data(self.handle_failure_lambda)
        self.message_buffer_table.grant_read_write_data(self.prepare_retry_lambda)

        # Grant AgentCore Runtime invocation permissions to invoke_agentcore_lambda
        self.invoke_agentcore_lambda.add_to_role_policy(
            iam.PolicyStatement(
                sid="AgentCoreRuntimeInvoke",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                resources=[f"{agentcore_runtime_arn}*"],
            )
        )

        # Grant Step Functions callback permissions to invoke_agentcore_lambda
        # Required for async task to send success/failure callbacks
        self.invoke_agentcore_lambda.add_to_role_policy(
            iam.PolicyStatement(
                sid="StepFunctionsCallback",
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:SendTaskSuccess",
                    "states:SendTaskFailure",
                ],
                resources=["*"],  # Task tokens are opaque, cannot scope by ARN
            )
        )

        #######################
        ### STEP FUNCTIONS ####
        #######################

        # Create dead letter queue for Step Functions
        # Note: This is a DLQ itself, so it doesn't need its own DLQ
        self.workflow_dlq = sqs.Queue(
            self,
            "WorkflowDLQ",
            queue_name=f"{stack_name}-message-buffering-workflow-dlq",
            retention_period=Duration.days(14),
            enforce_ssl=True,
        )

        # Add CDK Nag suppression for WorkflowDLQ (it's a DLQ itself)
        NagSuppressions.add_resource_suppressions(
            self.workflow_dlq,
            [
                NagPackSuppression(
                    id="AwsSolutions-SQS3",
                    reason="This queue is a dead letter queue (DLQ) for Step Functions workflow failures. "
                    "DLQs themselves do not require additional DLQs as they are the final destination "
                    "for failed messages.",
                )
            ],
        )

        # Create CloudWatch log group for Step Functions
        self.state_machine_log_group = logs.LogGroup(
            self,
            "StateMachineLogGroup",
            log_group_name=f"/aws/vendedlogs/states/{stack_name}-message-batcher",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Build state machine definition using CDK constructs with JSONata
        state_machine_definition = self._build_state_machine_definition()

        # Create Step Functions state machine with CloudWatch logging
        self.state_machine = sfn.StateMachine(
            self,
            "BatcherStateMachine",
            state_machine_name=f"{stack_name}-message-batcher",
            definition_body=sfn.DefinitionBody.from_chainable(state_machine_definition),
            query_language=sfn.QueryLanguage.JSONATA,
            timeout=Duration.minutes(5),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=self.state_machine_log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=True,
            ),
        )

        # Grant Step Functions permissions to invoke Lambda functions
        self.prepare_processing_lambda.grant_invoke(self.state_machine)
        self.invoke_agentcore_lambda.grant_invoke(self.state_machine)
        self.delete_processed_lambda.grant_invoke(self.state_machine)
        self.handle_failure_lambda.grant_invoke(self.state_machine)
        self.prepare_retry_lambda.grant_invoke(self.state_machine)

        # Grant Step Functions permissions to access DynamoDB
        self.message_buffer_table.grant_read_write_data(self.state_machine)

        # Grant message handler Lambda permission to start Step Functions execution
        self.state_machine.grant_start_execution(self.message_handler_lambda)

        # Add state machine ARN to message handler environment
        self.message_handler_lambda.add_environment("BATCHER_STATE_MACHINE_ARN", self.state_machine.state_machine_arn)

        #######################
        ### CDK NAG SUPPRESSIONS
        #######################

        # Add CDK Nag suppressions for Lambda functions
        lambda_functions = [
            self.message_handler_lambda,
            self.prepare_processing_lambda,
            self.delete_processed_lambda,
            self.invoke_agentcore_lambda,
            self.handle_failure_lambda,
            self.prepare_retry_lambda,
        ]

        for lambda_func in lambda_functions:
            NagSuppressions.add_resource_suppressions(
                lambda_func,
                [
                    NagPackSuppression(
                        id="AwsSolutions-L1",
                        reason="Using Python 3.14 runtime which is the latest available version for Lambda",
                    ),
                    NagPackSuppression(
                        id="AwsSolutions-IAM4",
                        reason="AWS managed policy AWSLambdaBasicExecutionRole is required for Lambda execution "
                        "and follows AWS best practices for basic Lambda logging permissions",
                    ),
                    NagPackSuppression(
                        id="AwsSolutions-IAM5",
                        reason="Lambda function requires wildcard permissions for: 1) CloudWatch Logs access "
                        "for runtime logging, 2) DynamoDB operations on message buffer table, "
                        "3) AgentCore Runtime invocation for AI agent operations, "
                        "4) Step Functions task token callbacks (task tokens are opaque and cannot be scoped by ARN). "
                        "These permissions are scoped to appropriate service namespaces and required for "
                        "message buffering functionality.",
                        applies_to=[
                            "Action::bedrock-agentcore:*",
                            "Resource::arn:aws:logs:*:*:*",
                            "Resource::*",
                        ],
                    ),
                ],
                apply_to_children=True,
            )

        # Add CDK Nag suppressions for Step Functions
        # Use path-based suppression for the state machine role's default policy
        # because the Lambda ARN wildcards are dynamically generated
        NagSuppressions.add_resource_suppressions_by_path(
            Stack.of(self),
            f"/{Stack.of(self).stack_name}/MessageBuffering/BatcherStateMachine/Role/DefaultPolicy/Resource",
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="Step Functions state machine requires wildcard permissions for Lambda function "
                    "invocation. The :* suffix on Lambda ARNs is required by Step Functions to invoke "
                    "Lambda functions with version/alias support. This is a standard AWS pattern for "
                    "Step Functions Lambda integrations and cannot be avoided. The permissions are scoped "
                    "to specific Lambda function ARNs defined in this construct.",
                ),
            ],
        )

    def _build_state_machine_definition(self) -> sfn.IChainable:
        """
        Build the Step Functions state machine definition using CDK constructs with JSONata.

        This method creates the complete state machine workflow for message buffering:
        1. SetWaitingState - Mark user as having active workflow, set $user_id execution variable
        2. WaitForMessages - Wait 2 seconds for more messages
        3. GetMessages - Retrieve buffer from DynamoDB, set $session_id execution variable
        4. CheckMessageAge - Use JSONata to check age of non-processing messages
        5. DecideNextAction - Loop if messages still arriving
        6. PrepareProcessing - Atomically clear waiting state and mark messages as processing
        7. InvokeAgentCore - Invoke AgentCore (combines content internally)
        8. DeleteProcessedMessages - Delete processed messages on success
        9. PrepareRetry - Unmark messages and reset waiting state before retry
        10. CalculateRetryWait - Calculate exponential backoff wait time
        11. WaitBeforeRetry - Wait before retrying
        12. CheckRetryLimit - Check if retry limit reached
        13. HandleFailure - Handle errors and mark messages as failed

        Uses execution-scoped variables ($user_id, $session_id) to avoid passing static data
        through every state. Only retry_count is passed through outputs since it changes.

        Returns:
            The chainable state machine definition starting with SetWaitingState
        """
        # 1. SetWaitingState - Update DynamoDB to set waiting_state = true
        # Use DynamoUpdateItem.jsonata() to avoid result_path which is not supported in JSONata mode
        set_waiting_state = tasks.DynamoUpdateItem.jsonata(
            self,
            "SetWaitingState",
            table=self.message_buffer_table,
            key={"user_id": tasks.DynamoAttributeValue.from_string("{% $states.input.user_id %}")},
            update_expression="SET waiting_state = :true",
            expression_attribute_values={":true": tasks.DynamoAttributeValue.from_boolean(True)},
            # Set execution-scoped variable for user_id
            assign={
                "user_id": "{% $states.input.user_id %}",
            },
        )

        # 2. WaitForMessages - Wait 2 seconds for more messages
        wait_for_messages = sfn.Wait(
            self,
            "WaitForMessages",
            time=sfn.WaitTime.duration(Duration.seconds(2)),
        )

        # 3. GetMessages - Get item from DynamoDB (non-destructive)
        # Use DynamoGetItem.jsonata() to use outputs instead of result_path
        # Set session_id as execution-scoped variable from buffer (if item exists)
        get_messages = tasks.DynamoGetItem.jsonata(
            self,
            "GetMessages",
            table=self.message_buffer_table,
            key={"user_id": tasks.DynamoAttributeValue.from_string("{% $user_id %}")},  # Use execution variable
            # Set session_id as execution variable only if Item exists, store buffer data
            assign={
                "session_id": (
                    "{% $states.result.Item.session_id.S ~> $exists() ? "
                    "$states.result.Item.session_id.S : $session_id %}"
                ),
            },
            outputs={
                "buffer_data": "{% $states.result %}",
            },
        )

        # 3a. CheckIfMessagesExist - Check if any messages were retrieved
        check_if_messages_exist = sfn.Pass.jsonata(
            self,
            "CheckIfMessagesExist",
            comment="Check if any messages were retrieved",
            outputs={
                "has_messages": (
                    "{% $states.input.buffer_data.Item.messages.L ~> $exists() ? "
                    "$count($states.input.buffer_data.Item.messages.L) > 0 : false %}"
                ),
                "messages": (
                    "{% $states.input.buffer_data.Item.messages.L ~> $exists() ? "
                    "$states.input.buffer_data.Item.messages.L : [] %}"
                ),
            },
        )

        # 4. CheckMessageAge - Use JSONata to check age of latest non-processing message
        # Filter non-processing messages and calculate if we should wait more
        check_message_age = sfn.Pass.jsonata(
            self,
            "CheckMessageAge",
            comment="Use JSONata to check age of latest non-processing message",
            outputs={
                "messages": "{% $states.input.messages %}",
                "should_wait": "{% ("
                "$nonProcessing := $states.input.messages[M.processing.BOOL = false];"
                "$count($nonProcessing) > 0 and "
                "($toMillis($states.context.State.EnteredTime) - $max($nonProcessing.M.timestamp.S.$toMillis())) < 2000"
                ") %}",
            },
        )

        # 5. DecideNextAction - Choice state based on should_wait
        decide_next_action = sfn.Choice.jsonata(self, "DecideNextAction")

        # 6. PrepareProcessing - Atomically clear waiting state and mark messages as processing
        # CRITICAL: PrepareProcessing reads fresh from DynamoDB to avoid race conditions
        prepare_processing = tasks.LambdaInvoke.jsonata(
            self,
            "PrepareProcessing",
            lambda_function=self.prepare_processing_lambda,
            comment="Read fresh from DynamoDB, clear waiting state, mark non-processing messages as processing=true",
            payload=sfn.TaskInput.from_object(
                {
                    "user_id": "{% $user_id %}",
                    "session_id": "{% $session_id %}",
                }
            ),
            payload_response_only=True,
            outputs={
                "marked_messages": "{% $states.result %}",
            },
        )

        # 7. InvokeAgentCore - Invoke Lambda with task token pattern (WAIT_FOR_TASK_TOKEN)
        # Lambda will combine content and extract IDs from marked_messages internally
        # The workflow will pause until the async task sends a callback
        invoke_agentcore = tasks.LambdaInvoke.jsonata(
            self,
            "InvokeAgentCore",
            lambda_function=self.invoke_agentcore_lambda,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object(
                {
                    "user_id": "{% $user_id %}",
                    "session_id": "{% $session_id %}",
                    "marked_messages": "{% $states.input.marked_messages %}",
                    "task_token": "{% $states.context.Task.Token %}",
                }
            ),
            timeout=Duration.minutes(4),
            outputs={
                "invocation_result": "{% $states.result %}",
            },
        )

        # 8. DeleteProcessedMessages - Call Lambda to delete processed messages
        delete_processed_messages = tasks.LambdaInvoke.jsonata(
            self,
            "DeleteProcessedMessages",
            lambda_function=self.delete_processed_lambda,
            comment="Delete messages where processing=true after successful invocation",
            payload=sfn.TaskInput.from_object({"user_id": "{% $user_id %}"}),
            payload_response_only=True,
        )

        # 8a. ClearWaitingState - Clear waiting state when no messages remain
        clear_waiting_state = tasks.DynamoUpdateItem.jsonata(
            self,
            "ClearWaitingState",
            table=self.message_buffer_table,
            key={"user_id": tasks.DynamoAttributeValue.from_string("{% $user_id %}")},
            update_expression="SET waiting_state = :false",
            expression_attribute_values={":false": tasks.DynamoAttributeValue.from_boolean(False)},
            comment="Clear waiting state when no messages remain",
        )

        # 9. PrepareRetry - Unmark messages and reset waiting state before retry
        prepare_retry = tasks.LambdaInvoke.jsonata(
            self,
            "PrepareRetry",
            lambda_function=self.prepare_retry_lambda,
            comment="Unmark processing messages and set waiting state to true before retry",
            payload=sfn.TaskInput.from_object(
                {
                    "user_id": "{% $user_id %}",
                    "retry_count": "{% $states.input.retry_count %}",
                }
            ),
            payload_response_only=True,
            outputs={
                "retry_count": "{% $states.result.retry_count %}",
            },
        )

        # 10. WaitBeforeRetry - Wait based on retry count (2,4s,8s)
        wait_before_retry = sfn.Wait(
            self,
            "WaitBeforeRetry",
            time=sfn.WaitTime.seconds("{% $states.input.wait_seconds %}"),
        )

        # 11. CalculateRetryWait - Use JSONata to calculate wait time based on retry count
        calculate_retry_wait = sfn.Pass.jsonata(
            self,
            "CalculateRetryWait",
            comment="Calculate wait time: 2s * (2 ^ retry_count) using $power() function",
            outputs={
                "retry_count": "{% $states.input.retry_count %}",
                "wait_seconds": "{% 2 * $power(2, $states.input.retry_count) %}",
            },
        )

        # 12. CheckRetryLimit - Choice state to check if we should retry or fail
        check_retry_limit = sfn.Choice.jsonata(self, "CheckRetryLimit")

        # 13. HandleFailure - Handle errors and mark messages as failed
        # Note: In JSONata mode, error info is passed via the catch clause's outputs
        handle_failure = tasks.LambdaInvoke.jsonata(
            self,
            "HandleFailure",
            lambda_function=self.handle_failure_lambda,
            comment="Mark all processing messages as failed, leave in buffer for manual cleanup",
            payload=sfn.TaskInput.from_object(
                {
                    "user_id": "{% $user_id %}",
                    "error": "{% $states.input.error_info %}",
                }
            ),
            payload_response_only=True,
        )

        # Add catch for InvokeAgentCore to handle session busy errors
        # For session busy, prepare for retry; for other errors, fail immediately
        invoke_agentcore.add_catch(
            prepare_retry,
            errors=["AgentCoreSessionBusyError"],
            outputs={
                "retry_count": "{% $states.input.retry_count ~> $exists() ? $states.input.retry_count : 0 %}",
            },
        )

        # Catch all other errors and fail immediately
        invoke_agentcore.add_catch(
            handle_failure,
            errors=["States.ALL"],
            outputs={
                "error_info": "{% $states.errorOutput %}",
            },
        )

        # Chain the states together
        # Main flow: SetWaitingState -> WaitForMessages -> GetMessages -> CheckIfMessagesExist
        set_waiting_state.next(wait_for_messages)
        wait_for_messages.next(get_messages)
        get_messages.next(check_if_messages_exist)

        # CheckIfMessagesExist branches:
        # - If has_messages is false, go to ClearWaitingState and exit
        # - Otherwise, proceed to CheckMessageAge
        check_if_messages_exist_choice = sfn.Choice.jsonata(self, "CheckIfMessagesExistChoice")
        check_if_messages_exist.next(check_if_messages_exist_choice)

        check_if_messages_exist_choice.when(
            sfn.Condition.jsonata("{% $states.input.has_messages = false %}"),
            clear_waiting_state,
        )
        check_if_messages_exist_choice.otherwise(check_message_age)

        # Continue with CheckMessageAge -> DecideNextAction
        check_message_age.next(decide_next_action)

        # DecideNextAction branches:
        # - If should_wait is true, go back to WaitForMessages
        # - Otherwise, proceed to PrepareProcessing
        decide_next_action.when(
            sfn.Condition.jsonata("{% $states.input.should_wait %}"),
            wait_for_messages,
        )
        decide_next_action.otherwise(prepare_processing)

        # Continue main flow after PrepareProcessing
        prepare_processing.next(invoke_agentcore)
        invoke_agentcore.next(delete_processed_messages)

        # Loop-back: After deleting processed messages, go back to GetMessages
        delete_processed_messages.next(get_messages)

        # ClearWaitingState exits successfully
        clear_waiting_state.next(sfn.Succeed(self, "WorkflowComplete"))

        # Retry flow: PrepareRetry -> CheckRetryLimit
        prepare_retry.next(check_retry_limit)

        # CheckRetryLimit branches:
        # - If retry_count < 6, calculate wait time and retry from ClearWaitingState
        # - Otherwise, fail
        check_retry_limit.when(
            sfn.Condition.jsonata("{% $states.input.retry_count < 6 %}"),
            calculate_retry_wait,
        )
        check_retry_limit.otherwise(handle_failure)

        # Continue retry flow: CalculateRetryWait -> WaitBeforeRetry -> PrepareProcessing
        calculate_retry_wait.next(wait_before_retry)
        wait_before_retry.next(prepare_processing)

        return set_waiting_state

    def subscribe_to_sns_topic(self, topic: sns.ITopic, filter_policy: dict = None) -> None:
        """
        Subscribe the message handler Lambda to an SNS topic.

        Args:
            topic: The SNS topic to subscribe to
            filter_policy: Optional SNS filter policy for message filtering
        """
        if filter_policy:
            topic.add_subscription(
                sns_subscriptions.LambdaSubscription(
                    self.message_handler_lambda,
                    filter_policy=filter_policy,
                )
            )
        else:
            topic.add_subscription(sns_subscriptions.LambdaSubscription(self.message_handler_lambda))
