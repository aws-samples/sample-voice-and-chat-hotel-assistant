# Requirements Document

## Introduction

This spec focuses on refactoring the hotel assistant packages into a uv
workspace structure to consolidate the `hotel-assistant-livekit` and
`hotel-assistant-chat` packages under a single `packages/hotel-assistant/`
directory. This refactoring will improve code organization, simplify dependency
management, and enable better code sharing between the two related packages.

## Requirements

### Requirement 1

**User Story:** As a developer, I want the hotel assistant packages consolidated
into a uv workspace, so that I can manage dependencies more efficiently and
share common code between LiveKit and chat implementations.

#### Acceptance Criteria

1. WHEN I examine the packages directory THEN I SHALL see a new
   `packages/hotel-assistant/` workspace root directory
2. WHEN I look at the workspace structure THEN the system SHALL contain
   `hotel-assistant-livekit/`, `hotel-assistant-chat/`, and
   `hotel-assistant-common/` sub-packages
3. WHEN I run uv commands THEN the system SHALL manage dependencies through a
   workspace configuration at the root
4. WHEN I examine the project structure THEN each sub-package SHALL maintain its
   own pyproject.toml for specific dependencies

### Requirement 2

**User Story:** As a DevOps engineer, I want Docker builds to work from the
workspace root, so that I can build container images with the correct context
and dependencies.

#### Acceptance Criteria

1. WHEN I build Docker images THEN the Dockerfiles SHALL be located at the
   workspace root (`packages/hotel-assistant/`)
2. WHEN Docker builds execute THEN they SHALL have access to both sub-packages
   and shared dependencies
3. WHEN I examine the Dockerfiles THEN they SHALL use the correct COPY commands
   for the new directory structure
4. WHEN containers start THEN they SHALL execute the correct entry points for
   each service

### Requirement 3

**User Story:** As an infrastructure developer, I want CDK constructs to
reference the new workspace paths, so that deployments continue to work with the
refactored structure.

#### Acceptance Criteria

1. WHEN CDK constructs build Docker images THEN they SHALL reference the new
   `packages/hotel-assistant/` path
2. WHEN I examine infrastructure code THEN all hardcoded paths to
   `hotel-assistant-livekit` and `hotel-assistant-chat` SHALL be updated
3. WHEN deployments run THEN they SHALL successfully build and deploy containers
   from the new structure
4. WHEN I check CDK outputs THEN repository names and descriptions SHALL reflect
   the new workspace structure

### Requirement 4

**User Story:** As a developer, I want the workspace to maintain backward
compatibility, so that existing functionality continues to work without breaking
changes.

#### Acceptance Criteria

1. WHEN I run the LiveKit agent THEN it SHALL start and function identically to
   the current implementation
2. WHEN I run the chat agent THEN it SHALL start and function identically to the
   current implementation
3. WHEN I examine import statements THEN they SHALL be updated to reflect the
   new package structure
4. WHEN tests run THEN they SHALL pass without modification to test logic
