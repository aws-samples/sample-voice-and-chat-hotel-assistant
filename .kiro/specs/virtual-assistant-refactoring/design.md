# Design Document

## Overview

This design document outlines the refactoring of the Hotel Assistant application
to become a more generic Virtual Assistant platform. The refactoring will rename
references from "hotel assistant" to "virtual assistant" throughout the
codebase, infrastructure, and documentation while preserving the hotel use case
as a reference implementation.

The design maintains all existing functionality while repositioning the
application as a flexible virtual assistant platform that can be customized for
various industries by simply changing system prompts and available tools.

## Architecture

### Current Architecture Analysis

The current application consists of several key components:

1. **Infrastructure Layer** (`packages/infra/`)
   - CDK stacks with hotel-assistant naming
   - ECR repositories, Lambda functions, and other AWS resources
   - Environment variables and configuration

2. **Virtual Assistant Packages** (`packages/hotel-assistant/`)
   - `hotel-assistant-chat/`: AgentCore chat implementation
   - `hotel-assistant-livekit/`: LiveKit voice agent
   - `hotel-assistant-common/`: Shared utilities and clients
   - `hotel-assistant-messaging-lambda/`: Message processing

3. **Frontend Application** (`packages/demo/`)
   - React-based web interface
   - Configuration and branding

4. **Hotel PMS Integration** (`packages/hotel-pms-lambda/`)
   - MCP server for hotel operations
   - Database and API layer

### Target Architecture

The refactored architecture will maintain the same structure but with updated
naming:

1. **Infrastructure Layer** (`packages/infra/`)
   - Renamed CDK constructs and resources
   - Updated environment variables and outputs
   - Virtual assistant branding throughout

2. **Virtual Assistant Packages** (`packages/virtual-assistant/`)
   - `virtual-assistant-chat/`: AgentCore chat implementation
   - `virtual-assistant-livekit/`: LiveKit voice agent
   - `virtual-assistant-common/`: Shared utilities and clients
   - `virtual-assistant-messaging-lambda/`: Message processing

3. **Frontend Application** (`packages/demo/`)
   - Updated configuration and references
   - Maintained hotel branding for demo purposes

4. **Hotel PMS Integration** (`packages/hotel-pms-lambda/`)
   - Unchanged - preserves hotel-specific functionality
   - Continues to serve as reference implementation

## Components and Interfaces

### 1. Package Structure Refactoring

#### Current Structure

```
packages/
├── hotel-assistant/
│   ├── hotel-assistant-chat/
│   ├── hotel-assistant-livekit/
│   ├── hotel-assistant-common/
│   └── hotel-assistant-messaging-lambda/
├── hotel-pms-lambda/
├── infra/
├── demo/
└── common/
    └── constructs/  # hotel_assistant_constructs
```

#### Target Structure

```
packages/
├── virtual-assistant/
│   ├── virtual-assistant-chat/
│   ├── virtual-assistant-livekit/
│   ├── virtual-assistant-common/
│   └── virtual-assistant-messaging-lambda/
├── hotel-pms-lambda/  # Unchanged
├── infra/
├── demo/
└── common/
    └── constructs/  # Renamed from hotel_assistant_constructs to virtual_assistant_constructs
```

### 2. Python Package Naming

#### Current Python Packages

- `hotel_assistant_chat`
- `hotel_assistant_livekit`
- `hotel_assistant_common`
- `hotel_assistant_messaging_lambda`

#### Target Python Packages

- `virtual_assistant_chat`
- `virtual_assistant_livekit`
- `virtual_assistant_common`
- `virtual_assistant_messaging_lambda`

### 3. Infrastructure Component Mapping

#### CDK Construct Names

| Current                   | Target                      |
| ------------------------- | --------------------------- |
| `HotelAssistantECR`       | `VirtualAssistantECR`       |
| `HotelAssistantChatImage` | `VirtualAssistantChatImage` |
| `HotelAssistantMemory`    | `VirtualAssistantMemory`    |
| `HotelAssistantRuntime`   | `VirtualAssistantRuntime`   |

#### Environment Variables

| Current             | Target                |
| ------------------- | --------------------- |
| `HOTEL_ASSISTANT_*` | `VIRTUAL_ASSISTANT_*` |
| `hotel-assistant-*` | `virtual-assistant-*` |

#### AWS Resource Names

| Current Pattern                        | Target Pattern                           |
| -------------------------------------- | ---------------------------------------- |
| `hotel-assistant-chat`                 | `virtual-assistant-chat`                 |
| `hotel-assistant-livekit`              | `virtual-assistant-livekit`              |
| `/hotel-assistant/whatsapp/allow-list` | `/virtual-assistant/whatsapp/allow-list` |

