# Industry Adaptation Guide

This guide explains how to adapt the Virtual Assistant Platform from the hotel reference implementation to your specific industry and business needs.

## Overview

The platform is industry-agnostic by design. The hotel implementation demonstrates capabilities, but the same architecture works for retail, healthcare, finance, real estate, or any industry requiring conversational AI with backend integration.

**The key insight:** You don't rebuild your systems. The platform connects to your existing APIs and data.

### What You Customize

1. **System Prompts** - Define agent behavior and conversation style
2. **Knowledge Base** - Provide business information for the agent to reference
3. **API Integration** - Connect your existing REST APIs as callable tools

### What Stays the Same

- Core infrastructure (LiveKit, Nova Sonic, AgentCore)
- Multi-modal interfaces (voice, chat, messaging)
- AWS deployment architecture
- Authentication and security patterns

## Understanding the Architecture

The platform uses two separate MCP (Model Context Protocol) servers that work together:

### Assistant MCP Server

**Purpose:** Provides system prompts and knowledge base access

**Responsibilities:**
- Serves customized system prompts for chat and voice
- Queries Amazon Bedrock knowledge base for business information
- Injects dynamic context (current date, available entities)

**Deployment:** Amazon Bedrock AgentCore Runtime (managed container hosting service)

**You customize:** Prompt content and knowledge base documents

**What is Amazon Bedrock AgentCore Runtime?** A secure, serverless hosting environment that runs your MCP server in isolated containers. You provide a Docker container with your MCP server code, and AgentCore Runtime handles deployment, scaling, and session isolation.

### Business API MCP Server

**Purpose:** Exposes your existing REST APIs as tools

**Responsibilities:**
- Wraps your existing APIs using Amazon Bedrock AgentCore Gateway
- Translates MCP tool calls into HTTP requests
- Handles authentication between agent and your APIs

**Deployment:** AgentCore Gateway (fully-managed AWS service)

**You provide:** OpenAPI specification describing your existing API

**Critical point:** You use your **existing APIs** without modification. AgentCore Gateway automatically converts any REST API into MCP tools using an OpenAPI specification.

## Step 1: Customize System Prompts

System prompts control the agent's personality, behavior, and how it interacts with users. They're text files that define the agent's instructions.

### Location

```
packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/
├── chat_prompt.txt    # Text-based chat interactions
└── voice_prompt.txt   # Speech-to-speech voice interactions
```

### What to Change

**Industry Context**

Replace hotel terminology with your industry:

```
Hotel: "You are a hotel assistant helping guests with reservations..."
Retail: "You are a retail assistant helping customers with products..."
Healthcare: "You are a healthcare assistant helping patients with appointments..."
Finance: "You are a financial assistant helping customers with accounts..."
```

**Capabilities**

Define what the agent can do:

```
Hotel: Room reservations, housekeeping, concierge services
Retail: Product search, inventory checks, order placement
Healthcare: Appointment scheduling, prescription refills, provider search
Finance: Account inquiries, transfers, fraud reporting
```

**Conversation Style**

Adjust tone and formality:

```
Retail: Friendly, enthusiastic, sales-oriented
Healthcare: Professional, empathetic, privacy-conscious
Finance: Professional, security-focused, precise
Real Estate: Consultative, informative, relationship-building
```

**Tool Usage Guidelines**

Explain when and how to use each tool:

```
When a customer asks about product availability:
1. Call checkInventory tool with product_id
2. If available, provide quantity and location
3. If unavailable, provide restock_date
4. Offer similar products if out of stock
```

**Business Rules**

Define data collection and validation:

```
Before creating an order:
- Collect: customer name, email, shipping address
- Validate: email format, address completeness
- Confirm: all details before submitting
- Never use placeholder data
```

### Dynamic Context Injection

Prompts use placeholders that are filled at runtime:

```
Current date: {current_date}

Available locations:
{location_list}
```

Modify the context generation function:

```python
# In mcp/server.py
def generate_business_context() -> dict[str, str]:
    """Generate dynamic context for your business"""
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Get your business entities
    locations = your_service.get_locations()
    location_list = "\n".join([
        f"- {loc.name} (ID: {loc.id})"
        for loc in locations
    ])
    
    return {
        "current_date": current_date,
        "location_list": location_list,
    }
```

### Industry-Specific Prompt Considerations

