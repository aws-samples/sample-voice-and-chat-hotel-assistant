/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useSendMessage, useMessages, useConversationId } from './messaging-hooks';
import { GlobalUIContext } from '../components/GlobalUIContextProvider';
import type { SendMessageResponse, GetMessagesResponse } from '../types';

// Mock the messaging API client
const mockApiClient = {
  sendMessage: vi.fn(),
  getMessages: vi.fn(),
  getMessagesSince: vi.fn(),
  getCurrentUserId: vi.fn(),
  generateConversationId: vi.fn(),
};

vi.mock('./messaging-api-client', () => ({
  useMessagingApiClient: vi.fn(() => mockApiClient),
}));

// Mock the GlobalUIContext
const mockAddFlashItem = vi.fn();
const mockGlobalUIContext = {
  flashItems: [],
  setFlashItems: vi.fn(),
  addFlashItem: mockAddFlashItem,
  toolsOpen: false,
  setToolsOpen: vi.fn(),
  helpPanelTopic: 'default',
  setHelpPanelTopic: vi.fn(),
  makeHelpPanelHandler: vi.fn(),
  appLayoutRef: { current: null },
};

// Test wrapper component
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <GlobalUIContext.Provider value={mockGlobalUIContext}>
        {children}
      </GlobalUIContext.Provider>
    </QueryClientProvider>
  );
};

describe('messaging hooks integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useSendMessage', () => {
    it('should successfully send a message', async () => {
      const mockResponse: SendMessageResponse = {
        message: {
          messageId: 'msg-123',
          conversationId: 'conv-123',
          senderId: 'user-123',
          recipientId: 'assistant-123',
          content: 'Hello',
          status: 'sent' as any,
          timestamp: '2024-01-01T00:00:00Z',
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: '2024-01-01T00:00:00Z',
        },
        success: true,
      };

      mockApiClient.sendMessage.mockResolvedValue(mockResponse);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSendMessage('https://api.example.com'), { wrapper });

      result.current.mutate({
        recipientId: 'assistant-123',
        content: 'Hello',
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockApiClient.sendMessage).toHaveBeenCalledWith(
        'assistant-123',
        'Hello',
        undefined,
        undefined,
        undefined
      );
    });

    it.skip('should handle errors and show flash notifications', async () => {
      const mockError = new Error('Network error');
      mockApiClient.sendMessage.mockRejectedValue(mockError);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSendMessage('https://api.example.com'), { wrapper });

      result.current.mutate({
        recipientId: 'assistant-123',
        content: 'Hello',
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      // Verify that flash notification was called
      expect(mockAddFlashItem).toHaveBeenCalled();
      const flashCall = mockAddFlashItem.mock.calls[0][0];
      expect(flashCall.type).toBe('error');
      expect(flashCall.content).toBe('Network error');
      expect(flashCall.dismissible).toBe(true);
    });
  });

  describe('useMessages', () => {
    it('should successfully retrieve messages', async () => {
      const mockResponse: GetMessagesResponse = {
        messages: [
          {
            messageId: 'msg-123',
            conversationId: 'conv-123',
            senderId: 'user-123',
            recipientId: 'assistant-123',
            content: 'Hello',
            status: 'sent' as any,
            timestamp: '2024-01-01T00:00:00Z',
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z',
            isUser: true,
          },
        ],
        success: true,
      };

      mockApiClient.getMessages.mockResolvedValue(mockResponse);

      const wrapper = createWrapper();
      const { result } = renderHook(
        () => useMessages('https://api.example.com', 'conv-123'),
        { wrapper }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockApiClient.getMessages).toHaveBeenCalledWith('conv-123');
      expect(result.current.data).toEqual(mockResponse);
    });

    it('should not fetch when conversationId is null', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () => useMessages('https://api.example.com', null),
        { wrapper }
      );

      expect(result.current.isFetching).toBe(false);
      expect(mockApiClient.getMessages).not.toHaveBeenCalled();
    });
  });

  describe('useConversationId', () => {
    it('should generate conversation ID successfully', async () => {
      const mockUserId = 'user-123';
      const mockConversationId = 'conv-123';

      mockApiClient.getCurrentUserId.mockResolvedValue(mockUserId);
      mockApiClient.generateConversationId.mockReturnValue(mockConversationId);

      const wrapper = createWrapper();
      const { result } = renderHook(
        () => useConversationId('https://api.example.com', 'assistant-123'),
        { wrapper }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockApiClient.getCurrentUserId).toHaveBeenCalled();
      expect(mockApiClient.generateConversationId).toHaveBeenCalledWith(mockUserId, 'assistant-123');
      expect(result.current.data).toBe(mockConversationId);
    });

    it('should not fetch when assistantClientId is null', () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () => useConversationId('https://api.example.com', null),
        { wrapper }
      );

      expect(result.current.isFetching).toBe(false);
      expect(mockApiClient.getCurrentUserId).not.toHaveBeenCalled();
    });
  });

  describe('error handling utilities', () => {
    it.skip('should identify retryable vs non-retryable errors', async () => {
      // Test retryable error
      const retryableError = new Error('Network error');
      mockApiClient.sendMessage.mockRejectedValue(retryableError);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSendMessage('https://api.example.com'), { wrapper });

      result.current.mutate({
        recipientId: 'assistant-123',
        content: 'Hello',
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      // Should show retry action for retryable errors
      expect(mockAddFlashItem).toHaveBeenCalled();
      const flashCall = mockAddFlashItem.mock.calls[0][0];
      expect(flashCall.action).toBeDefined();
      expect(flashCall.action.text).toBe('Retry');

      // Clear mocks for next test
      vi.clearAllMocks();

      // Test non-retryable error
      const nonRetryableError = new Error('Authentication failed');
      mockApiClient.sendMessage.mockRejectedValue(nonRetryableError);

      const { result: result2 } = renderHook(() => useSendMessage('https://api.example.com'), { wrapper });

      result2.current.mutate({
        recipientId: 'assistant-123',
        content: 'Hello',
      });

      await waitFor(() => {
        expect(result2.current.isError).toBe(true);
      });

      // Should not show retry action for non-retryable errors
      expect(mockAddFlashItem).toHaveBeenCalled();
      const flashCall2 = mockAddFlashItem.mock.calls[0][0];
      expect(flashCall2.action).toBeUndefined();
    });
  });
});