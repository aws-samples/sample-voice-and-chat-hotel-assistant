# Implementation Plan

- [x] 1. Setup and baseline security scan
  - Run all security tools locally to establish current baseline
  - Generate CDK Nag reports with `cdk synth` in packages/infra/
  - Document current finding counts by tool and category
  - _Requirements: 1.1, 1.2_

- [ ] 2. Review and fix CDK Nag findings in infrastructure
- [x] 2.1 Audit existing CDK Nag suppressions in packages/infra/
  - Review all NagSuppressions.addResourceSuppressions calls
  - Identify suppressions with insufficient justification
  - Document which suppressions are appropriate for prototype vs production
  - _Requirements: 1.3, 2.2_

- [x] 2.2 Update CDK Nag suppressions with proper rationale
  - Add detailed justification comments for each suppression
  - Remove unnecessary suppressions where fixes are simple
  - Ensure suppression reasons clearly state prototype vs production context
  - _Requirements: 3.1, 3.3_

- [ ] 3. Address high-impact security findings
- [x] 3.1 Fix Docker container security issues
  - Add HEALTHCHECK instructions to Dockerfiles
  - Create non-root users in container images
  - Update packages/hotel-assistant-chat/Dockerfile and
    packages/hotel-assistant-livekit/Dockerfile
  - _Requirements: 2.1, 4.1_

- [x] 3.2 Add HTTP request timeouts in Python code
  - Review bandit B113 findings for requests without timeout
  - Add appropriate timeout values to requests.get/post calls
  - Focus on packages/hotel-pms-lambda/ test files
  - _Requirements: 2.1, 4.1_

- [x] 3.3 Address SQL injection patterns
  - Run bandit and review bandit B608 findings in
    packages/hotel-pms-lambda/hotel_pms_lambda/database/
  - Evaluate if parameterized queries can replace string formatting
  - Add nosec comments with justification where string formatting is necessary
  - _Requirements: 2.1, 4.1_

- [ ] 4. Systematic review of semgrep findings
- [x] 4.1 Categorize React props spreading findings
  - Review all react-props-spreading findings in
    packages/frontend/src/components/ui/
  - Determine which are legitimate design patterns vs security risks
  - Add nosemgrep comments for accepted design patterns
  - _Requirements: 1.2, 2.2_

- [x] 4.2 Review logging error handling patterns
  - Evaluate logging-error-without-handling findings across Python packages
  - Determine which are acceptable for prototype logging patterns
  - Add nosemgrep comments for accepted logging patterns with rationale
  - _Requirements: 2.2, 3.3_

- [x] 4.3 Address internationalization findings
  - Review jsx-not-internationalized findings in packages/frontend/
  - Add nosemgrep comments since i18n is not in prototype scope
  - Document i18n as production recommendation in docs/IMPROVEMENTS.md
  - _Requirements: 2.2, 3.2_

- [ ] 4.4 Evaluate package dependency versioning
  - Review package-dependencies-check findings in package.json files
  - Verify that lock files provide version pinning
  - Add suppressions for dependencies managed by lock files
  - Update any dependencies with known security issues
  - _Requirements: 2.1, 4.1_

- [ ] 5. Handle grype dependency vulnerabilities
- [x] 5.1 Investigate pnpm vulnerabilities
  - Review GHSA-vm32-9rqf-rh3r and GHSA-8cc4-rfj6-fhg4 findings
  - Determine if vulnerabilities affect the prototype deployment
  - Update pnpm version if security fix is available and low-risk
  - Document decision rationale in SECURITY.md
  - _Requirements: 2.1, 3.1_

- [ ] 6. Documentation and validation
- [ ] 6.1 Update security documentation
  - Create or update docs/SECURITY.md with findings summary
  - Document all suppression decisions with clear rationale
  - Separate prototype security posture from production requirements
  - Include security baseline and future hardening roadmap
  - _Requirements: 3.1, 3.2, 5.1_

- [ ] 6.2 Validate fixes with local security scans
  - Re-run all security tools after implementing fixes
  - Generate new CDK Nag reports to verify infrastructure improvements
  - Compare before/after finding counts to measure progress
  - Document remaining findings and their acceptance rationale
  - _Requirements: 4.3, 5.2_

- [ ] 6.3 Create security maintenance procedures
  - Document how to run security tools locally for future development
  - Create checklist for reviewing new security findings
  - Establish baseline for CI/CD security scanning
  - Document suppression review process for production readiness
  - _Requirements: 5.3, 5.4_
