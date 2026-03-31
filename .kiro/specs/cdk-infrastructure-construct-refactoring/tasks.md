# Implementation Plan

- [x] 1. Create MessageProcessingConstruct
  - Create new construct file
    `packages/infra/stack/stack_constructs/message_processing_construct.py`
  - Extract SQS queue, DLQ, and Lambda function creation logic from
    `backend_stack.py`
  - Implement simple property-based interface with `self.processing_queue`,
    `self.dead_letter_queue`, `self.lambda_function`
  - Add CDK Nag suppressions with specific `appliesTo` justifications for
    AwsSolutions-IAM5
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Update backend_stack.py to use MessageProcessingConstruct
  - Replace `_create_message_processing_infrastructure()` method with
    MessageProcessingConstruct instantiation
  - Update references to use construct properties instead of returned tuple
    values
  - Remove the private method after successful migration
  - Verify all CDK outputs are preserved
  - _Requirements: 5.1, 5.4_

- [x] 3. Create MessagingBackendConstruct
  - Create new construct file
    `packages/infra/stack/stack_constructs/messaging_backend_construct.py`
  - Move all messaging stack logic from `messaging_stack.py` into the construct
  - Expose resources as simple properties: `self.messaging_topic`,
    `self.machine_client_secret`, `self.api`, `self.user_pool`
  - Include all components: DynamoDB, SNS, Lambda, API Gateway, Cognito, WAF
  - _Requirements: 2.1, 2.2_

- [x] 4. Implement WhatsApp grant pattern
  - Create `grant_whatsapp_permissions()` function that accepts `iam.IGrantable`
  - Move logic from `_grant_whatsapp_permissions()` method in backend_stack.py
  - Return `iam.Grant` object following CDK patterns
  - Support optional cross-account role parameter
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 5. Update backend_stack.py messaging integration
  - Modify messaging integration logic to use new WhatsApp grant pattern
  - Replace `_grant_whatsapp_permissions()` calls with new function
  - Update conditional deployment logic to use MessagingBackendConstruct when
    EUM Social is not available
  - _Requirements: 2.4, 2.5, 5.2_

- [x] 6. Clean up backend_stack.py
  - Remove unused private methods:
    `_create_message_processing_infrastructure()`,
    `_configure_eum_social_integration()`,
    `_configure_simulated_messaging_integration()`,
    `_grant_whatsapp_permissions()`
  - Simplify `_create_messaging_integration()` method to use new constructs
  - Verify stack complexity is reduced and readability improved
  - _Requirements: 5.4_

- [x] 7. Simplify construct imports
  - Remove re-exports from `packages/infra/stack/stack_constructs/__init__.py`
  - Update all stack files to use direct imports like
    `from .stack_constructs.message_processing_construct import MessageProcessingConstruct`
  - Remove the `__all__` list maintenance complexity
  - _Requirements: 4.1, 4.2_

- [ ] 8. Test with CDK synthesis
  - Run `uv run cdk synth` to verify all constructs work correctly
  - Check that no CDK Nag violations are introduced
  - Verify all expected AWS resources are created
  - Confirm all stack outputs are preserved
  - _Requirements: 1.4, 2.3_
