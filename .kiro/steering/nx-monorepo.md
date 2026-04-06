---
inclusion: always
---

# NX Monorepo Development Guide

## Overview

This project uses NX monorepo with pnpm workspaces for efficient development and
build management. NX provides intelligent build caching, task orchestration, and
dependency graph analysis across all packages.

## Key NX Commands

All commands use the direct nx executor with static output style (configured as
default in nx.json):

### Development Commands

```bash
# Frontend development
pnpm exec nx serve frontend
pnpm exec nx build frontend
pnpm exec nx test frontend
pnpm exec nx lint frontend
pnpm exec nx preview frontend

# Infrastructure & Backend
pnpm exec nx deploy infra
pnpm exec nx diff infra
pnpm exec nx destroy infra
pnpm exec nx serve websocket-server
pnpm exec nx serve hotel-pms-simulation

# Load testing
pnpm exec nx test load-test

# Workspace-wide operations
pnpm exec nx run-many -t build
pnpm exec nx run-many -t lint
pnpm exec nx run-many -t format

# Project information
pnpm exec nx show projects
pnpm exec nx show project <project-name>
pnpm exec nx graph
```

### Affected Commands

Run tasks only for projects affected by changes:

```bash
# Build only affected projects
pnpm exec nx affected -t build

# Test only affected projects
pnpm exec nx affected -t test

# Lint only affected projects
pnpm exec nx affected -t lint

# Show affected projects
pnpm exec nx show projects --affected
```

### Multi-project Commands

```bash
# Run tasks for specific projects
pnpm exec nx run-many -t build --projects=frontend,hotel-pms-simulation
pnpm exec nx run-many -t lint --projects=frontend,websocket-server

# Run tasks for all projects
pnpm exec nx run-many -t build
pnpm exec nx run-many -t test
```

## NX Configuration

### Target Defaults (`nx.json`)

- **build**: Depends on upstream builds, uses production inputs, cached
- **test**: Uses default inputs plus vitest config, cached
- **lint**: Uses default inputs plus ESLint config, cached
- **dev/serve**: Not cached (development servers)

### Named Inputs

- **default**: All project files plus shared globals
- **production**: Excludes test files, specs, and config files
- **sharedGlobals**: Currently empty but available for workspace-wide files

## Project Structure

Each package has a `project.json` file defining its NX configuration:

```json
{
  "name": "package-name",
  "targets": {
    "build": {
      /* build configuration */
    },
    "test": {
      /* test configuration */
    },
    "lint": {
      /* lint configuration */
    }
  }
}
```

## Package-specific Commands

For dependency management, use pnpm filters, but for task execution, always use
nx:

```bash
# Add dependencies to specific packages
pnpm --filter @virtual-assistant/frontend add <dependency>
pnpm --filter @hotel-assistant/load-test add <dependency>

# Run tasks using nx (preferred)
pnpm exec nx serve frontend
pnpm exec nx test load-test

# For Python packages, use uv within the package directory
cd packages/hotel-pms-simulation && uv add <dependency>
cd packages/infra && uv add <dependency>
```

## NX Monorepo Benefits

### Intelligent Build Caching

- NX caches build outputs and only rebuilds what's changed
- Shared cache across team members and CI/CD
- Significant time savings on repeated builds

### Task Orchestration

- Automatically handles task dependencies (e.g., frontend build before
  infrastructure deploy)
- Parallel execution of independent tasks
- Proper ordering of dependent tasks

### Dependency Graph

- Visualize and understand project relationships with `pnpx nx graph`
- Understand impact of changes across the monorepo
- Identify circular dependencies

### Affected Commands

- Run tasks only for projects affected by your changes
- Efficient CI/CD pipelines that only test/build what changed
- Faster development feedback loops

### Consistent Tooling

- Unified commands across different technologies (React, Python, Docker)
- Consistent task naming and execution
- Shared configuration and standards

## Local Development Workflows

### Full Stack Development

```bash
# Terminal 1: Start frontend
pnpm exec nx serve frontend

# Terminal 2: Start WebSocket server
pnpm exec nx serve websocket-server

# Terminal 3: Start hotel PMS API
pnpm exec nx serve hotel-pms-simulation

# Terminal 4: Run load tests against local setup
pnpm exec nx test load-test
```

### Frontend-only Development

```bash
# Start frontend with hot reload
pnpm exec nx serve frontend

# Build and preview frontend
pnpm exec nx build frontend
pnpm exec nx preview frontend
```

### Infrastructure Development

```bash
# Show what changes will be deployed
pnpm exec nx diff infra

# Deploy infrastructure changes
pnpm exec nx deploy infra

# Destroy infrastructure (cleanup)
pnpm exec nx destroy infra
```

## Best Practices

1. **Use direct nx commands**: Always use `pnpm exec nx` for consistent output
   (static style is configured as default)
2. **Leverage caching**: Let NX handle caching, don't bypass it unnecessarily
3. **Check affected**: Use `pnpm exec nx affected` in CI/CD for efficiency
4. **Visualize dependencies**: Use `pnpm exec nx graph` to understand project
   relationships
5. **Keep project.json clean**: Only include necessary target configurations
6. **Use consistent naming**: Follow established target naming conventions
   (build, test, lint, serve)
7. **Static output**: The workspace is configured with static output style by
   default in nx.json

## Troubleshooting

### Cache Issues

```bash
# Clear NX cache
pnpm exec nx reset

# Clean everything (use package.json script for this)
pnpm clean
```

### Dependency Issues

```bash
# Reinstall all dependencies (use package.json script)
pnpm clean && pnpm install
```

### Build Issues

```bash
# Check project configuration
pnpm exec nx show project <project-name>

# Run with verbose output
pnpm exec nx <target> <project> --verbose

# Show project graph for debugging dependencies
pnpm exec nx graph
```
