# Design Document

## Overview

This design addresses CDK deprecation warnings by migrating from deprecated APIs
to their modern replacements. The solution focuses on two main areas: updating
Cognito User Pool security configuration and modernizing Lambda function log
retention management.

## Architecture

The fix involves updating two key infrastructure constructs:

1. **AgentCore Cognito Construct** - Replace deprecated `advancedSecurityMode`
   with modern threat protection
2. **Database Setup Construct** - Replace deprecated `logRetention` with
   explicit log group management

### Current State Analysis

#### Cognito Configuration Issues

- `agentcore_cognito.py` uses
  `advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED`
- This API is deprecated and will be removed in the next major CDK release
- The construct already uses `feature_plan=cognito.FeaturePlan.PLUS` which is
  required for modern threat protection

#### Lambda Log Retention Issues

- `database_setup_construct.py` uses `log_retention=logs.RetentionDays.ONE_WEEK`
  in the custom resource provider
- This parameter is deprecated in favor of explicit log group creation
- The current approach creates log groups implicitly through the deprecated
  parameter

## Components and Interfaces

### Component 1: AgentCore Cognito Security Migration

**File:** `packages/infra/stack/stack_constructs/agentcore_cognito.py`

**Current Implementation:**

```python
self.user_pool = cognito.UserPool(
    self,
    "UserPool",
    # ... other properties
    feature_plan=cognito.FeaturePlan.PLUS,
    advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,  # DEPRECATED
)
```

**Target Implementation:**

```python
self.user_pool = cognito.UserPool(
    self,
    "UserPool",
    # ... other properties
    feature_plan=cognito.FeaturePlan.PLUS,
    standard_threat_protection_mode=cognito.StandardThreatProtectionMode.FULL_FUNCTION,
)
```

**Interface Changes:**

- Remove `advanced_security_mode` parameter
- Add `standard_threat_protection_mode` parameter
- Maintain all existing public properties and methods
- No breaking changes to construct consumers

### Component 2: Database Setup Log Group Migration

**File:** `packages/infra/stack/stack_constructs/database_setup_construct.py`

**Current Implementation:**

```python
self.provider = custom_resources.Provider(
    self,
    "DatabaseSetupProvider",
    on_event_handler=self.function,
    log_retention=logs.RetentionDays.ONE_WEEK,  # DEPRECATED
)
```

**Target Implementation:**

```python
# Create explicit log group
self.provider_log_group = logs.LogGroup(
    self,
    "DatabaseSetupProviderLogGroup",
    retention=logs.RetentionDays.ONE_WEEK,
    removal_policy=RemovalPolicy.DESTROY,
)

self.provider = custom_resources.Provider(
    self,
    "DatabaseSetupProvider",
    on_event_handler=self.function,
    log_group=self.provider_log_group,
)
```

**Interface Changes:**

- Add explicit log group creation
- Replace `log_retention` with `log_group` parameter
- Maintain same retention period (ONE_WEEK)
- No breaking changes to construct consumers

## Data Models

### Cognito Security Configuration

**Before:**

```python
{
    "feature_plan": "PLUS",
    "advanced_security_mode": "ENFORCED"  # Deprecated
}
```

**After:**

```python
{
    "feature_plan": "PLUS",
    "standard_threat_protection_mode": "FULL_FUNCTION"  # Modern
}
```

### Lambda Log Configuration

**Before:**

```python
{
    "provider_config": {
        "log_retention": "ONE_WEEK"  # Deprecated
    }
}
```

**After:**

```python
{
    "log_group": {
        "retention": "ONE_WEEK",
        "removal_policy": "DESTROY"
    },
    "provider_config": {
        "log_group": "<log_group_reference>"  # Modern
    }
}
```

## Error Handling

### Migration Safety

1. **Backward Compatibility**
   - All public interfaces remain unchanged
   - No breaking changes for construct consumers
   - Existing deployments will update seamlessly

2. **Deployment Validation**
   - CDK synthesis will validate new configurations
   - CloudFormation will handle resource updates
   - No service interruption expected