**Retail/E-commerce:**
- Product recommendation strategies
- Inventory checking before orders
- Upselling and cross-selling guidelines
- Return/exchange procedures

**Healthcare:**
- HIPAA-compliant language
- Medical terminology usage
- When to escalate to medical staff
- Privacy and consent protocols
- Emergency handling procedures

**Finance:**
- Security verification procedures
- Fraud detection protocols
- Regulatory compliance language
- Financial advice disclaimers
- Transaction confirmation requirements

**Real Estate:**
- Property description strategies
- Showing scheduling protocols
- Offer negotiation guidelines
- Legal disclaimers
- When to involve human agents

## Step 2: Replace Knowledge Base Content

The knowledge base provides detailed business information that the agent references during conversations. It's stored as markdown files and indexed by Amazon Bedrock.

### Current Structure

```
hotel_data/hotel-knowledge-base/
├── hotel-1/
│   ├── general-info.md
│   ├── services.md
│   ├── policies.md
│   └── operations.md
├── hotel-2/
└── hotel-3/
```

### Your Structure

Organize by your business entities:

```
knowledge-base/
├── location-1/              # Store, office, facility
│   ├── general-info.md
│   ├── services.md
│   ├── policies.md
│   └── hours-contact.md
├── location-2/
└── product-category/        # Or service category
    ├── overview.md
    ├── specifications.md
    └── pricing.md
```

### Content Guidelines

**Format:** Markdown with clear headings

**Style:** FAQ format works best for retrieval

```markdown
# Product Returns

## How do I return a product?

You can return any product within 30 days of purchase. Items must be unused
and in original packaging. To start a return:

1. Log into your account
2. Go to Order History
3. Select the item to return
4. Choose return reason
5. Print return label

Refunds are processed within 5-7 business days.

## What items cannot be returned?

The following items are final sale:
- Personalized or custom items
- Opened software or digital products
- Perishable goods
- Intimate apparel
```

**Metadata:** Include for filtering

```markdown
---
location_id: store-123
category: policies
language: en
last_updated: 2025-01-15
---
```

**Language:** Match your customer base

**Scope:** Public information only - no sensitive data

### What to Include

**Business Information:**
- Company overview and history
- Locations and contact information
- Products/services offered
- Pricing and availability
- Hours of operation

**Policies and Procedures:**
- Return/refund policies
- Terms and conditions
- Privacy policy
- Accessibility information
- Warranty information

**Operational Details:**
- Shipping/delivery options
- Payment methods
- Support channels
- FAQ and troubleshooting
- Getting started guides

### Deployment

Knowledge base is automatically deployed:

```bash
# Update markdown files in your repository
# Then deploy
pnpm exec nx deploy infra
```

The CDK stack:
- Uploads documents to S3
- Creates/updates Amazon Bedrock knowledge base
- Configures vector embeddings
- Sets up metadata filters

## Step 3: Connect Your Existing APIs

This is where AgentCore Gateway provides the most value - it wraps your existing REST APIs without requiring any changes to them.

### How AgentCore Gateway Works

```
User: "Do you have product ABC in stock?"
    ↓
Agent decides to check inventory
    ↓
Agent calls MCP tool: checkInventory(product_id="ABC")
    ↓
AgentCore Gateway receives MCP call
    ↓
Gateway validates JWT token from agent (inbound auth)
    ↓
Gateway reads OpenAPI spec to understand the tool
    ↓
Gateway translates to HTTP: POST /inventory/check
                            {"product_id": "ABC"}
    ↓
Gateway authenticates to your API (outbound auth: OAuth/IAM/API Key)
    ↓
Your existing API processes request
    ↓
Your API returns: {"available": true, "quantity": 42}
    ↓
Gateway translates HTTP response to MCP format
    ↓
Agent receives: {"available": true, "quantity": 42}
    ↓
Agent: "Yes, we have 42 units of product ABC in stock."
```

### What You Need

**1. Your Existing REST API**

Any HTTP API that accepts and returns JSON:

- **Internal microservices** - Your company's backend services
- **Third-party APIs** - Salesforce, Shopify, Stripe, etc.
- **Legacy systems** - Older systems with HTTP interfaces
- **SaaS platforms** - Any service with a REST API
- **AWS services** - AWS Lambda functions behind Amazon API Gateway

**No changes to your API required.**

**2. OpenAPI 3.0 Specification**

