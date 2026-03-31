/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useRuntimeConfig } from './useRuntimeConfig';
import { RuntimeConfigContext } from '../components/RuntimeConfig';
import { RuntimeConfig } from '../types';

describe('useRuntimeConfig', () => {
  it('should return runtime config when context is provided', () => {
    const mockConfig: RuntimeConfig = {
      cognitoProps: {
        userPoolId: 'us-east-1_test123',
        userPoolWebClientId: 'test-client-id',
        region: 'us-east-1',
      },
      messagingApiEndpoint: 'https://api.test.com',
      hotelAssistantClientId: 'test-id',
      applicationName: 'Test Hotel Assistant',
      logo: 'test-logo.png',
    };

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <RuntimeConfigContext.Provider value={mockConfig}>{children}</RuntimeConfigContext.Provider>
    );

    const { result } = renderHook(() => useRuntimeConfig(), { wrapper });

    expect(result.current).toEqual(mockConfig);
    expect(result.current.applicationName).toBe('Test Hotel Assistant');
    expect(result.current.cognitoProps.userPoolId).toBe('us-east-1_test123');
    expect(result.current.messagingApiEndpoint).toBe('https://api.test.com');
    expect(result.current.hotelAssistantClientId).toBe('test-id');
  });

  it('should throw error when used outside of RuntimeConfigProvider', () => {
    // Suppress console.error for this test since we expect an error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      renderHook(() => useRuntimeConfig());
    }).toThrow('useRuntimeConfig must be used within a RuntimeConfigProvider');

    consoleSpy.mockRestore();
  });

  it('should throw error when context value is undefined', () => {
    // Suppress console.error for this test since we expect an error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <RuntimeConfigContext.Provider value={undefined}>{children}</RuntimeConfigContext.Provider>
    );

    expect(() => {
      renderHook(() => useRuntimeConfig(), { wrapper });
    }).toThrow('useRuntimeConfig must be used within a RuntimeConfigProvider');

    consoleSpy.mockRestore();
  });
});
