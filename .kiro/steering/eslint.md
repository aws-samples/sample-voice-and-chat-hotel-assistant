---
inclusion: fileMatch
fileMatchPattern: '**/*.{ts,tsx}'
---

# Development Guide

## Code Quality & Formatting

This project uses ESLint and Prettier to maintain consistent code quality and
formatting across all TypeScript packages.

### ESLint Configuration

- **Root Configuration**: `.eslintrc.json` - Base configuration for all
  TypeScript code
- **Package-specific**: Each package can extend the root config with specific
  overrides
- **Rules**: Strict TypeScript rules with consistent formatting and best
  practices

### Prettier Configuration

- **Root Configuration**: `prettier.config.js` - Base formatting rules
- **Package-specific**: Packages can override specific formatting options
- **Integration**: Automatically formats code on save in VS Code

### Available Scripts

```bash
# Lint all TypeScript files
pnpm lint

# Lint and auto-fix issues
pnpm lint:fix

# Format all files
pnpm format

# Check if files are properly formatted
pnpm format:check

# Run linting across all packages
pnpm lint:all

# Run formatting across all packages
pnpm format:all
```

### Pre-commit Hooks

The project uses Husky and lint-staged to ensure code quality:

- **Husky**: Manages Git hooks
- **lint-staged**: Runs linting and formatting only on staged files
- **Pre-commit**: Automatically runs ESLint and Prettier before each commit

### VS Code Integration

The `.vscode/settings.json` file configures:

- Format on save with Prettier
- Auto-fix ESLint issues on save
- Organize imports automatically
- Proper TypeScript import preferences

### CI/CD Integration

GitHub Actions workflow (`.github/workflows/ci.yml`) includes:

- Formatting checks
- ESLint validation
- TypeScript compilation checks
- Automated testing

### Package-specific Configurations

#### Frontend Package (`packages/frontend`)

- Extends root ESLint config
- Includes React-specific rules
- Tailwind CSS integration with Prettier
- Browser environment settings

### Best Practices

1. **Always run linting before committing**:

   ```bash
   pnpm lint:fix
   ```

2. **Use consistent import styles**:

   ```typescript
   // Prefer type imports
   import type { SomeType } from './types';
   import { someFunction } from './utils';
   ```

3. **Follow naming conventions**:
   - Use PascalCase for classes and interfaces
   - Use camelCase for functions and variables
   - Use UPPER_SNAKE_CASE for constants

4. **Handle unused variables**:
   ```typescript
   // Prefix with underscore for intentionally unused
   const handleClick = (_event: MouseEvent) => {
     // implementation
   };
   ```

### Troubleshooting

#### ESLint Issues

If you encounter ESLint errors:

1. Check if the file is in the correct location
2. Ensure TypeScript compilation is working
3. Run `pnpm lint:fix` to auto-fix issues
4. Check package-specific ESLint overrides

#### Prettier Issues

If formatting isn't working:

1. Ensure VS Code Prettier extension is installed
2. Check `.prettierignore` for excluded files
3. Verify the file type is supported
4. Run `pnpm format` manually

### Configuration Files

- `.eslintrc.json` - Root ESLint configuration
- `prettier.config.js` - Root Prettier configuration
- `.prettierignore` - Files to exclude from formatting
- `package.json` - lint-staged configuration