This is the critical integration point. The OpenAPI spec tells AgentCore Gateway:
- What endpoints exist
- What parameters they accept
- What responses they return
- When agents should use each tool

If you don't have an OpenAPI spec, create one. If you have one, enhance it with agent-friendly descriptions.

### Writing Agent-Friendly OpenAPI Specs

**The most important insight:** Descriptions determine when agents call tools. Write them from the agent's perspective, not a developer's perspective.

#### Complete Example

```yaml
openapi: 3.0.0
info:
  title: Retail Inventory API
  version: 1.0.0
  description: API for managing product inventory and orders

servers:
  - url: https://api.yourcompany.com/v1
    description: Production API

paths:
  /inventory/check:
    post:
      operationId: checkInventory
      
      summary: Check product availability and stock levels
      
      description: |
        Use this tool when a customer asks about product availability,
        stock levels, or whether an item is in stock.
        
        This tool returns:
        - Current inventory count across all locations
        - Availability status (in stock / out of stock / low stock)
        - Stock levels by specific location if requested
        - Estimated restock date if currently out of stock
        
        WHEN TO USE THIS TOOL:
        - Customer asks "Do you have [product] in stock?"
        - Customer asks "How many [product] are available?"
        - Customer asks "When will [product] be back in stock?"
        - Customer asks "Is [product] available at [location]?"
        
        IMPORTANT: Always call this tool BEFORE attempting to create
        an order to verify the product is available. If the product
        is out of stock, inform the customer of the restock date and
        offer to notify them or suggest similar products.
        
        COMMON SCENARIOS:
        - In stock: Confirm availability and proceed with order
        - Low stock: Mention limited availability to create urgency
        - Out of stock: Provide restock date and alternatives
      
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - product_id
              properties:
                product_id:
                  type: string
                  description: |
                    Unique product identifier (SKU or product code).
                    This is the internal product ID, not the display name.
                    Example: "PROD-12345" or "SKU-SHIRT-BLU-M"
                  example: "PROD-12345"
                
                location_id:
                  type: string
                  description: |
                    Optional warehouse or store location to check.
                    If not provided, returns inventory across all locations.
                    Use this when customer asks about a specific store.
                    Example: "STORE-NYC-001" or "WAREHOUSE-WEST"
                  example: "STORE-NYC-001"
      
      responses:
        '200':
          description: Inventory information retrieved successfully
          content:
            application/json:
              schema:
                type: object
                required:
                  - product_id
                  - available
                  - total_quantity
                properties:
                  product_id:
                    type: string
                    description: Product identifier that was checked
                    example: "PROD-12345"
                  
                  available:
                    type: boolean
                    description: |
                      Whether product is currently in stock.
                      true = in stock, false = out of stock
                    example: true
                  
                  total_quantity:
                    type: integer
                    description: |
                      Total stock quantity across all locations.
                      0 means out of stock.
                    example: 42
                  
                  stock_status:
                    type: string
                    enum: [in_stock, low_stock, out_of_stock]
                    description: |
                      Stock status indicator:
                      - in_stock: Plenty available (>10 units)
                      - low_stock: Limited availability (1-10 units)
                      - out_of_stock: Not available (0 units)
                    example: "in_stock"
                  
                  locations:
                    type: array
                    description: Stock levels by location
                    items:
                      type: object
                      properties:
                        location_id:
                          type: string
                          example: "STORE-NYC-001"
                        location_name:
                          type: string
                          example: "New York City Store"
                        quantity:
                          type: integer
                          example: 15
                  
                  restock_date:
                    type: string
                    format: date
                    nullable: true
                    description: |
                      Expected restock date if out of stock.
                      null if product is in stock.
                      Format: YYYY-MM-DD
                    example: "2025-02-15"
        
        '404':
          description: Product not found
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
                    example: "Product not found"
                  product_id:
                    type: string
                    example: "PROD-12345"

  /orders:
    post:
      operationId: createOrder
      
      summary: Create a new customer order
      
      description: |
        Use this tool to create a new order after confirming:
        1. Product availability (call checkInventory first)
        2. Customer information is collected
        3. Shipping address is provided
        4. Customer has confirmed all details
        
        PREREQUISITES:
        - MUST call checkInventory first to verify stock
        - MUST collect customer name, email, phone
        - MUST collect complete shipping address
        - MUST confirm order details with customer
        
        DO NOT create order if:
        - Product is out of stock
        - Customer information is incomplete
        - Customer has not confirmed details
        
        After successful order creation:
        - Provide order confirmation number
        - Confirm shipping address
        - Provide estimated delivery date
        - Explain how to track the order
      
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - customer
                - items
                - shipping_address
              properties:
                customer:
                  type: object
                  required:
                    - name
                    - email
                    - phone
                  properties:
                    name:
                      type: string
                      description: Customer's full name
                      example: "Jane Smith"
                    email:
                      type: string
                      format: email
                      description: Customer's email address
                      example: "jane.smith@example.com"
                    phone:
                      type: string
                      description: Customer's phone number
                      example: "+1-555-123-4567"
                
                items:
                  type: array
                  description: List of products to order
                  minItems: 1
                  items:
                    type: object
                    required:
                      - product_id
                      - quantity
                    properties:
                      product_id:
                        type: string
                        example: "PROD-12345"
                      quantity:
                        type: integer
                        minimum: 1
                        example: 2
                
                shipping_address:
                  type: object
                  required:
                    - street
                    - city
                    - state
                    - postal_code
                    - country
                  properties:
                    street:
                      type: string
                      example: "123 Main St"
                    city:
                      type: string
                      example: "New York"
                    state:
                      type: string
                      example: "NY"
                    postal_code:
                      type: string
                      example: "10001"
                    country:
                      type: string
                      example: "USA"
      
      responses:
        '201':
          description: Order created successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  order_id:
                    type: string
                    description: Unique order confirmation number
                    example: "ORD-2025-001234"
                  status:
                    type: string
                    example: "confirmed"
                  total_amount:
                    type: number
                    format: decimal
                    description: Total order amount in USD
                    example: 149.99
                  estimated_delivery:
                    type: string
                    format: date
                    description: Estimated delivery date
                    example: "2025-01-25"
        
        '400':
          description: Invalid order request
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
                    example: "Product out of stock"
```

