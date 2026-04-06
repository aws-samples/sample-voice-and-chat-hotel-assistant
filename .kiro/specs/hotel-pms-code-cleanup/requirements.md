# Requirements Document

## Introduction

This specification defines the cleanup of dead code and renaming of
"simplified*" objects in the hotel-pms-simulation package. After migrating from
Aurora Serverless to DynamoDB and implementing the simplified Hotel PMS logic,
there is significant dead code related to the old database architecture that
should be removed. Additionally, the "simplified*" naming prefix is no longer
meaningful and should be removed.

**Architectural Context:**

- This cleanup is part of the **Hotel PMS Stack** simplification
- Removes Aurora Serverless-related code that is no longer used
- Renames "simplified\_" objects to cleaner names
- Uses AST analysis to identify unused code from the API Gateway handler
  entrypoint
- Removes tests for deleted code

## Glossary

- **Dead_Code**: Source files and objects that are no longer referenced from
  active entrypoints
- **Entrypoint**: The API Gateway handler that serves as the main entry to the
  application
- **AST_Analysis**: Abstract Syntax Tree analysis to identify code dependencies
- **Simplified_Prefix**: Naming convention used during migration that is no
  longer needed
- **Aurora_Code**: Code related to the old Aurora Serverless database
  architecture

## Requirements

### Requirement 1: AST-Based Dead Code Detection

**User Story:** As a developer, I want to use AST analysis to identify unused
code, so that I can safely remove dead code without breaking the application.

#### Acceptance Criteria

1. THE System SHALL analyze
   `packages/hotel-pms-simulation/hotel_pms_lambda/handlers/api_gateway_handler.py`
   as the entrypoint
2. THE System SHALL build a dependency graph of all imported modules and
   functions
3. THE System SHALL identify source files that are not in the dependency graph
4. THE System SHALL identify functions and classes that are not referenced
5. THE System SHALL generate a report of dead code to be removed

### Requirement 2: Remove Aurora Serverless Code from Lambda Package

**User Story:** As a developer, I want to remove Aurora Serverless-related code
from the Lambda package, so that the codebase only contains relevant DynamoDB
implementation.

#### Acceptance Criteria

1. THE System SHALL remove database connection code for Aurora PostgreSQL
2. THE System SHALL remove SQL query implementations
3. THE System SHALL remove database schema definitions for Aurora
4. THE System SHALL remove custom resources for Aurora database setup in Lambda
5. THE System SHALL remove Aurora-related configuration and utilities

### Requirement 3: Remove Aurora Serverless Infrastructure Code

**User Story:** As a DevOps engineer, I want to remove Aurora Serverless
infrastructure code from the CDK stack, so that the infrastructure only includes
DynamoDB resources.

#### Acceptance Criteria

1. THE System SHALL remove Aurora Serverless construct from `packages/infra/`
2. THE System SHALL remove VPC construct used only for Aurora
3. THE System SHALL remove database custom resources for Aurora schema setup
4. THE System SHALL remove Aurora-related IAM roles and policies
5. THE System SHALL remove Aurora-related CloudFormation outputs

### Requirement 4: Remove "simplified\_" Naming Prefix

**User Story:** As a developer, I want to remove the "simplified\_" prefix from
object names, so that the code has cleaner, more professional naming.

#### Acceptance Criteria

1. THE System SHALL rename `SimplifiedAvailabilityService` to
   `AvailabilityService`
2. THE System SHALL rename `SimplifiedReservationService` to
   `ReservationService`
3. THE System SHALL rename `SimplifiedHotelService` to `HotelService`
4. THE System SHALL rename `simplified_tools.py` to `tools.py`
5. THE System SHALL update all imports and references to use new names

### Requirement 5: Remove Unused Test Files

**User Story:** As a developer, I want to remove tests for deleted code, so that
the test suite only covers active functionality.

#### Acceptance Criteria

1. THE System SHALL identify test files for removed source files
2. THE System SHALL remove tests for Aurora Serverless functionality
3. THE System SHALL update test imports to use renamed modules
4. THE System SHALL verify remaining tests pass after cleanup
5. THE System SHALL maintain test coverage for active functionality