3. **Rollback Strategy**
   - Changes are configuration-only, not structural
   - CloudFormation stack updates can be rolled back
   - Previous functionality is preserved

### Error Scenarios

1. **CDK Synthesis Errors**
   - Invalid threat protection mode configuration
   - Missing log group dependencies
   - **Mitigation:** Validate configurations during synthesis

2. **CloudFormation Update Errors**
   - Resource update conflicts
   - Permission issues
   - **Mitigation:** Use CloudFormation change sets for validation

3. **Runtime Functionality Issues**
   - Authentication behavior changes
   - Logging configuration problems
   - **Mitigation:** Maintain equivalent functionality through proper
     configuration mapping

## Testing Strategy

### Unit Testing

1. **Cognito Construct Tests**
   - Verify `StandardThreatProtectionMode.FULL_FUNCTION` is used
   - Confirm `AdvancedSecurityMode` is not present
   - Validate feature plan remains PLUS

2. **Database Setup Construct Tests**
   - Verify explicit log group creation
   - Confirm log group is passed to provider
   - Validate retention period is preserved

### Integration Testing

1. **CDK Synthesis Testing**
   - Run `cdk synth` and verify no deprecation warnings
   - Validate CloudFormation template structure
   - Confirm resource properties are correct

2. **Deployment Testing**
   - Deploy to test environment
   - Verify Cognito authentication works
   - Confirm Lambda logging functions properly

### Validation Criteria

1. **Warning Elimination**
   - No deprecation warnings during CDK synthesis
   - Clean build output without deprecated API usage

2. **Functional Equivalence**
   - Cognito security behavior unchanged
   - Lambda logging behavior unchanged
   - All existing functionality preserved

## Implementation Approach

### Phase 1: Cognito Security Migration

1. Update `agentcore_cognito.py` to use modern threat protection
2. Remove deprecated `advanced_security_mode` parameter
3. Add `standard_threat_protection_mode` parameter
4. Test synthesis and deployment

### Phase 2: Lambda Log Group Migration

1. Update `database_setup_construct.py` to create explicit log groups
2. Replace deprecated `log_retention` with `log_group` parameter
3. Ensure proper log group lifecycle management
4. Test synthesis and deployment

### Phase 3: Validation and Documentation

1. Run comprehensive CDK synthesis tests
2. Verify no deprecation warnings remain
3. Update any related documentation
4. Validate deployment in test environment

## Dependencies

### CDK Version Requirements

- Current CDK version supports both deprecated and modern APIs
- Migration prepares for future CDK major version upgrade
- No immediate CDK version upgrade required

### AWS Service Dependencies

- Cognito User Pool PLUS feature plan (already configured)
- CloudWatch Logs service (already in use)
- No new AWS service dependencies

### Construct Dependencies

- No changes to construct dependency graph
- All existing construct relationships preserved
- No new construct dependencies introduced

## Security Considerations

### Cognito Security Impact

- `StandardThreatProtectionMode.FULL_FUNCTION` provides equivalent security to
  deprecated advanced security mode
- PLUS feature plan maintains all security features
- No reduction in security posture

### Log Group Security

- Explicit log group creation maintains same access controls
- Log retention period preserved
- No changes to log data security or access patterns

## Performance Impact

### Resource Creation

- No additional AWS resources created
- Configuration changes only
- No performance impact on existing resources

### Runtime Performance

- No changes to Cognito authentication performance
- No changes to Lambda execution performance
- Log group management remains identical

## Monitoring and Observability

### CDK Synthesis Monitoring

- Monitor CDK synthesis output for warnings
- Track successful elimination of deprecation warnings
- Validate CloudFormation template generation

### Deployment Monitoring

- Monitor CloudFormation stack updates
- Track resource update success
- Validate functional behavior post-deployment

### Operational Monitoring

- Continue existing Cognito authentication monitoring
- Continue existing Lambda function monitoring
- No changes to operational observability