### OpenAPI Best Practices for Agents

**operationId (Required):**
- Clear, descriptive name in camelCase
- Becomes the tool name agents see
- Examples: `checkInventory`, `createOrder`, `scheduleAppointment`

**summary:**
- One-line description of what the operation does
- Action-oriented and concise
- Examples: "Check product availability", "Create customer order"

**description:**
- Most important field for agents
- Include:
  - When to use this tool
  - What information it provides
  - Prerequisites or dependencies
  - Common customer questions that trigger this tool
  - Important warnings or constraints
  - What to do with the response

**Parameter descriptions:**
- Explain what each parameter means
- Provide examples
- Specify valid values or formats
- Indicate if optional and what happens if omitted
- Explain relationships between parameters

**Response descriptions:**
- Explain what each field means
- Show example values
- Document all possible response codes
- Explain error conditions

**servers:**
- Point to your actual API URL
- Can include multiple environments

### Authentication Configuration

AgentCore Gateway supports multiple authentication methods:

**OAuth 2.0** (Recommended for user-delegated access)

```python
credential_provider_configurations=[{
    "credentialProviderType": "OAUTH",
    "credentialProvider": {
        "oauthCredentialProvider": {
            "providerArn": oauth_provider_arn,
            "scopes": ["read", "write"],
            "grantType": "AUTHORIZATION_CODE"
        }
    }
}]
```

**IAM Role** (For AWS services)

```python
credential_provider_configurations=[{
    "credentialProviderType": "GATEWAY_IAM_ROLE"
}]
```

**API Key** (For simple authentication)

```python
credential_provider_configurations=[{
    "credentialProviderType": "API_KEY",
    "credentialProvider": {
        "apiKeyCredentialProvider": {
            "providerArn": secret_arn,
            "credentialLocation": "HEADER",
            "credentialParameterName": "X-API-Key"
        }
    }
}]
```

### CDK Infrastructure Setup

For AWS-hosted APIs, use the provided constructs:

```python
# packages/infra/stack/your_stack.py
from stack_constructs.agentcore_gateway import AgentCoreGatewayConstruct
from stack_constructs.hotel_pms_api_construct import HotelPmsApiConstruct

# If you have an existing Lambda function
api_construct = HotelPmsApiConstruct(
    self,
    "YourApi",
    lambda_function=your_existing_lambda,
)

# Create AgentCore Gateway
agentcore_gateway = AgentCoreGatewayConstruct(
    self,
    "YourBusinessMCP",
    api_construct=api_construct,
    openapi_spec_path="../your-api/openapi.yaml",
)
```