### Requirement 6: Update Import Statements

**User Story:** As a developer, I want all import statements updated
automatically, so that the application continues to work after renaming.

#### Acceptance Criteria

1. THE System SHALL update imports in `api_gateway_handler.py` to use renamed
   modules
2. THE System SHALL update imports in service files to use renamed dependencies
3. THE System SHALL update imports in test files to use renamed modules
4. THE System SHALL verify no broken imports remain
5. THE System SHALL use Python's AST to ensure import correctness

### Requirement 6: Clean Up Directory Structure

**User Story:** As a developer, I want a clean directory structure, so that the
codebase is easy to navigate.

#### Acceptance Criteria

1. THE System SHALL remove empty directories after file deletion
2. THE System SHALL organize remaining files logically (services, tools,
   handlers)
3. THE System SHALL remove unused `__init__.py` files
4. THE System SHALL update `__init__.py` exports to reflect renamed modules
5. THE System SHALL maintain proper Python package structure

### Requirement 7: Validation and Testing

**User Story:** As a QA engineer, I want comprehensive validation after cleanup,
so that I can verify the application still works correctly.

#### Acceptance Criteria

1. THE System SHALL run all remaining tests and verify they pass
2. THE System SHALL verify the API Gateway handler imports successfully
3. THE System SHALL check for any remaining "simplified\_" references
4. THE System SHALL verify no Aurora-related code remains
5. THE System SHALL generate a cleanup report with statistics

### Requirement 8: Documentation Updates

**User Story:** As a developer, I want documentation updated to reflect the
cleanup, so that future developers understand the current architecture.

#### Acceptance Criteria

1. THE System SHALL update README files to remove Aurora references
2. THE System SHALL update code comments to use new naming
3. THE System SHALL update docstrings to reflect renamed classes
4. THE System SHALL remove outdated architecture documentation
5. THE System SHALL maintain accurate API documentation

## Success Criteria

### Functional Success

- [ ] All dead code identified and removed
- [ ] All "simplified\_" prefixes removed from code
- [ ] All imports updated and working
- [ ] All remaining tests pass
- [ ] API Gateway handler works correctly

### Quality Success

- [ ] No broken imports or references
- [ ] No Aurora-related code remains
- [ ] Clean, professional naming throughout
- [ ] Reduced codebase size by removing dead code
- [ ] Improved code maintainability

## Acceptance Criteria

### Code Cleanup

- [ ] AST analysis identifies all unused code
- [ ] Aurora Serverless code completely removed
- [ ] "simplified\_" prefix removed from all objects
- [ ] Import statements updated correctly
- [ ] Directory structure cleaned up

### Testing

- [ ] All remaining tests pass
- [ ] Test coverage maintained for active code
- [ ] No tests for deleted code remain
- [ ] Integration tests verify API functionality

### Validation

- [ ] No broken imports
- [ ] No "simplified\_" references remain
- [ ] No Aurora code remains
- [ ] Cleanup report generated
- [ ] Documentation updated

## Constraints

### Technical Constraints

- **Python Version**: Python 3.13+ for AST analysis
- **Backward Compatibility**: Not required (internal refactoring)
- **API Compatibility**: Must maintain API Gateway handler interface

### Business Constraints

- **Timeline**: Single developer implementation
- **Risk**: Must not break existing functionality

## Dependencies

### External Dependencies

- **Python AST**: For code analysis and dependency graphing
- **pytest**: For running tests after cleanup

### Internal Dependencies

- **API Gateway Handler**: Entrypoint for dependency analysis
- **Existing Tests**: Validation that cleanup doesn't break functionality

## Deliverables

### Code Deliverables

- [ ] AST analysis script for dead code detection
- [ ] Renamed service files (remove "simplified\_" prefix)
- [ ] Updated import statements throughout codebase
- [ ] Removed Aurora Serverless code
- [ ] Removed unused test files
- [ ] Cleanup report with statistics

### Documentation Deliverables

- [ ] Cleanup report showing removed files and renamed objects
- [ ] Updated README files
- [ ] Updated code documentation
