# Implementation Plan

- [x] 1. Create workspace root structure
  - Create `packages/hotel-assistant/` directory
  - Create workspace root `pyproject.toml` with uv workspace configuration
  - _Requirements: 1.1, 1.3_

- [x] 2. Move hotel-assistant-livekit package to workspace
  - Move `packages/hotel-assistant-livekit/` to
    `packages/hotel-assistant/hotel-assistant-livekit/`
  - Update package `pyproject.toml` to work within workspace
  - Add hotel-assistant-livekit to workspace members
  - _Requirements: 1.2, 2.3_

- [x] 3. Move hotel-assistant-chat package to workspace
  - Move `packages/hotel-assistant-chat/` to
    `packages/hotel-assistant/hotel-assistant-chat/`
  - Update package `pyproject.toml` to work within workspace
  - Add hotel-assistant-chat to workspace members
  - _Requirements: 1.2, 2.3_

- [x] 4. Create empty hotel-assistant-common package
  - Create `packages/hotel-assistant/hotel-assistant-common/` directory
    structure
  - Add basic `pyproject.toml` configuration for common package
  - Create empty `hotel_assistant_common/__init__.py` module
  - Add hotel-assistant-common to workspace members
  - _Requirements: 1.2_

- [x] 5. Create Dockerfile-livekit at workspace root
  - Create `packages/hotel-assistant/Dockerfile-livekit`
  - Configure multi-stage build copying only necessary files (uv.lock,
    pyproject.toml, README.md, hotel-assistant-common/, livekit pyproject.toml
    and README.md)
  - Set correct entry point for LiveKit agent
  - Test Docker build and verify container functionality
  - _Requirements: 2.1, 2.2, 2.4, 4.1_

- [x] 6. Create Dockerfile-chat at workspace root
  - Create `packages/hotel-assistant/Dockerfile-chat`
  - Configure multi-stage build copying only necessary files (uv.lock,
    pyproject.toml, README.md, hotel-assistant-common/, chat pyproject.toml and
    README.md)
  - Set correct entry point for chat agent
  - Test Docker build and verify container functionality
  - _Requirements: 2.1, 2.2, 2.4, 4.2_

- [x] 7. Update CDK backend stack Docker image paths
  - Update `packages/infra/stack/backend_stack.py` to reference new
    `packages/hotel-assistant/` path
  - Change Docker build context from individual packages to workspace root
  - Update Dockerfile reference to use `Dockerfile-chat`
  - _Requirements: 3.1, 3.2_

- [x] 8. Update CDK LiveKit ECS construct Docker paths
  - Update `packages/infra/stack/stack_constructs/livekit_ecs_construct.py` to
    reference new workspace path
  - Change Docker build context to workspace root
  - Update Dockerfile reference to use `Dockerfile-livekit`
  - _Requirements: 3.1, 3.2_

- [x] 9. Remove original Dockerfiles from sub-packages
  - Remove `packages/hotel-assistant/hotel-assistant-livekit/Dockerfile`
  - Remove `packages/hotel-assistant/hotel-assistant-chat/Dockerfile`
  - _Requirements: 2.3_

- [ ] 10. Test workspace dependency resolution
  - Run `uv sync` in workspace root to verify dependency resolution
  - Test that both sub-packages can be installed and imported correctly
  - Verify workspace lock file generation
  - _Requirements: 1.3, 4.4_

- [ ] 11. Test CDK deployment with new paths
  - Run CDK diff to verify infrastructure changes
  - Deploy to development environment to test Docker image builds
  - Verify that services start and function correctly
  - _Requirements: 3.3, 4.1, 4.2_