The construct automatically:
- Creates AgentCore Gateway with JWT authentication
- Creates Identity Provider for OAuth
- Reads OpenAPI spec and creates Gateway Target
- Configures authentication and authorization

**For non-AWS APIs:**

You can still use AgentCore Gateway:

1. Create Gateway using AWS Console or CLI
2. Add your API as a target with OpenAPI spec
3. Configure outbound authentication
4. Point `servers` URL in OpenAPI to your API

### MCP Configuration

Both MCP servers are configured together:

```json
{
  "mcpServers": {
    "your-assistant-mcp": {
      "type": "streamable-http",
      "url": "https://runtime.bedrock-agentcore.region.amazonaws.com/...",
      "authentication": {
        "type": "cognito",
        "secretArn": "arn:aws:secretsmanager:..."
      },
      "systemPrompts": {
        "chat": "chat_system_prompt",
        "voice": "voice_system_prompt"
      }
    },
    "your-business-mcp": {
      "type": "streamable-http",
      "url": "https://gateway-id.gateway.bedrock-agentcore.region.amazonaws.com/mcp",
      "authentication": {
        "type": "cognito",
        "secretArn": "arn:aws:secretsmanager:..."
      }
    }
  }
}
```

This configuration is stored in Parameter Store and automatically created by the CDK stack.

## Testing Your Adaptation

### 1. Test Assistant MCP Server

```bash
cd packages/your-assistant-mcp
uv run python -m your_package.mcp.server
```

Verify:
- Server starts on port 8000
- Health check responds: `curl http://localhost:8000/health`
- Prompts load with your context
- Knowledge base queries return relevant results

### 2. Validate Your Existing API

Your API should already be working. Test:
- Endpoints respond correctly
- Authentication works
- Request/response formats are correct
- Error handling is appropriate

### 3. Validate OpenAPI Specification

```bash
# Validate syntax
npx @apidevtools/swagger-cli validate openapi.yaml
```

Manually verify:
- All endpoints are documented
- Every operation has `operationId`
- Descriptions are detailed and agent-friendly
- Schemas match actual request/response formats
- Server URL points to your API
- Authentication is specified

Test against your actual API:
- Make sample requests
- Verify responses match schema
- Test error conditions

### 4. Test AgentCore Gateway Integration

After deploying:

```bash
# List available tools
curl -X POST https://gateway-id.gateway.bedrock-agentcore.region.amazonaws.com/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/list"}'

# Call a tool
curl -X POST https://gateway-id.gateway.bedrock-agentcore.region.amazonaws.com/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "checkInventory",
      "arguments": {"product_id": "PROD-123"}
    }
  }'
```

Verify:
- Tools appear with correct names (from operationId)
- Tool descriptions are clear and helpful
- Tool calls translate to correct API requests
- Responses are properly formatted
- Errors are handled gracefully

### 5. Test End-to-End Agent Behavior

Test through all interfaces:

**Web Chat:**
```bash
pnpm exec nx serve demo
```

**LiveKit Voice:**
- Make test calls
- Verify speech recognition
- Test conversation flow

**WhatsApp/SMS:**
- Send test messages
- Verify responses
- Test multi-turn conversations

Verify:
- Agent uses your prompts correctly
- Agent calls tools at appropriate times
- Tool parameters are passed correctly
- Knowledge base provides relevant information
- Error handling works gracefully
- Authentication flows work
- Conversation memory persists

## Industry-Specific Examples

### Retail/E-commerce

**API Endpoints:**
```
POST /products/search       - Search product catalog
GET  /inventory/check       - Check stock availability
POST /orders                - Create order
GET  /orders/{id}           - Get order status
POST /returns               - Process return
GET  /recommendations       - Get product recommendations
```

**Knowledge Base:**
- Product descriptions and specifications
- Shipping and return policies
- Store locations and hours
- Size guides and fit information
- Product care instructions
- Promotions and discounts

**System Prompt Focus:**
- Product recommendation strategies
- Always check inventory before orders
- Upselling and cross-selling guidelines
- Return/exchange procedures
- Gift wrapping and special requests

### Healthcare/Medical

**API Endpoints:**
```
POST /appointments          - Schedule appointment
GET  /providers/availability - Check provider schedules
GET  /patients/{id}         - Get patient info (authorized)
POST /prescriptions/refill  - Request prescription refill
GET  /providers/search      - Search for providers
POST /messages              - Send secure message
```

