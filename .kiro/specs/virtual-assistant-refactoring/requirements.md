# Requirements Document

## Introduction

This feature refactors the Hotel Assistant application to become a more generic
Virtual Assistant platform. The goal is to make the application
industry-agnostic by renaming references from "hotel assistant" to "virtual
assistant" while preserving the hotel use case as a reference implementation.
This change will make it easier for developers to adapt the solution for other
industries by simply changing system prompts and available tools.

The refactoring maintains all existing functionality while improving the
application's positioning as a flexible virtual assistant platform that can be
customized for various industries including hospitality, retail, healthcare,
finance, and more.

## Requirements

### Requirement 1

**User Story:** As a developer, I want the application to emphasize its
adaptability to different industries while maintaining the hotel use case as the
primary example, so that I can easily understand how to customize it for my
specific industry.

#### Acceptance Criteria

1. WHEN I view the main README.md THEN it SHALL emphasize that this is a hotel
   assistant that can be easily adapted to other industries
2. WHEN I view the application description THEN it SHALL clearly explain that
   customization only requires changing system prompts and tools
3. WHEN I view the project documentation THEN it SHALL highlight the generic
   virtual assistant architecture with hotel as the reference implementation
4. WHEN I view the cost breakdown THEN it SHALL reference "Virtual Assistant"
   components to show the generic infrastructure costs

### Requirement 2

**User Story:** As a developer, I want the infrastructure code to use "virtual
assistant" naming conventions, so that the deployed resources reflect the
generic nature of the platform.

#### Acceptance Criteria

1. WHEN I deploy the infrastructure THEN ECR repository names SHALL use
   "virtual-assistant" instead of "hotel-assistant"
2. WHEN I view CloudFormation outputs THEN they SHALL reference "Virtual
   Assistant" instead of "Hotel Assistant"
3. WHEN I view CDK construct names THEN they SHALL use "VirtualAssistant"
   instead of "HotelAssistant"
4. WHEN I view environment variable names THEN they SHALL use
   "VIRTUAL_ASSISTANT" instead of "HOTEL_ASSISTANT"
5. WHEN I view IAM resource names THEN they SHALL use "virtual-assistant"
   instead of "hotel-assistant"
6. WHEN I view SSM parameter paths THEN they SHALL use "/virtual-assistant/"
   instead of "/hotel-assistant/"

### Requirement 3

**User Story:** As a developer, I want the package structure to reflect the
virtual assistant naming, so that the codebase is consistent with the new
positioning.

#### Acceptance Criteria

1. WHEN I view the packages directory THEN the main package SHALL be named
   "virtual-assistant" instead of "hotel-assistant"
2. WHEN I view sub-packages THEN they SHALL use "virtual-assistant" prefixes
   (e.g., "virtual-assistant-chat", "virtual-assistant-livekit")
3. WHEN I view Python package names THEN they SHALL use "virtual_assistant"
   instead of "hotel_assistant"
4. WHEN I view import statements THEN they SHALL reference "virtual_assistant"
   modules
5. WHEN I view Docker image names THEN they SHALL use "virtual-assistant"
   instead of "hotel-assistant"

### Requirement 4

**User Story:** As a developer, I want the configuration and deployment scripts
to use virtual assistant naming, so that all tooling is consistent with the new
branding.

#### Acceptance Criteria

1. WHEN I view CDK context variables THEN they SHALL use "virtualAssistant"
   instead of "hotelAssistant"
2. WHEN I view deployment commands THEN they SHALL reference virtual assistant
   components
3. WHEN I view environment configuration files THEN they SHALL use virtual
   assistant naming
4. WHEN I view build scripts THEN they SHALL reference virtual assistant
   packages
5. WHEN I view Docker files THEN they SHALL use virtual assistant naming
   conventions

### Requirement 5

**User Story:** As a developer, I want the documentation to clearly explain how
to customize the virtual assistant for different industries, so that I can
easily adapt it for my specific use case.

#### Acceptance Criteria

1. WHEN I read the README THEN it SHALL explain how the hotel use case serves as
   a reference implementation
2. WHEN I view the customization documentation THEN it SHALL emphasize that
   adaptation only requires providing new system prompts and tools that
   integrate with business processes
3. WHEN I view the deployment guide THEN it SHALL use virtual assistant
   terminology
4. WHEN I view the troubleshooting guide THEN it SHALL reference virtual
   assistant components
5. WHEN I view the WhatsApp integration guide THEN it SHALL use virtual
   assistant naming

### Requirement 6

**User Story:** As a developer, I want to preserve all hotel-specific
functionality and naming for the PMS integration, so that the reference
implementation remains complete and functional.

#### Acceptance Criteria

1. WHEN I view hotel PMS related code THEN it SHALL maintain "hotel_pms" naming
   conventions
2. WHEN I view MCP client references THEN they SHALL keep "hotel_pms_mcp_client"
   naming
3. WHEN I view hotel data and knowledge base content THEN it SHALL remain
   unchanged
4. WHEN I view hotel-specific prompts and tools THEN they SHALL maintain their
   current naming
5. WHEN I view database schemas and seed data THEN they SHALL preserve
   hotel-specific structure

### Requirement 7

**User Story:** As a developer, I want the refactoring to be implemented as a
clean break from the old naming, so that the new virtual assistant branding is
consistent throughout the codebase.

#### Acceptance Criteria

1. WHEN I deploy the refactored code THEN it SHALL use entirely new resource
   names with virtual assistant branding
2. WHEN I run the refactored tests THEN they SHALL use the new naming
   conventions throughout
3. WHEN I use the new deployment THEN I SHALL destroy existing stacks and deploy
   new ones with updated names
4. WHEN I access the refactored APIs THEN they SHALL use virtual assistant
   naming conventions
5. WHEN I view the refactored codebase THEN it SHALL have no references to the
   old hotel assistant naming (except for hotel PMS specific components)
