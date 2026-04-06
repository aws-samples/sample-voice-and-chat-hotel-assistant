# Implementation Plan

- [x] 1. Create and run Lambda package AST analysis
  - Create Lambda package AST analysis script at `scripts/analyze_dead_code.py`
  - Script analyzes from `api_gateway_handler.py` entrypoint
  - Execute script: `python scripts/analyze_dead_code.py`
  - Review generated `dead_code_report.md` for Lambda package dead code
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Create and run Infrastructure AST analysis
  - Create Infrastructure AST analysis script at
    `scripts/analyze_cdk_dead_constructs.py`
  - Script analyzes from `packages/infra/app.py` entrypoint
  - Execute script: `python scripts/analyze_cdk_dead_constructs.py`
  - Review generated `cdk_dead_constructs_report.md` for Infrastructure dead
    code
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 3. Remove Aurora-related Lambda code based on analysis report
  - Review `dead_code_report.md` to identify Aurora-related files
  - Delete identified Aurora database code (connection, schema, queries)
  - Delete
    `packages/hotel-pms-simulation/hotel_pms_lambda/handlers/db_custom_resource.py`
  - Delete Aurora client wrapper if identified
  - Delete Aurora-related test files identified in report
  - _Requirements: 2.1, 2.2_

- [x] 4. Remove dead Infrastructure constructs based on analysis report
  - Review `cdk_dead_constructs_report.md` (7 unused constructs identified)
  - Delete Aurora constructs: `aurora_construct.py`,
    `database_setup_construct.py`
  - Delete old AgentCore constructs: `agentcore_gateway_construct.py`,
    `agentcore_lambda_construct.py`
  - Delete old Bedrock KB construct: `bedrock_knowledge_base_construct.py`
  - Delete unused CloudFront construct: `cloudfront_constructs.py`
  - Delete unused Lambda function: `stack/lambdas/update_config_js_fn/index.py`
  - Update `packages/infra/stack/hotel_pms_stack.py` to remove dead construct
    imports
  - Remove CloudFormation outputs for deleted constructs
  - Note: VPC construct is still in use - DO NOT remove
  - _Requirements: 2.1, 2.2_

- [x] 5. Create and run renaming script
  - Create `scripts/rename_simplified.py` with renaming logic
  - Define RENAME*MAP for all files and classes with "simplified*" prefix
  - Implement file renaming function
  - Implement import update function with regex patterns
  - Execute script to rename files and update all imports
  - _Requirements: 3.1, 3.2_

- [x] 6. Validate Lambda package cleanup
  - Run `python -m py_compile` on all Lambda package files to check for syntax
    errors
  - Execute `uv run pytest` in `packages/hotel-pms-simulation` to verify all
    tests pass
  - Search for remaining "simplified*" references: `grep -r "simplified*"
    hotel_pms_lambda/`
  - Search for remaining Aurora references:
    `grep -r "aurora\|Aurora" hotel_pms_lambda/`
  - Verify API Gateway handler imports:
    `uv run python -c "from hotel_pms_lambda.handlers.api_gateway_handler import lambda_handler"`
  - _Requirements: 4.1, 4.2_

- [x] 7. Validate Infrastructure cleanup
  - Run `uv run cdk synth` in `packages/infra` to verify CDK synthesis works
  - Check for remaining Aurora references in infrastructure code
  - Verify no broken imports in stack files
  - _Requirements: 4.1, 4.2_

- [ ] 8. Generate cleanup report
  - Create cleanup report documenting all changes
  - Include counts of files removed, renamed, and imports updated
  - List all Aurora code removed from Lambda and Infrastructure
  - List all files renamed with before/after names
  - Include validation results (tests passing, no broken imports, etc.)
  - Document code metrics (lines removed, test coverage maintained)
  - _Requirements: 4.2_