### 4. Import Statement Updates

#### Current Imports

```python
from hotel_assistant_common import hotel_pms_mcp_client
from hotel_assistant_common.models.messaging import AgentCoreInvocationRequest
from hotel_assistant_common.platforms.router import platform_router
from hotel_assistant_chat.memory_hooks import MemoryHookProvider
```

#### Target Imports

```python
from virtual_assistant_common import hotel_pms_mcp_client  # Note: hotel_pms stays
from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest
from virtual_assistant_common.platforms.router import platform_router
from virtual_assistant_chat.memory_hooks import MemoryHookProvider
```

### 5. NX Configuration and Package Updates

#### Root Package.json Updates

```json
// Current
{
  "name": "@hotel-assistant/workspace",
  "description": "Hotel Assistant - Full Stack Application"
}

// Target
{
  "name": "@virtual-assistant/workspace",
  "description": "Virtual Assistant - Full Stack Application"
}
```

#### NX Project Configuration Updates

Each package's `project.json` file will need updates:

```json
// Current project.json
{
  "name": "hotel-assistant-chat",
  "targets": {
    "build": {
      "executor": "@nx/python:build"
    }
  }
}

// Target project.json
{
  "name": "virtual-assistant-chat",
  "targets": {
    "build": {
      "executor": "@nx/python:build"
    }
  }
}
```

#### CDK Constructs Package Updates

The `packages/common/constructs/` package will be renamed:

```typescript
// Current: hotel_assistant_constructs
export { AgentCoreMemory } from './agentcore-memory';
export { AgentCoreRuntime } from './agentcore-runtime';

// Target: virtual_assistant_constructs
export { AgentCoreMemory } from './agentcore-memory';
export { AgentCoreRuntime } from './agentcore-runtime';
```

Package.json for constructs:

```json
// Current
{
  "name": "hotel_assistant_constructs"
}

// Target
{
  "name": "virtual_assistant_constructs"
}
```

### 6. Docker and Container Updates

#### Dockerfile References

- Update `Dockerfile-chat` and `Dockerfile-livekit` to reference new package
  paths
- Update container image names in ECR repositories
- Update build contexts and copy commands

#### Container Names

| Current                   | Target                      |
| ------------------------- | --------------------------- |
| `hotel-assistant-chat`    | `virtual-assistant-chat`    |
| `hotel-assistant-livekit` | `virtual-assistant-livekit` |

## Data Models

### Configuration Models

The refactoring will update configuration models to use virtual assistant naming
while maintaining compatibility with hotel PMS specific configurations.

#### Environment Configuration

```python
# Current
HOTEL_ASSISTANT_CLIENT_ID = "hotel-assistant-client"
HOTEL_PMS_MCP_SECRET_ARN = "arn:aws:secretsmanager:..."

# Target
VIRTUAL_ASSISTANT_CLIENT_ID = "virtual-assistant-client"
HOTEL_PMS_MCP_SECRET_ARN = "arn:aws:secretsmanager:..."  # Unchanged
```

#### CDK Context Variables

```json
// Current
{
  "hotelAssistantClientId": "hotel-assistant-client",
  "whatsappAllowListParameter": "/hotel-assistant/whatsapp/allow-list"
}

// Target
{
  "virtualAssistantClientId": "virtual-assistant-client",
  "whatsappAllowListParameter": "/virtual-assistant/whatsapp/allow-list"
}
```

### Message Models

Message models in `virtual_assistant_common.models.messaging` will maintain
their current structure but be imported from the new package location.

## Error Handling

### Migration Error Scenarios

1. **Import Errors**: Old import statements will fail after refactoring
   - Solution: Update all import statements systematically
   - Testing: Comprehensive import testing across all modules

2. **Environment Variable Mismatches**: Old environment variables will be
   undefined
   - Solution: Update all environment variable references
   - Testing: Environment variable validation in tests

3. **Resource Name Conflicts**: New AWS resources may conflict with existing
   ones
   - Solution: Use clean deployment approach (destroy old, deploy new)
   - Testing: Infrastructure deployment testing

4. **Docker Build Failures**: Container builds may fail due to path changes
   - Solution: Update all Dockerfile references and build contexts
   - Testing: Container build and deployment testing

### Error Recovery Strategies

1. **Git Rollback**: Use git to revert to previous commit if issues arise during
   refactoring
2. **Validation Scripts**: Create scripts to validate naming consistency
3. **Testing Coverage**: Comprehensive test coverage for all renamed components
4. **Documentation Updates**: Clear documentation of all changes made

## Testing Strategy

### Unit Testing Updates

1. **Test File Renaming**: Update test files to match new package structure
2. **Import Statement Updates**: Update all test imports to use new package
   names
