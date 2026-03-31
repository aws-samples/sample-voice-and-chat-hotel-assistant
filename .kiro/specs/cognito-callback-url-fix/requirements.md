# Requirements Document

## Introduction

The Hotel Assistant frontend authentication is failing due to a Cognito User
Pool callback URL mismatch. The current Cognito configuration only includes
callback URLs for `localhost:5173` and `localhost:3000`, but the frontend is
running on `localhost:4200`, causing a `redirect_mismatch` error during OAuth
authentication flow.

## Requirements

### Requirement 1

**User Story:** As a developer, I want to be able to authenticate with the Hotel
Assistant frontend running on any common development port, so that I can develop
and test the application without authentication failures.

#### Acceptance Criteria

1. WHEN the frontend runs on `localhost:4200` THEN the Cognito authentication
   SHALL complete successfully
2. WHEN the frontend runs on `localhost:5173` THEN the Cognito authentication
   SHALL continue to work as before
3. WHEN the frontend runs on `localhost:3000` THEN the Cognito authentication
   SHALL continue to work as before
4. WHEN the frontend runs on `localhost:4173` THEN the Cognito authentication
   SHALL complete successfully (common Vite alternative port)

### Requirement 2

**User Story:** As a developer, I want the Cognito configuration to support
common development scenarios, so that team members can run the frontend on
different ports without infrastructure changes.

#### Acceptance Criteria

1. WHEN the Cognito User Pool is deployed THEN it SHALL include callback URLs
   for all common development ports
2. WHEN the Cognito User Pool is deployed THEN it SHALL include logout URLs for
   all common development ports
3. WHEN a developer uses a supported port THEN they SHALL be able to complete
   the full OAuth flow without errors
4. WHEN the infrastructure is redeployed THEN the callback URL configuration
   SHALL persist correctly

### Requirement 3

**User Story:** As a developer, I want clear documentation of supported
development URLs, so that I know which ports I can use for local development.

#### Acceptance Criteria

1. WHEN reviewing the infrastructure code THEN the supported callback URLs SHALL
   be clearly documented
2. WHEN setting up local development THEN the README SHALL specify which ports
   are supported
3. WHEN encountering authentication issues THEN the error messages SHALL be
   clear about URL mismatches
4. WHEN adding new development ports THEN the process SHALL be documented and
   straightforward
