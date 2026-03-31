/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import RuntimeConfigProvider from './index';

// Mock fetch
global.fetch = vi.fn();

// Simple test component
const TestComponent = () => <div data-testid="test-content">Test Content</div>;

// Mock the GlobalUIContext
vi.mock('../../hooks/useGlobalUIContext', () => ({
  useGlobalUIContext: () => ({
    addFlashItem: vi.fn(),
  }),
}));

describe('RuntimeConfigProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock fetch to return a rejected promise by default
    (global.fetch as any).mockRejectedValue(new Error('Not found'));
  });

  it('should render children when config is loaded from fetch', async () => {
    const mockConfig = {
      cognitoProps: {
        userPoolId: 'us-east-1_test123',
        userPoolWebClientId: 'test-client-id',
        region: 'us-east-1',
      },
      messagingApiEndpoint: 'https://api.test.com',
      hotelAssistantClientId: 'hotel-test-id',
      applicationName: 'Test Hotel Assistant',
    };

    // Mock successful fetch
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockConfig),
    });

    await act(async () => {
      render(
        <RuntimeConfigProvider>
          <TestComponent />
        </RuntimeConfigProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('test-content')).toBeInTheDocument();
    });
  });

  it('should show error when configuration is missing', async () => {
    // Mock fetch to fail and no environment variables
    (global.fetch as any).mockRejectedValue(new Error('Not found'));

    // Mock import.meta.env to have missing required variables
    Object.defineProperty(import.meta, 'env', {
      value: {
        VITE_COGNITO_USER_POOL_ID: undefined,
        VITE_COGNITO_USER_POOL_CLIENT_ID: undefined,
        VITE_AWS_REGION: undefined,
        VITE_MESSAGING_API_ENDPOINT: undefined,
        VITE_HOTEL_ASSISTANT_CLIENT_ID: undefined,
      },
      writable: true,
    });

    await act(async () => {
      render(
        <RuntimeConfigProvider>
          <TestComponent />
        </RuntimeConfigProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByText('Configuration error')).toBeInTheDocument();
    });

    // Should not render the test content
    expect(screen.queryByTestId('test-content')).not.toBeInTheDocument();
  });
});
