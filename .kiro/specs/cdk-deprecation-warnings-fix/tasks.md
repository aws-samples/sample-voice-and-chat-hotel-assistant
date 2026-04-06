# Implementation Plan

- [x] 1. Fix Cognito User Pool deprecated advanced security mode
  - Update AgentCore Cognito construct to use modern threat protection
    configuration
  - Replace deprecated `advancedSecurityMode` with
    `standardThreatProtectionMode`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.1 Update AgentCore Cognito construct security configuration
  - Modify `packages/infra/stack/stack_constructs/agentcore_cognito.py`
  - Replace `advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED` with
    `standard_threat_protection_mode=cognito.StandardThreatProtectionMode.FULL_FUNCTION`
  - Ensure `feature_plan=cognito.FeaturePlan.PLUS` is maintained
  - _Requirements: 1.1, 1.2, 1.3_

- [ ]\* 1.2 Add unit tests for Cognito security configuration
  - Create tests to verify `StandardThreatProtectionMode.FULL_FUNCTION` is used
  - Validate that deprecated `AdvancedSecurityMode` is not present in
    configuration
  - Test that feature plan remains PLUS
  - _Requirements: 1.4, 1.5_

- [x] 2. Fix Lambda function deprecated log retention configuration
  - Update Database Setup construct to use explicit log group management
  - Replace deprecated `logRetention` parameter with explicit `logGroup`
    configuration
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2.1 Create explicit log group for custom resource provider
  - Modify `packages/infra/stack/stack_constructs/database_setup_construct.py`
  - Add explicit CloudWatch log group creation with ONE_WEEK retention
  - Set appropriate removal policy for log group lifecycle management
  - _Requirements: 2.2, 2.3, 2.4_

- [x] 2.2 Update custom resource provider configuration
  - Replace deprecated `log_retention=logs.RetentionDays.ONE_WEEK` parameter
  - Use `log_group=self.provider_log_group` parameter instead
  - Ensure provider references the explicitly created log group
  - _Requirements: 2.1, 2.2, 2.3_

- [ ]\* 2.3 Add unit tests for log group configuration
  - Create tests to verify explicit log group creation
  - Validate that log group is properly passed to custom resource provider
  - Test that retention period is preserved (ONE_WEEK)
  - _Requirements: 2.4, 2.5_

- [ ] 3. Validate CDK synthesis and deployment
  - Run CDK synthesis to verify deprecation warnings are eliminated
  - Test deployment to ensure functionality is preserved
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3.1 Run CDK synthesis validation
  - Execute `pnpm exec nx run infra:synth` command
  - Verify no deprecation warnings are generated in output
  - Confirm CloudFormation templates are generated successfully
  - _Requirements: 3.1, 3.2_

- [ ] 3.2 Validate CloudFormation template structure
  - Review generated CloudFormation templates for correct resource properties
  - Verify Cognito User Pool uses modern threat protection configuration
  - Confirm Lambda log groups are explicitly defined
  - _Requirements: 3.3, 3.4_

- [ ]\* 3.3 Test deployment in development environment
  - Deploy updated infrastructure to test environment
  - Verify Cognito authentication continues to function properly
  - Confirm Lambda logging works without issues
  - Validate no service interruption occurs during update
  - _Requirements: 3.5_

- [ ] 4. Code quality and documentation updates
  - Ensure code follows project standards and best practices
  - Update any related documentation or comments
  - _Requirements: 3.3, 3.4_

- [x] 4.1 Review and clean up code changes
  - Run `uv run ruff check --fix && uv run ruff format` on modified Python files
  - Ensure proper imports and code organization
  - Add appropriate comments explaining the modern configuration approach
  - _Requirements: 3.3_

- [ ]\* 4.2 Update documentation and comments
  - Update inline comments to reflect modern CDK patterns
  - Document the migration from deprecated to modern APIs
  - Add notes about CDK version compatibility
  - _Requirements: 3.4_
