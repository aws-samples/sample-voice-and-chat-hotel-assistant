# Design Document

## Overview

This design outlines a systematic approach to reviewing and addressing the 200+
security findings identified by static analysis tools in the Hotel Assistant
codebase. The focus is on evaluating each finding's actual risk in the prototype
context and either implementing fixes or documenting suppression decisions with
clear rationale.

## Architecture

### Manual Review Process

The security review follows a structured manual evaluation:

1. **Finding Categorization**: Group similar findings for efficient review
2. **Risk Assessment**: Evaluate actual security impact in prototype context
3. **Remediation Planning**: Identify specific code changes needed
4. **Implementation**: Apply fixes directly to codebase
5. **Documentation**: Record decisions and rationale
6. **Verification**: Confirm fixes resolve findings

### Finding Categories from Audit

#### checkov (2 findings)

- Docker container security (HEALTHCHECK, user creation)
- Infrastructure configuration issues

#### grype (2 findings)

- pnpm dependency vulnerabilities
- Package management security issues

#### semgrep (165+ findings)

- React props spreading (security risk)
- Logging patterns (error handling)
- Internationalization gaps
- Package dependency versioning
- Code quality patterns

#### bandit (25+ findings)

- SQL injection vectors in repository code
- HTTP requests without timeouts
- Python security patterns

#### CDK Nag (packages/infra/)

- AWS security best practices violations
- Existing suppressions with insufficient justification
- Infrastructure security patterns
- Reports available in `packages/infra/cdk.out/` after
  `pnpm exec nx run infra:synth`

### Decision Framework

#### MITIGATE (Fix Now)

- Easy fixes with clear security benefit
- Container security improvements
- Obvious SQL injection risks
- Missing timeouts in HTTP requests

#### SUPPRESS (Accept with Documentation)

- React props spreading (design decision)
- Logging patterns (acceptable for prototype)
- Internationalization (not in scope)
- Some dependency versioning (managed by lock files)

#### DOCUMENT (Production Hardening)

- Complex architectural changes
- Performance vs security tradeoffs
- Features not implemented in prototype

## Components and Interfaces

### Security Review Matrix

A structured evaluation of each finding type:

```markdown
| Finding Type         | Count | Risk Level | Effort | Decision | Rationale                  |
| -------------------- | ----- | ---------- | ------ | -------- | -------------------------- |
| Docker HEALTHCHECK   | 1     | Medium     | Low    | MITIGATE | Easy container improvement |
| Docker user creation | 1     | Medium     | Low    | MITIGATE | Security best practice     |
| pnpm vulnerabilities | 2     | High       | Medium | EVALUATE | Check actual impact        |
| Props spreading      | 40+   | Low        | High   | SUPPRESS | Design pattern choice      |
| SQL injection        | 25+   | High       | Medium | MITIGATE | Critical security issue    |
| HTTP timeouts        | 4     | Medium     | Low    | MITIGATE | Easy reliability fix       |
| Logging patterns     | 80+   | Low        | Medium | SUPPRESS | Acceptable for prototype   |
| Internationalization | 20+   | Low        | High   | SUPPRESS | Not in scope               |
| Package versioning   | 30+   | Low        | Low    | EVALUATE | Check lock file coverage   |
```

### Documentation Structure

```
docs/
├── SECURITY.md (updated with findings review)
└── security/
    ├── findings-analysis.md (detailed review)
    ├── suppression-decisions.md (documented suppressions)
    └── production-todo.md (future hardening tasks)
```

## Data Models

### Finding Review Record

Each finding will be documented with:

- **Finding ID**: Tool + Rule + File reference
- **Current Status**: OPEN, MITIGATED, SUPPRESSED, DOCUMENTED
- **Risk Assessment**: Actual security impact in prototype context
- **Decision**: MITIGATE, SUPPRESS, or DOCUMENT with rationale
- **Implementation**: Specific code changes or suppression rules
- **Verification**: How to confirm the fix works

### Suppression Configuration

For findings that should be suppressed using inline comments:

```typescript
// React props spreading - design decision for UI components
<Component {...props} /> // nosemgrep: react-props-spreading

// Internationalization - not in prototype scope
<div>Welcome</div> // nosemgrep: jsx-not-internationalized
```

```python
# SQL query construction - using parameterized queries where possible
cursor.execute(f"SELECT * FROM {table_name}") # nosec B608

# HTTP request - timeout not critical for internal services
response = requests.get(url) # nosec B113
```

```dockerfile
# Docker healthcheck - not required for prototype deployment
FROM python:3.12-slim # checkov:skip=CKV_DOCKER_2:Prototype deployment
```

```typescript
// CDK Nag suppression with proper justification
NagSuppressions.addResourceSuppressions(resource, [
  {
    id: 'AwsSolutions-IAM4',
    reason:
      'AWS managed policy acceptable for prototype - will use custom policy in production',
  },
]);
```

## Error Handling

### Code Changes

- Test all fixes to ensure no functionality breaks
- Use feature flags for risky changes
- Maintain rollback capability

### Suppression Rules

- Document why each suppression is acceptable
- Include conditions for future review
- Provide production remediation guidance

### Documentation

- Keep security documentation up to date
- Link findings to specific code locations
- Maintain traceability for audit purposes

## Testing Strategy

### Verification Testing

- Run security tools locally after fixes to confirm resolution
- Execute `pnpm exec nx run infra:synth` to generate updated CDK Nag reports
- Test application functionality after changes
- Validate suppression rules work correctly
- Compare before/after tool outputs to verify improvements

### Regression Testing

- Ensure fixes don't introduce new issues
- Test critical user flows after security changes
- Verify container builds and deployments still work

## Implementation Approach

### Phase 1: Infrastructure and High-Impact Fixes

1. Review CDK Nag suppressions in `packages/infra/` for proper justification
2. Fix Docker container security (HEALTHCHECK, user)
3. Add HTTP request timeouts in Python code
4. Address obvious SQL injection patterns
5. Update critical dependency versions

### Phase 2: Systematic Code Review

1. Categorize all semgrep findings by type and frequency
2. Evaluate each category for prototype relevance
3. Implement fixes for genuine security issues
4. Add inline suppressions with proper rationale for accepted risks

### Phase 3: Validation and Documentation

1. Run all security tools locally to verify fixes
2. Generate fresh CDK Nag reports with `pnpm exec nx run infra:synth`
3. Update docs/SECURITY.md with findings summary
4. Document production hardening requirements
5. Create baseline for future security scans

## Security Considerations

### Prototype Context

- Focus on genuine security risks, not code style
- Accept some technical debt for development velocity
- Document all security decisions for future reference

### Production Readiness

- Clearly separate prototype vs production requirements
- Provide roadmap for production security hardening
- Maintain awareness of accepted security debt

### Risk Management

- Prioritize data protection and system integrity
- Accept UI/UX security findings that don't affect core security
- Document risk acceptance with clear business rationale

## Performance Considerations

### Minimal Impact Changes

- Prefer configuration changes over code refactoring
- Use suppression rules instead of extensive code changes
- Focus on changes that improve both security and reliability

### Development Workflow

- Integrate security fixes into normal development process
- Avoid blocking development with extensive security refactoring
- Maintain clear separation between security and feature work
