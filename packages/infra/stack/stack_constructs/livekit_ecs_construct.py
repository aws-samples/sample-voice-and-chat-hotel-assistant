# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_applicationautoscaling as appscaling,
)
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecr_assets as ecr_assets,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from cdk_nag import NagPackSuppression, NagSuppressions
from cdklabs.generative_ai_cdk_constructs.bedrock import BedrockFoundationModel
from constructs import Construct


class LiveKitECSConstruct(Construct):
    """
    A construct that deploys the LiveKit agent as an ECS Fargate service with autoscaling.

    This construct creates:
    - ECS cluster for LiveKit agents
    - Docker image asset with ARM64 platform targeting and ECR integration
    - Fargate service with ARM64 tasks
    - Application Auto Scaling configuration
    - Custom CloudWatch metrics integration
    - IAM roles with least-privilege permissions
    - Security groups and networking configuration
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        mcp_config_secret: secretsmanager.ISecret,
        mcp_config_parameter: str,
        livekit_secret_name: str = "virtual-assistant-livekit",
        **kwargs,
    ):
        """
        Initialize the LiveKit ECS construct.

        Args:
            scope: The scope in which this construct is defined
            construct_id: The unique identifier for this construct
            vpc: The VPC to deploy the ECS service in
            mcp_config_secret: The Secrets Manager secret containing MCP configuration
            mcp_config_parameter: SSM parameter name containing MCP configuration
            livekit_secret_name: The name of the LiveKit secret in Secrets Manager
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        self._vpc = vpc
        self._mcp_config_secret = mcp_config_secret
        self._mcp_config_parameter = mcp_config_parameter
        self._livekit_secret_name = livekit_secret_name

        # Create ECS cluster
        self._create_cluster()

        # Create Docker image asset
        self._create_docker_image()

        # Create IAM roles
        self._create_iam_roles()

        # Create task definition
        self._create_task_definition()

        # Create security group
        self._create_security_group()

        # Create ECS service
        self._create_service()

        # Create auto scaling configuration
        self._create_auto_scaling()

        # Add CDK Nag suppressions
        self._add_nag_suppressions()

    def _create_cluster(self) -> None:
        """Create the ECS cluster for LiveKit agents."""
        self._cluster = ecs.Cluster(
            self,
            "LiveKitCluster",
            vpc=self._vpc,
            container_insights=True,
            cluster_name=f"{Stack.of(self).stack_name}-livekit-cluster",
        )

    def _create_docker_image(self) -> None:
        """Create Docker image asset for the LiveKit agent."""
        import os

        # Get the path to the virtual-assistant workspace root
        workspace_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "virtual-assistant",
        )

        # Create Docker image asset with ARM64 platform targeting and proper ECR integration
        self._docker_image_asset = ecr_assets.DockerImageAsset(
            self,
            "LiveKitAgentImage",
            directory=workspace_path,
            file="Dockerfile-livekit",
            platform=ecr_assets.Platform.LINUX_ARM64,
            # Asset hash-based versioning for cache efficiency
            asset_name=f"virtual-assistant-livekit-{Stack.of(self).stack_name.lower()}",
            # Build arguments for optimization
            build_args={
                "BUILDKIT_INLINE_CACHE": "1",
            },
        )

        # Create container image from the asset
        self._container_image = ecs.ContainerImage.from_docker_image_asset(self._docker_image_asset)

    def _create_iam_roles(self) -> None:
        """Create IAM roles for ECS task execution and task runtime."""
        # Create execution role for ECS runtime permissions
        self._execution_role = iam.Role(
            self,
            "LiveKitExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ],
        )

        # Grant access to MCP secret for execution role (needed for container startup)
        self._mcp_config_secret.grant_read(self._execution_role)

        # Create task role for application runtime permissions
        self._task_role = iam.Role(
            self,
            "LiveKitTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Grant access to LiveKit secret for task role (needed at runtime)
        self._task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:{self._livekit_secret_name}*"
                ],
            )
        )

        # Grant access to MCP secret for task role (needed at runtime)
        self._mcp_config_secret.grant_read(self._task_role)

        # Grant access to both Nova Sonic 1 and Nova Sonic 2 models for gradual migration
        # Nova Sonic 1 (legacy) - kept for rollback capability
        nova_sonic_1_model = BedrockFoundationModel("amazon.nova-sonic-v1:0")
        nova_sonic_1_model.grant_invoke(self._task_role)

        # Nova Sonic 2 (current) - primary model for voice agent
        nova_sonic_2_model = BedrockFoundationModel("amazon.nova-2-sonic-v1:0")
        nova_sonic_2_model.grant_invoke(self._task_role)

        # Add CloudWatch permissions for custom metrics
        self._task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )

        # Add CloudWatch Logs permissions
        self._task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        # Add ECS task protection permissions
        self._task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:GetTaskProtection",
                    "ecs:UpdateTaskProtection",
                ],
                resources=[f"arn:aws:ecs:{Stack.of(self).region}:{Stack.of(self).account}:task/*"],
            )
        )

        # Add SSM parameter read permissions for MCP configuration
        self._task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter{self._mcp_config_parameter}"
                ],
            )
        )

    def _create_task_definition(self) -> None:
        """Create the Fargate task definition."""
        # Create log group
        self._log_group = logs.LogGroup(
            self,
            "LiveKitLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
            log_group_name=f"/ecs/livekit-agent-{Stack.of(self).stack_name}",
        )

        # Create task definition
        self._task_definition = ecs.FargateTaskDefinition(
            self,
            "LiveKitTaskDefinition",
            memory_limit_mib=4096,  # 4 GB
            cpu=2048,  # 2 vCPU
            task_role=self._task_role,
            execution_role=self._execution_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )

        # Prepare environment variables
        environment_vars = {
            # Bedrock configuration
            "BEDROCK_MODEL_ID": "amazon.nova-2-sonic-v1:0",
            "MODEL_TEMPERATURE": "0.0",
            # Nova Sonic 2 configuration
            # ENDPOINTING_SENSITIVITY controls turn-taking behavior:
            # - HIGH: ~300ms pause detection (fast but may interrupt)
            # - MEDIUM: ~500ms pause detection (balanced, recommended)
            # - LOW: ~800ms pause detection (patient, fewer interruptions)
            "ENDPOINTING_SENSITIVITY": "MEDIUM",
            # Logging configuration
            "LOG_LEVEL": "INFO",
            # MCP configuration - SSM parameter name for MCP configuration
            "MCP_CONFIG_PARAMETER": self._mcp_config_parameter,
            # MCP configuration - use secret name for application to retrieve (legacy, kept for compatibility)
            "HOTEL_PMS_MCP_SECRET_ARN": self._mcp_config_secret.secret_arn,
            # LiveKit configuration
            "LIVEKIT_SECRET_NAME": self._livekit_secret_name,
            # AWS configuration
            "AWS_REGION": Stack.of(self).region,
            # CloudWatch metrics configuration
            "CLOUDWATCH_NAMESPACE": "VirtualAssistant",
            "CLOUDWATCH_METRIC_NAME": "ActiveCalls",
            "ECS_SERVICE_NAME": "virtual-assistant-livekit",
            "METRICS_PUBLISH_INTERVAL": "60",
            # ECS task protection configuration
            "TASK_PROTECTION_DURATION_MINUTES": "120",  # 2 hours default
            # ECS metadata (will be populated by ECS at runtime)
            # The HOSTNAME environment variable is automatically set by ECS to the task ID
            # ECS_AGENT_URI is automatically injected by ECS for task protection API
        }

        # Add container to task definition
        self._container = self._task_definition.add_container(
            "LiveKitAgentContainer",
            image=self._container_image,
            logging=ecs.AwsLogDriver(
                log_group=self._log_group,
                stream_prefix="livekit-agent",
            ),
            environment=environment_vars,
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8081/ || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
            stop_timeout=Duration.minutes(2),
        )

    def _create_security_group(self) -> None:
        """Create security group for the ECS service."""
        self._security_group = ec2.SecurityGroup(
            self,
            "LiveKitSecurityGroup",
            vpc=self._vpc,
            allow_all_outbound=True,
            description="Security group for LiveKit ECS service",
        )

    def _create_service(self) -> None:
        """Create the Fargate service."""
        self._service = ecs.FargateService(
            self,
            "LiveKitService",
            cluster=self._cluster,
            task_definition=self._task_definition,
            security_groups=[self._security_group],
            desired_count=1,
            # min_healthy_percent=100,
            min_healthy_percent=0,
            max_healthy_percent=200,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            enable_execute_command=False,
            # circuit_breaker=ecs.DeploymentCircuitBreaker(
            #     enable=True,
            #     rollback=True,
            # ),
            circuit_breaker=ecs.DeploymentCircuitBreaker(
                enable=False,
                rollback=False,
            ),
        )

    def _create_auto_scaling(self) -> None:
        """Create Application Auto Scaling configuration."""
        # Create scalable target
        self._scaling_target = appscaling.ScalableTarget(
            self,
            "LiveKitScalingTarget",
            service_namespace=appscaling.ServiceNamespace.ECS,
            resource_id=f"service/{self._cluster.cluster_name}/{self._service.service_name}",
            scalable_dimension="ecs:service:DesiredCount",
            min_capacity=1,
            max_capacity=5,
        )

        # Create custom CloudWatch metric for active calls
        active_calls_metric = cloudwatch.Metric(
            namespace="VirtualAssistant",
            metric_name="ActiveCalls",
            dimensions_map={"ServiceName": "virtual-assistant-livekit"},
            statistic="Average",
        )

        # Create target tracking scaling policy
        self._scaling_policy = appscaling.TargetTrackingScalingPolicy(
            self,
            "LiveKitScalingPolicy",
            scaling_target=self._scaling_target,
            target_value=20.0,  # 20 active calls per task
            custom_metric=active_calls_metric,
            scale_in_cooldown=Duration.minutes(10),
            scale_out_cooldown=Duration.minutes(2),
        )

    def _add_nag_suppressions(self) -> None:
        """Add CDK Nag suppressions for security compliance."""
        # Suppress IAM role warnings
        NagSuppressions.add_resource_suppressions(
            self._task_role,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="LiveKit ECS task role requires wildcard permissions for: 1) Secrets Manager "
                    "access to LiveKit secret with dynamic suffix (arn:aws:secretsmanager:*:*:secret:"
                    "virtual-assistant-livekit*), 2) Bedrock model invocation with wildcard actions "
                    "(bedrock:InvokeModel*) for Nova Sonic model access, 3) CloudWatch metrics "
                    "publishing (*) for custom metrics, 4) CloudWatch Logs operations (*) for "
                    "application logging, 5) ECS task protection operations (arn:aws:ecs:*:*:task/*) "
                    "for task lifecycle management. SSM parameter access is scoped to specific "
                    "parameter ARN for MCP configuration. These permissions are required for LiveKit "
                    "agent runtime functionality and are scoped to appropriate service namespaces.",
                )
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_resource_suppressions(
            self._execution_role,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="LiveKit ECS execution role uses AWS managed policy "
                    "(AmazonECSTaskExecutionRolePolicy) which is required for ECS Fargate task "
                    "execution. This is the standard AWS-managed policy for ECS task execution.",
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="LiveKit ECS execution role requires wildcard permissions (*) for ECS task "
                    "execution operations including container image pulls from ECR, CloudWatch log "
                    "stream creation, and Secrets Manager access for container startup. These "
                    "permissions are managed by AWS ECS service and required for Fargate task execution.",
                ),
            ],
            apply_to_children=True,
        )

        # Suppress security group warnings
        NagSuppressions.add_resource_suppressions(
            self._security_group,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-EC23",
                    reason="LiveKit ECS security group allows all outbound traffic for LiveKit server "
                    "connections to external LiveKit cloud services, AWS API calls, and Nova Sonic "
                    "model access. Inbound traffic is not allowed. This is required for LiveKit agent "
                    "functionality in prototype environment. Production deployment should implement "
                    "more restrictive egress rules based on specific LiveKit server endpoints and "
                    "AWS service requirements.",
                )
            ],
        )

        # Suppress task definition warnings
        NagSuppressions.add_resource_suppressions(
            self._task_definition,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-ECS2",
                    reason="LiveKit ECS task definition uses environment variables for configuration "
                    "(Bedrock model ID, logging level, AWS region, secret names) which contain no "
                    "sensitive data. Sensitive values like API keys and credentials are retrieved "
                    "from AWS Secrets Manager at runtime. This is the recommended pattern for "
                    "containerized applications.",
                )
            ],
        )

        # Suppress Docker image asset warnings if any
        NagSuppressions.add_resource_suppressions(
            self._docker_image_asset,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-ECR1",
                    reason="Docker image asset automatically creates ECR repository with appropriate lifecycle "
                    "policies managed by CDK. The repository includes automatic cleanup of old images and "
                    "follows AWS best practices for container image management.",
                )
            ],
        )

    @property
    def cluster(self) -> ecs.ICluster:
        """Return the ECS cluster."""
        return self._cluster

    @property
    def service(self) -> ecs.IFargateService:
        """Return the Fargate service."""
        return self._service

    @property
    def task_role(self) -> iam.IRole:
        """Return the IAM task role."""
        return self._task_role

    @property
    def execution_role(self) -> iam.IRole:
        """Return the IAM execution role."""
        return self._execution_role

    @property
    def log_group(self) -> logs.ILogGroup:
        """Return the CloudWatch log group."""
        return self._log_group

    @property
    def scaling_target(self) -> appscaling.ScalableTarget:
        """Return the auto scaling target."""
        return self._scaling_target

    @property
    def scaling_policy(self) -> appscaling.TargetTrackingScalingPolicy:
        """Return the auto scaling policy."""
        return self._scaling_policy

    @property
    def docker_image_asset(self) -> ecr_assets.DockerImageAsset:
        """Return the Docker image asset."""
        return self._docker_image_asset

    @property
    def container_image(self) -> ecs.ContainerImage:
        """Return the container image."""
        return self._container_image
