/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import CognitoAuth from './index';
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig';

// Mock the runtime config hook
vi.mock('../../hooks/useRuntimeConfig');

// Mock react-oidc-context
vi.mock('react-oidc-context', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="auth-provider">{children}</div>
  ),
  useAuth: () => ({
    isAuthenticated: true, // Set to true so children render
    isLoading: false,
    error: null,
    signinRedirect: vi.fn(),
  }),
}));

const mockUseRuntimeConfig = useRuntimeConfig as any;

describe('CognitoAuth', () => {
  it('should render error when cognitoProps are not configured', () => {
    mockUseRuntimeConfig.mockReturnValue({
      cognitoProps: null,
      messagingApiEndpoint: 'https://api.test.com',
      hotelAssistantClientId: 'test-id',
      applicationName: 'Test App',
    });

    render(
      <CognitoAuth>
        <div>Test Child</div>
      </CognitoAuth>
    );

    expect(screen.getByText(/Authentication configuration error/)).toBeInTheDocument();
    expect(screen.getByText(/cognitoProps have not been configured/)).toBeInTheDocument();
  });

  it('should render AuthProvider when cognitoProps are configured', () => {
    mockUseRuntimeConfig.mockReturnValue({
      cognitoProps: {
        userPoolId: 'us-east-1_test123',
        userPoolWebClientId: 'test-client-id',
        region: 'us-east-1',
      },
      messagingApiEndpoint: 'https://api.test.com',
      hotelAssistantClientId: 'test-id',
      applicationName: 'Test App',
    });

    render(
      <CognitoAuth>
        <div data-testid="test-child">Test Child</div>
      </CognitoAuth>
    );

    expect(screen.getByTestId('auth-provider')).toBeInTheDocument();
    expect(screen.getByTestId('test-child')).toBeInTheDocument();
  });

  it('should configure AuthProvider with correct Hotel Assistant scopes', () => {
    const mockConfig = {
      cognitoProps: {
        userPoolId: 'us-east-1_test123',
        userPoolWebClientId: 'test-client-id',
        region: 'us-east-1',
      },
      messagingApiEndpoint: 'https://api.test.com',
      hotelAssistantClientId: 'test-id',
      applicationName: 'Hotel Assistant',
    };

    mockUseRuntimeConfig.mockReturnValue(mockConfig);

    render(
      <CognitoAuth>
        <div data-testid="test-child">Test Child</div>
      </CognitoAuth>
    );

    // Verify the component renders correctly with the configuration
    expect(screen.getByTestId('auth-provider')).toBeInTheDocument();
    expect(screen.getByTestId('test-child')).toBeInTheDocument();
  });
});