3. **Mock Updates**: Update mocks to use new naming conventions
4. **Assertion Updates**: Update test assertions to expect new naming

### Integration Testing

1. **End-to-End Testing**: Verify complete workflows with new naming
2. **Infrastructure Testing**: Test CDK deployment with new resource names
3. **Container Testing**: Test Docker builds and deployments
4. **API Testing**: Verify API endpoints work with new naming

### Testing Phases

#### Phase 1: Package Structure Testing

- Verify package renaming and imports
- Test Python module loading
- Validate package dependencies

#### Phase 2: Infrastructure Testing

- Test CDK synthesis with new naming
- Verify AWS resource creation
- Test environment variable propagation

#### Phase 3: Application Testing

- Test chat functionality with new packages
- Test voice functionality with new packages
- Test messaging integration

#### Phase 4: Documentation Testing

- Verify documentation accuracy
- Test deployment instructions
- Validate troubleshooting guides

## Implementation Phases

### Phase 1: Package Structure Refactoring

1. Rename package directories
2. Update Python package names
3. Update import statements
4. Update pyproject.toml files

### Phase 2: Infrastructure Updates

1. Update CDK construct names
2. Update environment variables
3. Update AWS resource names
4. Update CloudFormation outputs

### Phase 3: Configuration Updates

1. Update Docker files
2. Update build scripts
3. Update deployment commands
4. Update environment files

### Phase 4: Documentation Updates

1. Update README files
2. Update architecture documentation
3. Update deployment guides
4. Update troubleshooting guides

### Phase 5: Testing and Validation

1. Run comprehensive test suite
2. Validate infrastructure deployment
3. Test end-to-end functionality
4. Verify documentation accuracy

## Deployment Strategy

### Clean Deployment Approach

The refactoring will use a clean deployment approach:

1. **Destroy Existing Stacks**: Remove all existing AWS resources
2. **Deploy New Stacks**: Deploy with new virtual assistant naming
3. **Validate Functionality**: Ensure all features work correctly
4. **Update Documentation**: Provide clear deployment instructions

### Deployment Steps

1. **Pre-deployment Cleanup**

   ```bash
   # Destroy existing stacks
   nx destroy infra
   ```

2. **Code Refactoring**
   - Apply all naming changes
   - Update configuration files
   - Update documentation

3. **New Deployment**

   ```bash
   # Deploy with new naming
   nx deploy infra
   ```

4. **Post-deployment Validation**
   - Test all functionality
   - Verify resource naming
   - Validate documentation

### Rollback Strategy

If issues arise during refactoring:

1. **File-level Rollback**: Use `git checkout HEAD~1 -- <specific-file>` to
   rollback individual files that are causing issues
2. **Selective Revert**: Revert specific changes while keeping working
   modifications
3. **Validation**: Test functionality after each rollback to identify
   problematic changes

## Security Considerations

### IAM Policy Updates

IAM policies will need updates to reflect new resource names:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ssm:GetParameter",
      "Resource": "arn:aws:ssm:*:*:parameter/virtual-assistant/whatsapp/*"
    }
  ]
}
```

### Secrets Management

Secrets will maintain their current structure but may need new names:

- LiveKit credentials: Keep existing secret name for compatibility
- MCP configuration: Keep existing secret name for hotel PMS integration
- New secrets: Use virtual-assistant naming convention

### Access Control

Access control patterns will remain the same but with updated resource names:

- ECR repository access
- Lambda execution roles
- AgentCore runtime permissions

## Performance Considerations

### Build Performance

The refactoring should not impact build performance:

- Package structure changes are cosmetic
- Import updates are compile-time changes
- No runtime performance impact expected

### Runtime Performance

Runtime performance will remain unchanged:

- Same application logic
- Same AWS services
- Same resource configurations

### Deployment Performance

Deployment will require full redeployment:

- Initial deployment will take full time (~15-20 minutes)
- Subsequent deployments will use normal incremental updates
- No performance degradation expected

## Monitoring and Observability

### CloudWatch Updates

CloudWatch resources will use new naming:

- Log groups: `/aws/lambda/virtual-assistant-*`
- Metrics: `VirtualAssistant/*`
- Alarms: `virtual-assistant-*`

### Tracing Updates

OpenTelemetry tracing will use updated service names:

- Service name: `virtual-assistant-chat`
- Operation names: Maintain current structure
- Trace attributes: Update to reflect new naming

### Metrics Updates

Custom metrics will use new naming conventions:

- Namespace: `VirtualAssistant`
- Metric names: Maintain current structure
- Dimensions: Update to reflect new resource names

This design provides a comprehensive approach to refactoring the Hotel Assistant
to a Virtual Assistant platform while maintaining all functionality and
providing clear guidance for customization to other industries.
