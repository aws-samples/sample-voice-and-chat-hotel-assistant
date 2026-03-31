# Implementation Plan

- [x] 1. Move all directories at once (big bang approach)
  - Move `packages/hotel-assistant/` to `packages/virtual-assistant/`
  - Rename all sub-directories: `hotel-assistant-*` to `virtual-assistant-*`
  - Rename all Python modules: `hotel_assistant_*` to `virtual_assistant_*`
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 2. Update all package configuration files
- [x] 2.1 Update pyproject.toml files for all Python packages
  - Change package names from `hotel-assistant-*` to `virtual-assistant-*`
  - Change Python package names from `hotel_assistant_*` to
    `virtual_assistant_*`
  - Update package descriptions to use "Virtual Assistant" terminology
  - _Requirements: 3.3_

- [x] 2.2 Update NX project.json files for all packages
  - Update project names to use `virtual-assistant-*` prefix
  - Update build paths and output directories
  - Update target configurations and dependencies
  - _Requirements: 4.2_

- [x] 2.3 Update CDK constructs package
  - Update `packages/common/constructs/package.json` name from
    `hotel_assistant_constructs` to `virtual_assistant_constructs`
  - Update TypeScript exports and imports in constructs package
  - _Requirements: 3.2_

- [x] 3. Update all Python import statements across the codebase
- [x] 3.1 Replace hotel_assistant imports with virtual_assistant imports
  - Replace `from hotel_assistant_common` with `from virtual_assistant_common`
  - Replace `from hotel_assistant_chat` with `from virtual_assistant_chat`
  - Replace `from hotel_assistant_livekit` with `from virtual_assistant_livekit`
  - Replace `from hotel_assistant_messaging_lambda` with
    `from virtual_assistant_messaging_lambda`
  - Preserve `hotel_pms_mcp_client` imports unchanged
  - _Requirements: 3.4, 6.2_

- [x] 3.2 Update test imports across all packages
  - Update all test files to import from `virtual_assistant_*` modules
  - Update mock configurations to use new naming
  - Update test assertions and expectations
  - _Requirements: 3.4, 7.2_

- [x] 4. Update infrastructure and CDK code
- [x] 4.1 Update backend_stack.py CDK construct names and imports
  - Update import from `hotel_assistant_constructs` to
    `virtual_assistant_constructs`
  - Rename `HotelAssistantECR` to `VirtualAssistantECR`
  - Rename `HotelAssistantChatImage` to `VirtualAssistantChatImage`
  - Rename `HotelAssistantMemory` to `VirtualAssistantMemory`
  - Rename `HotelAssistantRuntime` to `VirtualAssistantRuntime`
  - _Requirements: 2.3, 3.4_

- [x] 4.2 Update AWS resource names and descriptions
  - Change ECR repository names from `hotel-assistant-chat` to
    `virtual-assistant-chat`
  - Update CloudFormation output descriptions to reference "Virtual Assistant"
  - Update IAM resource names to use `virtual-assistant` prefix
  - Update SSM parameter paths from `/hotel-assistant/` to `/virtual-assistant/`
  - _Requirements: 2.1, 2.2, 2.5, 2.6_

- [x] 4.3 Update environment variable names and Lambda handler paths
  - Replace `HOTEL_ASSISTANT_*` with `VIRTUAL_ASSISTANT_*` in environment
    configurations
  - Update CDK context variable references from `hotelAssistant*` to
    `virtualAssistant*`
  - Update Lambda handler paths to reference new package names (e.g.,
    `virtual_assistant_messaging_lambda.handlers.message_processor.lambda_handler`)
  - _Requirements: 2.4_

- [x] 4.4 Update Docker configurations
  - Update `Dockerfile-chat` to reference new package paths
  - Update `Dockerfile-livekit` to reference new package paths
  - Update COPY commands to use new directory structure
  - Update container image names from `hotel-assistant-*` to
    `virtual-assistant-*`
  - _Requirements: 4.5, 3.5_

- [x] 5. Update root configuration and workspace files
- [x] 5.1 Update root package.json
  - Change workspace name from `@hotel-assistant/workspace` to
    `@virtual-assistant/workspace`
  - Update description from "Hotel Assistant - Full Stack Application" to
    "Virtual Assistant - Full Stack Application"
  - _Requirements: 1.1, 1.2_

- [x] 5.2 Update pnpm workspace configuration
  - Verify `pnpm-workspace.yaml` references work with new package structure
  - Test workspace dependency resolution with `pnpm install`
  - _Requirements: 4.4_

- [ ] 6. Update documentation
- [x] 6.1 Update main README.md
  - Emphasize that this is a hotel assistant easily adaptable to other
    industries
  - Clearly explain that customization only requires changing system prompts and
    tools
  - Update cost breakdown to reference "Virtual Assistant" components
  - Update project structure diagram with new package names
  - Add section explaining how to adapt for different industries
  - _Requirements: 1.1, 1.2, 1.4, 5.2_

- [x] 6.2 Update architecture documentation
  - Update `documentation/architecture.md` to highlight generic virtual
    assistant capabilities
  - Emphasize hotel use case as reference implementation
  - _Requirements: 1.3_

- [x] 6.3 Update deployment and troubleshooting guides
  - Update `packages/infra/README.md` to use virtual assistant terminology
  - Update `documentation/troubleshooting.md` to reference virtual assistant
    components
  - Update deployment commands and examples
  - _Requirements: 5.3, 5.4_

- [x] 6.4 Update WhatsApp integration documentation
  - Update `documentation/whatsapp-integration.md` to use virtual assistant
    naming
  - Update SSM parameter paths and examples
  - _Requirements: 5.5_

- [ ] 7. Test and validate the refactored application
- [x] 7.1 Run comprehensive test suite
  - Execute `pnpm install` to update dependencies
  - Run `nx run-many -t build` to build all packages
  - Run `nx run-many -t test` to test all packages
  - Fix any remaining import or naming issues
  - _Requirements: 7.2_

- [x] 7.2 Test infrastructure deployment
  - The previous infrastructure has already been destroyed
  - Deploy with new naming: `nx deploy infra`
  - Verify all AWS resources are created correctly with new names
  - Test environment variable propagation
  - _Requirements: 7.1, 7.3_

- [x] 7.3 Test end-to-end functionality
  - Test chat functionality with new packages
  - Test voice functionality with new packages
  - Test messaging integration with new naming
  - Verify hotel PMS integration still works (should be unchanged)
  - _Requirements: 7.4, 6.1_

- [x] 7.4 Validate documentation accuracy
  - Verify all documentation reflects new naming
  - Test deployment instructions with new commands
  - Validate troubleshooting guides work correctly
  - _Requirements: 5.1, 5.3, 5.4, 5.5_
