# Current Package Structure and Dependencies

**Documentation Date:** 2025-10-03  
**Purpose:** Document the current state of the hotel-assistant workspace before
refactoring to virtual-assistant

---

## Table of Contents

1. [Workspace Overview](#workspace-overview)
2. [Package Structure](#package-structure)
3. [Python Packages](#python-packages)
4. [TypeScript/JavaScript Packages](#typescriptjavascript-packages)
5. [Infrastructure Configuration](#infrastructure-configuration)
6. [Docker Configurations](#docker-configurations)
7. [Dependency Graph](#dependency-graph)
8. [Build and Deployment](#build-and-deployment)

---

## Workspace Overview

### Root Configuration

- **Workspace Name:** `@hotel-assistant/workspace`
- **Description:** Hotel Assistant - Full Stack Application
- **Package Manager:** pnpm (v10.0.0+)
- **Build System:** NX Monorepo (v21.3.10)
- **Python Version:** 3.13
- **Node Version:** 18.0.0+

### Workspace Structure

```
hotel-assistant/
├── packages/
│   ├── hotel-assistant/          # Python workspace (uv)
│   │   ├── hotel-assistant-common/
│   │   ├── hotel-assistant-chat/
│   │   ├── hotel-assistant-livekit/
│   │   └── hotel-assistant-messaging-lambda/
│   ├── hotel-pms-simulation/         # Standalone Python package
│   ├── chatbot-messaging-backend/ # Standalone Python package
│   ├── infra/                    # CDK infrastructure (Python)
│   ├── demo/                     # React frontend
│   └── common/
│       └── constructs/           # CDK constructs (TypeScript)
├── hotel_data/                   # Hotel-specific data and knowledge base
├── documentation/                # Project documentation
└── scripts/                      # Utility scripts
```

---

## Package Structure

### 1. hotel-assistant (Python UV Workspace)

**Location:** `packages/hotel-assistant/`

#### Workspace Configuration

```toml
[tool.uv.workspace]
members = [
    "hotel-assistant-livekit",
    "hotel-assistant-chat",
    "hotel-assistant-common",
    "hotel-assistant-messaging-lambda"
]
```

#### Sub-packages

##### 1.1 hotel-assistant-common

- **Package Name:** `hotel-assistant-common`
- **Python Module:** `hotel_assistant_common`
- **Type:** Library
- **Description:** Shared utilities and components for hotel assistant packages

**Key Dependencies:**

- `httpx>=0.25.0` - HTTP client with authentication support
- `httpx-sse>=0.4.0` - Server-sent events support
- `mcp>=1.0.0` - MCP protocol support
- `anyio>=4.0.0` - Async utilities
- `boto3>=1.34.0` - AWS SDK
- `pydantic>=2.0.0` - Data validation
- `tenacity>=8.0.0` - Retry logic

**Key Components:**

- MCP client for hotel PMS integration (`hotel_pms_mcp_client`)
- Platform routers and integrations
- Shared models and exceptions
- AWS utilities (Cognito, Secrets Manager)

**NX Project Name:** `hotel-assistant-common` **Tags:**
`["python", "library", "common"]`

##### 1.2 hotel-assistant-chat

- **Package Name:** `hotel-assistant-chat`
- **Python Module:** `hotel_assistant_chat`
- **Type:** Application
- **Description:** Hotel assistant chat functionality using Strands AgentCore

**Key Dependencies:**

- `strands-agents` - Strands agent framework
- `bedrock-agentcore` - AWS Bedrock AgentCore
- `mcp` - MCP protocol
- `boto3>=1.37.31` - AWS SDK
- `httpx>=0.27.0` - HTTP client
- `fastapi` - Web framework
- `uvicorn[standard]` - ASGI server
- `pydantic` - Data validation
- `hotel-assistant-common` - Workspace dependency

**NX Project Name:** `hotel-assistant-chat` **Tags:**
`["python", "application", "chat", "agentcore"]`

**Docker Image:** `Dockerfile-chat`

##### 1.3 hotel-assistant-livekit

- **Package Name:** `hotel-assistant-livekit`
- **Python Module:** `hotel_assistant_livekit`
- **Type:** Application
- **Description:** LiveKit integration for Hotel Assistant with Amazon Nova
  Sonic

**Key Dependencies:**

- `livekit-agents[mcp]>=1.2.1` - LiveKit agents framework
- `livekit-plugins-aws>=1.2.1` - AWS plugins for LiveKit
- `aws_sdk_bedrock_runtime` - Bedrock runtime SDK
- `httpx>=0.25.0` - HTTP client
- `boto3>=1.34.0` - AWS SDK
- `hotel-assistant-common` - Workspace dependency

**NX Project Name:** `hotel-assistant-livekit` **Tags:**
`["python", "application", "livekit", "voice"]`

**Docker Image:** `Dockerfile-livekit`

##### 1.4 hotel-assistant-messaging-lambda

- **Package Name:** `hotel-assistant-messaging-lambda`
- **Python Module:** `hotel_assistant_messaging_lambda`
- **Type:** Library (Lambda function)
- **Description:** Lambda function for processing hotel assistant messages from
  SQS queue

**Key Dependencies:**

- `aws-lambda-powertools[parser,tracer]>=3.8.0` - Lambda utilities
- `aws-xray-sdk>=2.12.0` - X-Ray tracing
- `boto3>=1.37.31` - AWS SDK
- `httpx>=0.27.0` - HTTP client
- `pydantic>=2.0.0` - Data validation
- `hotel-assistant-common` - Workspace dependency

**NX Project Name:** `hotel-assistant-messaging-lambda` **Tags:**
`["python", "lambda", "messaging", "agentcore"]`

**Lambda Package:** Built with custom NX target that creates deployment zip

---

### 2. hotel-pms-simulation (Standalone Python Package)

**Location:** `packages/hotel-pms-simulation/`

- **Package Name:** `hotel-pms-simulation`
- **Python Module:** `hotel_pms_lambda`
- **Type:** Application (Lambda + MCP Server)
- **Description:** Hotel Property Management System Lambda API

**Key Dependencies:**

- `boto3>=1.35.0` - AWS SDK
- `aws-lambda-powertools[all]>=2.43.0` - Lambda utilities
- `pydantic>=2.5.0` - Data validation
- `python-json-logger>=2.0.7` - Structured logging
- `pg8000>=1.31.4` - PostgreSQL driver
- `scramp>=1.4.5` - SCRAM authentication

**Key Components:**

- Hotel PMS API endpoints
- MCP server implementation
- PostgreSQL database integration
- Seed data management
- CloudFormation custom resource for DB setup

**Note:** This package maintains hotel-specific naming as it's part of the
reference implementation.

---

### 3. chatbot-messaging-backend (Standalone Python Package)

**Location:** `packages/chatbot-messaging-backend/`

- **Package Name:** `chatbot-messaging-backend`
- **Python Module:** `chatbot_messaging_backend`
- **Type:** Application (Lambda)
- **Description:** Chatbot messaging backend that simulates messaging platform
  integrations

**Key Dependencies:**

- `aws-lambda-powertools[parser]>=3.8.0` - Lambda utilities
- `boto3>=1.37.31` - AWS SDK
- `pydantic>=2.0.0` - Data validation

**Key Components:**

- Message handling and routing
- SNS publishing
- DynamoDB repository
- Lambda handler

---

### 4. infra (CDK Infrastructure)

**Location:** `packages/infra/`

- **Package Name:** `backend-cdk`
- **Python Module:** `stack`
- **Type:** Application (CDK)
- **Description:** AWS CDK infrastructure for the backend application

**Key Dependencies:**

- `aws-cdk-lib==2.214.0` - CDK library
- `aws_cdk.aws_lambda_python_alpha==2.214.0a0` - Lambda Python support
- `constructs>=10.0.0,<11.0.0` - CDK constructs
- `cdk_nag>=2.35.81` - CDK security checks
- `hotel-assistant-constructs` - Custom constructs (local)
- `boto3>=1.40.2` - AWS SDK
- `cdklabs-generative-ai-cdk-constructs>=0.1.309` - GenAI constructs

**Key Stacks:**

- `backend_stack.py` - Main backend infrastructure
- `hotel_pms_stack.py` - Hotel PMS infrastructure
- `messaging_stack.py` - Messaging infrastructure

**Custom Constructs Used:**

- `HotelAssistantECR` - ECR repositories
- `HotelAssistantChatImage` - Chat container image
- `HotelAssistantMemory` - AgentCore memory
- `HotelAssistantRuntime` - AgentCore runtime

---

## TypeScript/JavaScript Packages

### 1. common/constructs (CDK Constructs)

**Location:** `packages/common/constructs/`

- **Package Name:** `@hotel-assistant/constructs`
- **Type:** Library (JSII)
- **Description:** Common CDK constructs for Hotel Assistant

**Key Exports:**

- `AgentCoreMemory` - Memory construct for AgentCore
- `AgentCoreRuntime` - Runtime construct for AgentCore
- `AgentCoreCognito` - Cognito construct for AgentCore
- `AgentCoreGateway` - API Gateway construct for AgentCore

**JSII Configuration:**

```json
{
  "targets": {
    "python": {
      "distName": "hotel-assistant-constructs",
      "module": "hotel_assistant_constructs"
    }
  }
}
```

**Build Output:**

- TypeScript: `lib/`
- Python: `dist/python/`

---

### 2. demo (React Frontend)

**Location:** `packages/demo/`

- **Package Name:** `@hotel-assistant/demo`
- **Type:** Application (React)
- **Description:** Hotel Assistant messaging application

**Key Dependencies:**

- `@cloudscape-design/components` - UI components
- `@tanstack/react-router` - Routing
- `@tanstack/react-query` - Data fetching
- `react-oidc-context` - Authentication

**Build Output:** `dist/` (deployed to S3/CloudFront)

---

## Infrastructure Configuration

### CDK Context Variables

Current naming conventions in CDK:

```python
# Construct names
HotelAssistantECR
HotelAssistantChatImage
HotelAssistantMemory
HotelAssistantRuntime
```

### Environment Variables

**Chat Application:**

- `HOTEL_ASSISTANT_CLIENT_ID`
- `HOTEL_PMS_MCP_SECRET_ARN`
- AWS region and credentials

**LiveKit Application:**

- `HOTEL_ASSISTANT_CLIENT_ID`
- `HOTEL_PMS_MCP_SECRET_ARN`
- LiveKit credentials

**Messaging Lambda:**

- `HOTEL_ASSISTANT_*` environment variables
- AgentCore configuration

### AWS Resource Names

Current patterns:

- ECR repositories: `hotel-assistant-chat`, `hotel-assistant-livekit`
- SSM parameters: `/hotel-assistant/whatsapp/allow-list`
- IAM resources: `hotel-assistant-*` prefix
- CloudFormation outputs: Reference "Hotel Assistant"

---

## Docker Configurations

### Dockerfile-chat

**Base Image:** `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`

**Build Context:** `packages/hotel-assistant/`

**Key Steps:**

1. Copy workspace root files (`pyproject.toml`, `uv.lock`)
2. Copy `hotel-assistant-common/` package
3. Copy `hotel-assistant-chat/` package configuration
4. Install dependencies with `uv sync --frozen --package hotel-assistant-chat`
5. Copy application code
6. Install project

**Entry Point:** `opentelemetry-instrument python -m hotel_assistant_chat.agent`

**Port:** 8080

### Dockerfile-livekit

**Base Image:** `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`

**Build Context:** `packages/hotel-assistant/`

**Key Steps:**

1. Copy workspace root files (`pyproject.toml`, `uv.lock`)
2. Copy `hotel-assistant-common/` package
3. Copy `hotel-assistant-livekit/` package configuration
4. Install dependencies with
   `uv sync --frozen --package hotel-assistant-livekit`
5. Copy application code
6. Install project

**Entry Point:** `python -m hotel_assistant_livekit.agent`

**Port:** 8081

---

## Dependency Graph

### Python Package Dependencies

```
hotel-assistant-chat
├── hotel-assistant-common (workspace)
├── strands-agents
├── bedrock-agentcore
├── mcp
└── boto3

hotel-assistant-livekit
├── hotel-assistant-common (workspace)
├── livekit-agents[mcp]
├── livekit-plugins-aws
├── aws_sdk_bedrock_runtime
└── boto3

hotel-assistant-messaging-lambda
├── hotel-assistant-common (workspace)
├── aws-lambda-powertools[parser,tracer]
├── aws-xray-sdk
└── boto3

hotel-assistant-common
├── httpx
├── httpx-sse
├── mcp
├── anyio
├── boto3
├── pydantic
└── tenacity
```

### Infrastructure Dependencies

```
infra (backend-cdk)
├── hotel-assistant-constructs (local)
├── aws-cdk-lib
├── constructs
├── cdk_nag
└── cdklabs-generative-ai-cdk-constructs

common/constructs
├── aws-cdk-lib (peer)
└── constructs (peer)
```

### Cross-Package References

1. **hotel-assistant-common** is referenced by:
   - hotel-assistant-chat
   - hotel-assistant-livekit
   - hotel-assistant-messaging-lambda

2. **hotel-assistant-constructs** is referenced by:
   - infra package

3. **hotel_pms_mcp_client** (in hotel-assistant-common) is used by:
   - hotel-assistant-chat
   - hotel-assistant-livekit

---

## Build and Deployment

### NX Build Targets

**Python Packages:**

- `test` - Run pytest
- `lint` - Run ruff check
- `format` - Run ruff format
- `build` - Build package with uv
- `install` - Install dependencies with uv sync

**TypeScript Packages:**

- `build` - Build with TypeScript compiler
- `test` - Run Jest tests
- `lint` - Run ESLint
- `format` - Run Prettier

**Infrastructure:**

- `deploy` - Deploy CDK stacks
- `diff` - Show CDK diff
- `destroy` - Destroy CDK stacks

### Deployment Commands

```bash
# Build all packages
pnpm exec nx run-many -t build

# Deploy infrastructure
pnpm exec nx deploy infra

# Build Docker images (via CDK)
# Images are built during CDK deployment
```

### Lambda Packaging

**hotel-assistant-messaging-lambda** has a custom `package` target:

1. Export dependencies to requirements.txt
2. Install dependencies to lambda_package/
3. Install project and hotel-assistant-common
4. Create lambda.zip

**Output:** `dist/lambda/message-processor/lambda.zip`

---

## Import Patterns

### Current Import Examples

**In hotel-assistant-chat:**

```python
from hotel_assistant_common import hotel_pms_mcp_client
from hotel_assistant_common.models.messaging import AgentCoreInvocationRequest
from hotel_assistant_common.platforms.router import platform_router
from hotel_assistant_chat.memory_hooks import MemoryHookProvider
```

**In hotel-assistant-livekit:**

```python
from virtual_assistant_common.hotel_pms_mcp_client import hotel_pms_mcp_client
from hotel_assistant_common.exceptions import MCPClientError
from hotel_assistant_livekit.agent import LiveKitAgent
```

**In hotel-assistant-messaging-lambda:**

```python
from hotel_assistant_common.platforms.router import platform_router
from hotel_assistant_common.models.messaging import AgentCoreInvocationRequest
from hotel_assistant_messaging_lambda.handlers.message_processor import process_message
```

---

## Key Files to Update

### Root Level

- `package.json` - Workspace name and description
- `pnpm-workspace.yaml` - Package references (if needed)

### Python Workspace

- `packages/hotel-assistant/pyproject.toml` - Workspace members
- All sub-package `pyproject.toml` files - Package names and dependencies
- All sub-package `project.json` files - NX configuration

### Infrastructure

- `packages/infra/stack/backend_stack.py` - Construct names and resource names
- `packages/infra/pyproject.toml` - Dependency on constructs package
- `packages/common/constructs/package.json` - Package name and JSII config

### Docker

- `packages/hotel-assistant/Dockerfile-chat` - COPY paths and module references
- `packages/hotel-assistant/Dockerfile-livekit` - COPY paths and module
  references

### Documentation

- `README.md` - Project description and examples
- `packages/infra/README.md` - Deployment instructions
- `documentation/architecture.md` - Architecture diagrams
- `documentation/troubleshooting.md` - Troubleshooting guides
- `documentation/whatsapp-integration.md` - Integration guides

---

## Notes for Refactoring

### Items to Preserve (Hotel-Specific)

1. **hotel-pms-simulation** package - Keep all naming as-is
2. **hotel_pms_mcp_client** references - Keep as-is
3. **hotel_data/** directory - Keep all content unchanged
4. Database schemas and seed data - Keep hotel-specific structure
5. Hotel-specific prompts and tools - Maintain current naming

### Items to Rename (Generic Virtual Assistant)

1. **Package names:** `hotel-assistant-*` → `virtual-assistant-*`
2. **Python modules:** `hotel_assistant_*` → `virtual_assistant_*`
3. **CDK constructs:** `HotelAssistant*` → `VirtualAssistant*`
4. **Environment variables:** `HOTEL_ASSISTANT_*` → `VIRTUAL_ASSISTANT_*`
5. **AWS resources:** `hotel-assistant-*` → `virtual-assistant-*`
6. **SSM parameters:** `/hotel-assistant/` → `/virtual-assistant/`
7. **Documentation:** Update to emphasize generic virtual assistant with hotel
   as reference

### Critical Dependencies

The refactoring must maintain:

- UV workspace structure and member relationships
- NX project dependencies and build order
- Docker multi-stage build patterns
- Lambda packaging process
- CDK construct dependencies
- JSII Python package generation

---

**End of Documentation**
