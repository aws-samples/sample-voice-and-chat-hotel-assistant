# Security

## Shared Responsibility Model

Security and Compliance is a shared responsibility between AWS and the customer.

This shared model can help relieve the customer’s operational burden as AWS
operates, manages and controls the components from the host operating system and
virtualization layer down to the physical security of the facilities in which
the service operates.

The customer assumes responsibility and management of the guest operating system
(including updates and security patches), other associated application software
as well as the configuration of the AWS provided security group firewall.
Customers should carefully consider the services they choose as their
responsibilities vary depending on the services used, the integration of those
services into their IT environment, and applicable laws and regulations. The
nature of this shared responsibility also provides the flexibility and customer
control that permits the deployment. As shown in the chart below, this
differentiation of responsibility is commonly referred to as Security “of” the
Cloud versus Security “in” the Cloud.

![Shared Responsibility Model](./images/shared_responsibility_model_v2.jpg)

For more details, please refer to
[AWS Shared Responsibility Model](https://aws.amazon.com/compliance/shared-responsibility-model/).

## Data Classification and Handling

This solution processes data that may include personally identifiable
information (PII) such as guest names, phone numbers, and conversation content.
You are responsible for classifying data according to your organization's
policies and applicable regulations. Consider defining classification levels
(e.g., Public, Internal, Confidential, Restricted) and mapping each data type
handled by the solution to the appropriate level.

Implement data retention policies appropriate for your use case. Conversation
history, user messages, and authentication tokens should have defined retention
periods. Use Amazon DynamoDB TTL, S3 lifecycle rules, and CloudWatch log retention
settings to enforce automatic data expiration.

For handling PII, consider enabling Amazon Bedrock Guardrails with PII detection
and redaction, and review the
[Amazon Bedrock Data Protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html)
documentation.

## Amazon Bedrock

There are three pillars when considering security of LLM applications:

- Security and Privacy of your data;
- Safety; and
- Responsibility.

Amazon Bedrock offers a host of features and controls around these three
pillars. For an in-depth description please consult the service page.

We do emphasize some general recommendations:

### DoS, Bruteforcing and Noisy-neighbor threats

We recommend you monitor the usage of the service to detect anomalies that might
correlate to attack attempts such as Denial-of-service, brute-force attacks or
even unintended noisy-neighbor events.

As a suggestion, consider some form of rate limiting to both avoid malicious
attacks and also to avoid over-consumption of the service.

### LLM Threats

LLM applications are subject to novel class of security threats, such as those
described in the
[OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/).

The security considerations below are not comprehensive and as you move to
production we recommend you dive deeper into both the security model of the
Amazon Bedrock platform (see details in
[Amazon Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html))
and security model for LLMs in general, such as those described by OWASP.

### Prompt injection

This manipulates a large language model (LLM) through crafty inputs, causing
unintended actions by the LLM. Direct injections overwrite system prompts, while
indirect ones manipulate inputs from external sources. Indirect prompt injection
is particularly relevant for agentic systems where tool responses, knowledge base
results, or other external data sources may contain malicious instructions that
influence LLM behavior.

For speed, this prototype does not implement prompt injection mitigations. For
deployments beyond demo, AWS recommends a defense-in-depth approach:

- **Amazon Bedrock Guardrails** with prompt attack filters enabled as an
  essential requirement. See
  [Detect prompt attacks with Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html).
- **Multi-layered input sanitization** at the application level before sending
  inputs to inference engines. See
  [Prompt injection security](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).
- **System prompt scoping** to clearly define what the agent can and cannot do.
- **Automated testing suites** for prompt validation, including adversarial
  inputs and cross-agent prompt propagation exploits.

For comprehensive guidance, see
[Security best practices for agentic AI systems on AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-security/best-practices.html)
and specifically
[Input validation and guardrails](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-security/best-practices-input-validation.html).

### Jailbreaking

Jailbreaking is the class of attacks that attempt to subvert safety filters
built into the LLMs themselves.

There is a subtle difference between Prompt Injection and Jailbreaking. See
details
[here](https://simonwillison.net/2024/Mar/5/prompt-injection-jailbreaking/).

### Sensitive information disclosure

LLMs may inadvertently reveal confidential data in its responses, leading to
unauthorized data access, privacy violations, and security breaches. It is
crucial to implement data sanitization and strict user policies to mitigate
this.

### Overreliance

Systems or people overly depending on LLMs without oversight may face
misinformation, miscommunication, legal issues, and security vulnerabilities due
to incorrect or inappropriate content generated by LLMs.

This risk is inherent to all LLM applications.

### Guardrails

Guardrails for Amazon Bedrock provides additional customizable safeguards on top
of the native protections of FMs, delivering safety protections that is among
the best in the industry by:

For speed, in this prototype, we did not use Guardrails for Amazon Bedrock. You should
evaluate if this is a necessary safeguard by weighing against your security
posture.

### Auditing

Consider enabling model invocation logging and set alerts to ensure adherence to
any responsible AI policies.

Model invocation logging is disabled by default. See
[Model Invocation Logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)
for details.

### Bias and Fairness

When adapting this solution to your use case, consider evaluating AI responses
for bias across different user demographics, languages, and interaction
patterns. Amazon Bedrock provides
[Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
that can help enforce content policies and reduce harmful outputs. For
multi-language deployments, test response quality and consistency across all
supported languages. Document your bias testing methodology and mitigation
strategies as part of your responsible AI practices.

## IAM Governance

AWS has a series of
[best practices and guidelines](https://docs.aws.amazon.com/IAM/latest/UserGuide/IAMBestPracticesAndUseCases.html)
around IAM.

### AWS Managed Policies

In this prototype, we used the default AWSAWS LambdaBasicExecutionRole AWS Managed
Policy to facilitate development. AWS Managed Policies don’t grant least
privileges in order to cover common use cases. The best practice it to write a
custom policy with only the permissions needed by the task. More information at:
Use
[AWS Defined Policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#bp-use-aws-defined-policies).

### Wildcard Policies

In this prototype, some policies use wildcards to specify resources to expedite
development. The best practice is to create policies that grant least
privileges. For more information refer to:
[Grant Least Privilege](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege)

## Monitoring

### Enable AWS Config

[AWS Config](https://aws.amazon.com/config/) is a service that maintains a
configuration history of your AWS resources and evaluates the configuration
against best practices and your internal policies. You can use this information
for operational troubleshooting, audit, and compliance use cases.

You should consider enabling AWS Config all regions in your account.

For more details on AWS Config best practices, please refer to the
[AWS Config best practices](https://aws.amazon.com/blogs/mt/aws-config-best-practices/)
blog post.

### Configure CloudTrail

You automatically have access to the CloudTrail Event history when you create
your AWS account. The Event history provides a viewable, searchable,
downloadable, and immutable record of the past 90 days of recorded management
events in an AWS Region.

We recommend that you create a trail or a CloudTrail Lake event data store for
your resources extending past 90 days:

- Enable DynamoDB data plane logging
- Enable API logging

### Enable CloudWatch alarms

In Amazon Cloudwatch, you can create your own metrics and alarms. While this
project does not implement any metrics, we recommend that you go over the
[list of recommended Cloudwatch alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
and set up the metrics that make sense for your own use case.

## Web Application Security

If the endpoint needs to be publicly visible on the internet, rather than
restricted to an intranet, we recommend exploring AWS WAF, AWS Shield, and AWS
Firewall Manager to increase the security posture of the solution.

For more details, refer to the
[AWS WAF Developer Guide](https://docs.aws.amazon.com/waf/latest/developerguide/what-is-aws-waf.html).

## Encryption Keys

This project uses AWS Managed keys to encrypt resources. While this reduces the
administrative burden of managing encryption keys, please consider using a
Customer Managed Key (CMK) if you are subject to corporate or regulatory
policies that require complete control in terms of creation, rotation, deletion
as well as the access control and usage policy of encryption keys.

For more information on how to create an manage your keys, refer to
[AWS Key Management Service concepts](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html).

## Credential Rotation

Audit and rotate credentials periodically to limit how long the credentials can
be used to access your resources. Long-term credentials create many risks, and
these risks can be reduced by rotating long-term credentials regularly.

This prototype stores secrets in AWS Secrets Manager but does not configure
automatic rotation. The following secrets should have rotation enabled for
deployments beyond demo:

- **MCP server credentials**: The Cognito client ID and secret used for
  machine-to-machine authentication between the virtual assistant agents and the
  MCP servers. These credentials grant access to the Hotel PMS tools and
  knowledge base. If compromised, they remain valid indefinitely until manually
  rotated.
- **LiveKit credentials**: The API key and secret used to connect to LiveKit
  Cloud for voice processing.

For guidance on configuring automatic rotation, see
[Rotate AWS Secrets Manager secrets](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html).

## S3

Amazon S3 provides a number of security features to consider as you develop and
implement your own security policies. The following best practices are general
guidelines and don’t represent a complete security solution. Because these best
practices might not be appropriate or sufficient for your environment, treat
them as helpful considerations rather than prescriptions.

For an in-depth description of best practices around S3, please refer to
[Security Best Practices for Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).
At a minimum, we recommend that you:

1. Ensure that your Amazon S3 buckets use the correct policies and are not
   publicly accessible;
2. Implement least privilege access;
3. Consider encryption at-rest (on disk);
4. Enforce encryption in-transit by restricting access using secure transport
   (TLS);
5. Enable object versioning when applicable; and
6. Enable cross-region replication as a disaster recovery strategy;
7. Consider if the data stored in the buckets warrants enabling MFA delete.

## Logs

Logging can become verbose in prod and too many logs can make analysis
difficult. Logging can also disclose data. For further AWS-recommended best
practices, see
[Logging best practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/logging-best-practices.html).

## Lambda

### Runtimes

This project uses AWS Lambda provided runtimes.

Lambda’s standard deprecation policy is to deprecate a runtime when any major
component of the runtime reaches the end of community long-term support (LTS)
and security updates are no longer available. Most usually, this is the language
runtime, though in some cases, a runtime can be deprecated because the operating
system (OS) reaches end of LTS.

After a runtime is deprecated, AWS may no longer apply security patches or
updates to that runtime, and functions using that runtime are no longer eligible
for technical support. Such deprecated runtimes are provided ‘as-is’, without
any warranties, and may contain bugs, errors, defects, or other vulnerabilities.

You should periodically review and update each AWS Lambda function runtime
making sure that it is in the
[list of supported runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html#runtimes-supported).

### Security scans

You should periodically run security and vulnerability scans for the code,
dependencies and images in your Lambda functions and Lambda layers.

You can use tools like
[AWS Inspector](https://docs.aws.amazon.com/inspector/latest/user/scanning_resources_lambda_code.html)
or choose your own scanning tool.

For scanning this prototype, we used
[ASH - The Automated Security Helper](https://github.com/awslabs/automated-security-helper).
The security helper tool was created to help you reduce the probability of a
security violation in a new code, infrastructure or IAM configuration by
providing a fast and easy tool to conduct preliminary security check as early as
possible within your development process.

## VPC

The following best practices are general guidelines and don’t represent a
complete security solution. Because these best practices might not be
appropriate or sufficient for your environment, treat them as helpful
considerations rather than prescriptions.

- **Multi AZ:** Use multiple Availability Zone deployments so you have high
  availability.
- **Securing:** Use security groups and network ACLs.
- **VPC Flow Logs:** Use Amazon CloudWatch to monitor your VPC components and
  VPN connections.
- **Data Safety:** When working with sensitive data it is recommended to access
  AWS service with VPC endpoint when available.
- **Resource Isolation:** When possible, isolate the resources within a VPC
  different from the default and configure internet access to restrict the
  network to only nown hosts and destinations.
- **Limit outbound access:** Generally speaking, if a has a path to the
  Internet, it should not have unrestricted access to all ports and all IP
  addresses. Either a NACL, egress rule, or other mechanism like a routing table
  should limit the Internet addresses and ports that an instance can reach.

For an in-depth description of best practices around VPC, please refer to
[Security Best Practices for Amazon VPC](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-best-practices.html).

## Third Party Services

LiveKit Cloud and WhatsApp for Business are third party services. Please review their pricing and
policies.

LiveKit is Open Source and can be
[self hosted](https://docs.livekit.io/home/self-hosting/kubernetes/).

## Compliance

When adapting this solution for regulated industries (e.g., healthcare, finance),
you are responsible for determining whether your use of AWS services meets
applicable regulatory requirements such as HIPAA, GDPR, or PCI DSS. Use
[HIPAA Eligible Services](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/)
and configure appropriate safeguards. Review the
[AWS Compliance Programs](https://aws.amazon.com/compliance/programs/) page to
understand which certifications and attestations are available for the services
used in this solution.

## RDS

This prototype uses the same Aurora Serverless cluster for the simulated PMS and
the vector store for the knowledge base. In production, consider using separate
resources.
