# Design Document

## Overview

This design outlines the refactoring of `hotel-assistant-livekit` and
`hotel-assistant-chat` packages into a unified uv workspace structure. The new
structure will consolidate related packages under `packages/hotel-assistant/`
while maintaining clear separation of concerns and enabling shared code through
a common package.

## Architecture

### Current Structure

```
packages/
├── hotel-assistant-livekit/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── hotel_assistant_livekit/
└── hotel-assistant-chat/
    ├── pyproject.toml
    ├── Dockerfile
    └── hotel_assistant_chat/
```

### Target Structure

```
packages/
└── hotel-assistant/
    ├── pyproject.toml (workspace root)
    ├── uv.lock
    ├── Dockerfile-livekit
    ├── Dockerfile-chat
    ├── hotel-assistant-livekit/
    │   ├── pyproject.toml
    │   └── hotel_assistant_livekit/
    ├── hotel-assistant-chat/
    │   ├── pyproject.toml
    │   └── hotel_assistant_chat/
    └── hotel-assistant-common/
        ├── pyproject.toml
        └── hotel_assistant_common/
```

## Components and Interfaces

### Workspace Root Configuration

**File:** `packages/hotel-assistant/pyproject.toml`

- Defines the uv workspace with member packages
- Contains shared development dependencies
- Manages workspace-level configuration

**Key Configuration:**

```toml
[tool.uv.workspace]
members = [
    "hotel-assistant-livekit",
    "hotel-assistant-chat",
    "hotel-assistant-common"
]

[tool.uv.sources]
hotel-assistant-common = { workspace = true }
```

### Sub-package Structure

Each sub-package maintains its own `pyproject.toml` with:

- Package-specific dependencies
- Entry points and scripts
- Build configuration
- References to shared common package

### Docker Integration

**Dockerfile-livekit:**

- Multi-stage build from workspace root
- Copies only necessary files: root uv.lock, pyproject.toml, README.md, all of
  hotel-assistant-common/, and livekit-specific pyproject.toml and README.md
- Installs only livekit-specific dependencies in final stage
- Sets correct entry point for LiveKit agent

**Dockerfile-chat:**

- Multi-stage build from workspace root
- Copies only necessary files: root uv.lock, pyproject.toml, README.md, all of
  hotel-assistant-common/, and chat-specific pyproject.toml and README.md
- Installs only chat-specific dependencies in final stage
- Sets correct entry point for chat agent

### Shared Common Package

**Purpose:** Empty uv project for future shared code consolidation

**Structure:**

```
hotel-assistant-common/
├── pyproject.toml
└── hotel_assistant_common/
    └── __init__.py
```

## Error Handling

### Migration Error Scenarios

1. **Import Path Conflicts**
   - **Issue:** Existing imports may break during migration
   - **Solution:** Maintain backward compatibility through **init**.py
     re-exports
   - **Fallback:** Gradual migration with deprecation warnings

2. **Dependency Resolution Conflicts**
   - **Issue:** Version conflicts between sub-packages
   - **Solution:** Use uv's dependency resolver with workspace constraints
   - **Fallback:** Pin conflicting dependencies at workspace level

3. **Docker Build Context Issues**
   - **Issue:** Dockerfiles may not find required files
   - **Solution:** Use multi-stage builds with explicit COPY commands
   - **Fallback:** Temporary build scripts to prepare context

4. **Workspace Root Build Errors** ⚠️ **Critical**
   - **Issue:** `hatchling.build` fails when workspace root has `[project]`
     section but no source code
   - **Error:**
     `ValueError: Unable to determine which files to ship inside the wheel`
   - **Solution:** Remove `[project]` and `[build-system]` sections from
     workspace root
   - **Prevention:** Workspace root should only contain workspace configuration,
     not package definition

5. **Premature Workspace Dependencies** ⚠️ **Critical**
   - **Issue:** Adding workspace dependencies before target package exists
     causes sync failures
   - **Error:**
     `references a workspace in tool.uv.sources but is not a workspace member`
   - **Solution:** Only add workspace dependencies after all referenced packages
     are created
   - **Prevention:** Follow strict task order - create packages before adding
     cross-references

### Infrastructure Update Risks

1. **CDK Path Resolution**
   - **Issue:** Hardcoded paths in infrastructure code
   - **Solution:** Update all path references systematically
   - **Validation:** Test deployments in development environment

2. **Container Registry Naming**
   - **Issue:** Existing ECR repositories expect specific names
   - **Solution:** Update repository names and maintain backward compatibility
   - **Migration:** Gradual transition with both old and new names

## Workspace Configuration Best Practices

### Workspace Root Configuration

**Key Learning:** The workspace root should NOT be configured as a buildable
package to avoid hatchling build errors.

**Correct Configuration:**

```toml
[tool.uv.workspace]
members = [
    "hotel-assistant-livekit",
    "hotel-assistant-chat",
    "hotel-assistant-common"
]

[tool.uv.sources]
hotel-assistant-common = { workspace = true }

# Workspace root - no package definition needed
# No [project] section
# No [build-system] section

[dependency-groups]
dev = [
    # Shared development tools only
]
```

### Package Migration Cleanup

**Critical Steps:**

1. Remove old `.venv` directories from moved packages
2. Remove individual `uv.lock` files (workspace manages at root)
3. Avoid adding workspace dependencies until the target package exists
4. Test workspace sync after each package move

## Testing Strategy

### Unit Testing

- Each sub-package maintains its own test suite
- Shared test utilities in common package
- Test workspace dependency resolution
- **New:** Remove hanging tests during migration to avoid blocking CI/CD

### Integration Testing

- Docker build tests for both services
- CDK deployment tests with new paths
- End-to-end functionality validation
- **New:** Workspace sync validation after each package move

### Migration Testing

- Verify import compatibility
- Test dependency resolution
- Validate container startup and functionality
- **New:** Test package-specific pytest execution within workspace

## Implementation Phases

### Phase 1: Workspace Setup

1. Create workspace root structure
2. Configure uv workspace in pyproject.toml
3. Move existing packages to sub-directories
4. Update import paths and dependencies

### Phase 2: Docker Integration

1. Create Dockerfiles at workspace root
2. Update build contexts and COPY commands
3. Test container builds and functionality
4. Validate entry points and startup

### Phase 3: Infrastructure Updates

1. Update CDK construct path references
2. Modify ECR repository configurations
3. Update deployment scripts and documentation
4. Test full deployment pipeline

### Phase 4: Common Package Creation

1. Create empty hotel-assistant-common package structure
2. Add basic pyproject.toml configuration
3. Include package in workspace members