**Knowledge Base:**
- Services offered
- Insurance accepted
- Office locations and hours
- Patient policies and procedures
- Health education materials
- Preparation instructions

**System Prompt Focus:**
- HIPAA-compliant language
- Medical terminology usage
- When to escalate to medical staff
- Privacy and consent protocols
- Emergency handling procedures
- Appointment confirmation requirements

**Important:** Ensure HIPAA compliance for all patient data.

### Financial Services

**API Endpoints:**
```
GET  /accounts/{id}/balance     - Get account balance
GET  /accounts/{id}/transactions - Get transaction history
POST /transfers                  - Transfer funds
POST /fraud/report               - Report fraud
GET  /statements/{id}            - Get statement
POST /payments                   - Make payment
```

**Knowledge Base:**
- Account types and features
- Fees and rates
- Security policies
- Branch locations and hours
- Financial products
- Regulatory disclosures

**System Prompt Focus:**
- Security verification procedures
- Fraud detection protocols
- Regulatory compliance language
- Financial advice disclaimers
- Transaction confirmation requirements
- Escalation for complex transactions

**Important:** Implement strong authentication and comprehensive audit logging.

### Real Estate

**API Endpoints:**
```
GET  /properties/search     - Search properties
POST /showings              - Schedule showing
GET  /properties/{id}       - Get property details
POST /offers                - Submit offer
GET  /applications/{id}     - Check application status
POST /inquiries             - Submit inquiry
```

**Knowledge Base:**
- Property listings
- Neighborhood information
- Financing options
- Application process
- Market trends
- School districts

**System Prompt Focus:**
- Property description strategies
- Showing scheduling protocols
- Offer negotiation guidelines
- Legal disclaimers
- When to involve human agents
- Qualification questions

## Infrastructure and Deployment

### Minimal Changes Required

The CDK infrastructure is designed to be reusable:

```python
# packages/infra/app.py
app_name = "your-business-assistant"  # Change application name

# packages/infra/stack/stack_config.py
# Update configuration values
```

### Environment Variables

```bash
# Assistant MCP
KNOWLEDGE_BASE_ID=auto-populated-by-cdk
YOUR_BUSINESS_TABLE=your-dynamodb-table
AWS_DEFAULT_REGION=us-east-1

# Business API (if needed)
YOUR_API_KEY=your-api-key
YOUR_SERVICE_URL=https://api.yourbusiness.com
```

### Deployment Process

```bash
# Deploy everything
pnpm exec nx deploy infra
```

CDK automatically:
- Deploys Assistant MCP as Lambda
- Syncs knowledge base to S3
- Creates Bedrock knowledge base
- Creates AgentCore Gateway
- Configures authentication
- Sets up networking and permissions

## Summary

Adapting the platform to your industry requires three focused changes:

1. **System Prompts** - Define agent behavior for your domain
2. **Knowledge Base** - Provide your business information
3. **API Integration** - Connect your existing APIs via AgentCore Gateway

**Key Advantages:**

- Use your existing APIs - no reimplementation needed
- AgentCore Gateway handles all MCP protocol complexity
- OpenAPI spec is the only integration point
- Multi-modal support (voice, chat, messaging) out of the box
- Scalable AWS infrastructure included
- Production-ready security and authentication

**The platform gives you:**

- Real-time speech-to-speech conversations
- Natural language understanding
- Multi-channel support (voice, chat, messaging)
- Conversation memory and context
- Secure authentication and authorization
- Scalable, serverless infrastructure

**You provide:**

- System prompts defining agent behavior
- Knowledge base with your business information
- OpenAPI spec describing your existing APIs

The result is a production-ready conversational AI system customized for your specific industry and business needs.

## Getting Help

**Documentation:**
- `documentation/architecture.md` - Infrastructure details
- `documentation/technical_approach.md` - Design patterns
- `documentation/security.md` - Security best practices
- `documentation/troubleshooting.md` - Common issues

**AWS Resources:**
- [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/)
- [AgentCore Gateway documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [LiveKit documentation](https://docs.livekit.io/)
- [MCP protocol specification](https://modelcontextprotocol.io/)

**Testing Strategy:**
- Start with the hotel implementation to understand patterns
- Modify one component at a time
- Test thoroughly at each step
- Use staging environment before production
- Monitor and iterate based on real usage
