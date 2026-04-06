/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useSendMessage, useMessages, useConversationId } from './messaging-hooks';
import { vi } from 'vitest';

// Mock the messaging API client
vi.mock('./messaging-api-client', () => ({
  useMessagingApiClient: vi.fn(() => ({
    sendMessage: vi.fn(),
    getMessages: vi.fn(),
    getCurrentUserId: vi.fn(),
    generateConversationId: vi.fn(),
  })),
}));

// Mock react-oidc-context
vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'mock-token' },
    isAuthenticated: true,
  }),
}));

// Mock GlobalUIContextProvider
vi.mock('../components/GlobalUIContextProvider', () => ({
  useGlobalUIContext: () => ({
    addFlashMessage: vi.fn(),
  }),
}));
// Simple test wrapper
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('messaging hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useSendMessage', () => {
    it('should return mutation function', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useSendMessage('https://api.example.com'), { wrapper });

      expect(result.current.mutate).toBeDefined();
      expect(result.current.isPending).toBe(false);
    });
  });

  describe('useMessages', () => {
    it('should return query result', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useMessages('conv-123', false), { wrapper });

      expect(result.current.data).toBeUndefined();
      expect(result.current.isLoading).toBeDefined();
    });
  });

  describe('useConversationId', () => {
    it('should return query result', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useConversationId('assistant-123'), { wrapper });

      expect(result.current.data).toBeUndefined();
      expect(result.current.isLoading).toBeDefined();
    });
  });
});