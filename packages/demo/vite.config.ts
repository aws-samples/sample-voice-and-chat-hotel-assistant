/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import tsconfigPaths from 'vite-tsconfig-paths';
import { tanstackRouter } from '@tanstack/router-plugin/vite';
/// <reference types='vitest' />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const licenseHeader = readFileSync(resolve(__dirname, '../../LICENSE_HEADER'), 'utf-8')
  .trim()
  .split('\n')
  .map((line) => ` * ${line}`.trimEnd());
const routeTreeFileHeader = [`/**\n${licenseHeader.join('\n')}\n */`];

export default defineConfig({
  define: {
    global: {},
  },
  root: __dirname,
  cacheDir: '../../node_modules/.vite/packages/demo',
  server: {
    port: 4200,
    host: 'localhost',
  },
  preview: {
    port: 4300,
    host: 'localhost',
  },
  plugins: [
    react(),
    tanstackRouter({
      routesDirectory: `${__dirname}/src/routes`,
      generatedRouteTree: `${__dirname}/src/routeTree.gen.ts`,
      routeTreeFileHeader,
    }),
    tsconfigPaths(),
  ],
  build: {
    outDir: '../../dist/packages/demo',
    emptyOutDir: true,
    reportCompressedSize: true,
    commonjsOptions: {
      transformMixedEsModules: true,
    },
  },
  test: {
    watch: false,
    globals: true,
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    reporters: ['default'],
    coverage: {
      reportsDirectory: './test-output/vitest/coverage',
      provider: 'v8',
    },
    passWithNoTests: true,
  },
});
