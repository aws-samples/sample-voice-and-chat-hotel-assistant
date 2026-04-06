/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { renderHook, act } from '@testing-library/react';
import { useState, useCallback } from 'react';
import { vi } from 'vitest';

// Mock crypto.randomUUID
Object.defineProperty(global, 'crypto', {
  value: {
    randomUUID: vi.fn(() => 'mock-uuid-1234'),
  },
});

/**
 * Test the conversation state management logic in isolation
 * This tests the core state management patterns used in the Chatbot component
 */
describe('Conversation State Management Logic', () => {
  // Mock messaging client
  const mockMessagingClient = {
    generateNewConversationId: vi.fn(() => 'new-uuid-5678'),
    sendMessage: vi.fn(),
  };

  // Mock flash message function
  const mockAddFlashMessage = vi.fn();

  // Hook that simulates the conversation state management logic from Chatbot component
  const useConversationStateManagement = () => {
    const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);

    const handleNewSession = useCallback(() => {
      // Generate new conversation ID
      const newConversationId = mockMessagingClient.generateNewConversationId();

      // Set new conversation ID
      setCurrentConversationId(newConversationId);

      // Show success flash message
      mockAddFlashMessage({
        type: 'success',
        content: 'New conversation started',
        dismissible: true,
      });
    }, []);

    const handleSendMessage = useCallback(
      async (messageText: string, fallbackConversationId: string) => {
        if (!messageText.trim()) {
          return;
        }

        // Use current conversation ID if available, otherwise use fallback
        const conversationIdToUse = currentConversationId || fallbackConversationId;

        if (!conversationIdToUse) {
          return;
        }

        try {
          const response = await mockMessagingClient.sendMessage({
            recipientId: 'hotel-assistant',
            content: messageText,
            modelId: 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
            temperature: '0.2',
            conversationId: conversationIdToUse,
          });

          // Update conversation ID state from API response
          if (response?.message?.conversationId) {
            setCurrentConversationId(response.message.conversationId);
          }

          return response;
        } catch (error) {
          console.error('Failed to send message:', error);
          throw error;
        }
      },
      [currentConversationId]
    );

    return {
      currentConversationId,
      handleNewSession,
      handleSendMessage,
    };
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Current Conversation ID State', () => {
    it('should initialize with null currentConversationId', () => {
      const { result } = renderHook(() => useConversationStateManagement());

      expect(result.current.currentConversationId).toBeNull();
    });

    it('should use fallback conversation ID when currentConversationId is null', async () => {
      const fallbackConversationId = 'fallback-conversation-id';

      mockMessagingClient.sendMessage.mockResolvedValue({
        message: {
          messageId: 'msg-123',
          conversationId: fallbackConversationId,
          content: 'Test response',
        },
        success: true,
      });

      const { result } = renderHook(() => useConversationStateManagement());

      await act(async () => {
        await result.current.handleSendMessage('Hello', fallbackConversationId);
      });

      expect(mockMessagingClient.sendMessage).toHaveBeenCalledWith({
        recipientId: 'hotel-assistant',
        content: 'Hello',
        modelId: 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
        temperature: '0.2',
        conversationId: fallbackConversationId,
      });
    });

    it('should use currentConversationId when available', async () => {
      const newConversationId = 'current-conversation-id';

      mockMessagingClient.sendMessage.mockResolvedValue({
        message: {
          messageId: 'msg-123',
          conversationId: newConversationId,
          content: 'Test response',
        },
        success: true,
      });

      const { result } = renderHook(() => useConversationStateManagement());

      // Start new session to set currentConversationId
      act(() => {
        result.current.handleNewSession();
      });

      expect(result.current.currentConversationId).toBe('new-uuid-5678');

      // Send message should use the current conversation ID
      await act(async () => {
        await result.current.handleSendMessage('Hello', 'fallback-id');
      });

      expect(mockMessagingClient.sendMessage).toHaveBeenCalledWith({
        recipientId: 'hotel-assistant',
        content: 'Hello',
        modelId: 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
        temperature: '0.2',
        conversationId: 'new-uuid-5678',
      });
    });
  });

  describe('Conversation ID Updates from API Response', () => {
    it('should update currentConversationId from API response', async () => {
      const apiResponseConversationId = 'api-returned-conversation-id';

      mockMessagingClient.sendMessage.mockResolvedValue({
        message: {
          messageId: 'msg-123',
          conversationId: apiResponseConversationId,
          content: 'Test response',
        },
        success: true,
      });

      const { result } = renderHook(() => useConversationStateManagement());

      // Send first message
      await act(async () => {
        await result.current.handleSendMessage('First message', 'fallback-id');
      });

      // Conversation ID should be updated from API response
      expect(result.current.currentConversationId).toBe(apiResponseConversationId);

      // Send second message - should use the API-returned conversation ID
      mockMessagingClient.sendMessage.mockClear();
      mockMessagingClient.sendMessage.mockResolvedValue({
        message: {
          messageId: 'msg-456',
          conversationId: apiResponseConversationId,
          content: 'Second response',
        },
        success: true,
      });

      await act(async () => {
        await result.current.handleSendMessage('Second message', 'fallback-id');
      });

      expect(mockMessagingClient.sendMessage).toHaveBeenCalledWith({
        recipientId: 'hotel-assistant',
        content: 'Second message',
        modelId: 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
        temperature: '0.2',
        conversationId: apiResponseConversationId,
      });
    });
  });

  describe('New Session Functionality', () => {
    it('should generate new conversation ID when starting new session', () => {
      const { result } = renderHook(() => useConversationStateManagement());

      act(() => {
        result.current.handleNewSession();
      });

      expect(mockMessagingClient.generateNewConversationId).toHaveBeenCalled();
      expect(result.current.currentConversationId).toBe('new-uuid-5678');
    });

    it('should show success flash message when starting new session', () => {
      const { result } = renderHook(() => useConversationStateManagement());

      act(() => {
        result.current.handleNewSession();
      });

      expect(mockAddFlashMessage).toHaveBeenCalledWith({
        type: 'success',
        content: 'New conversation started',
        dismissible: true,
      });
    });

    it('should reset conversation state after new session', async () => {
      const originalConversationId = 'original-conversation-id';
      const newConversationId = 'new-session-conversation-id';

      // First message response
      mockMessagingClient.sendMessage.mockResolvedValueOnce({
        message: {
          messageId: 'msg-123',
          conversationId: originalConversationId,
          content: 'Original response',
        },
        success: true,
      });

      const { result } = renderHook(() => useConversationStateManagement());

      // Send first message
      await act(async () => {
        await result.current.handleSendMessage('First message', 'fallback-id');
      });

      expect(result.current.currentConversationId).toBe(originalConversationId);

      // Start new session
      mockMessagingClient.generateNewConversationId.mockReturnValue(newConversationId);

      act(() => {
        result.current.handleNewSession();
      });

      expect(result.current.currentConversationId).toBe(newConversationId);

      // New message response after session reset
      mockMessagingClient.sendMessage.mockResolvedValueOnce({
        message: {
          messageId: 'msg-456',
          conversationId: newConversationId,
          content: 'New session response',
        },
        success: true,
      });

      // Send message after new session
      await act(async () => {
        await result.current.handleSendMessage('New session message', 'fallback-id');
      });

      expect(mockMessagingClient.sendMessage).toHaveBeenCalledWith({
        recipientId: 'hotel-assistant',
        content: 'New session message',
        modelId: 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
        temperature: '0.2',
        conversationId: newConversationId,
      });
    });
  });

  describe('Message Flow with Conversation ID', () => {
    it('should pass conversation ID to all sendMessage calls', async () => {
      const conversationId = 'test-conversation-id';

      mockMessagingClient.sendMessage.mockResolvedValue({
        message: {
          messageId: 'msg-123',
          conversationId,
          content: 'Test response',
        },
        success: true,
      });

      const { result } = renderHook(() => useConversationStateManagement());

      // Send multiple messages
      const messages = ['First message', 'Second message', 'Third message'];

      for (const message of messages) {
        await act(async () => {
          await result.current.handleSendMessage(message, conversationId);
        });

        expect(mockMessagingClient.sendMessage).toHaveBeenCalledWith(
          expect.objectContaining({
            content: message,
            conversationId: expect.any(String),
          })
        );
      }

      expect(mockMessagingClient.sendMessage).toHaveBeenCalledTimes(3);
    });

    it('should not send message if no conversation ID is available', async () => {
      const { result } = renderHook(() => useConversationStateManagement());

      await act(async () => {
        await result.current.handleSendMessage('Hello', ''); // Empty fallback
      });

      // Should not call sendMessage if no conversation ID
      expect(mockMessagingClient.sendMessage).not.toHaveBeenCalled();
    });

    it('should handle empty message gracefully', async () => {
      const { result } = renderHook(() => useConversationStateManagement());

      await act(async () => {
        await result.current.handleSendMessage('   ', 'fallback-id'); // Only whitespace
      });

      // Should not call sendMessage for empty/whitespace-only messages
      expect(mockMessagingClient.sendMessage).not.toHaveBeenCalled();
    });
  });

  describe('State Updates and Message Flow', () => {
    it('should maintain conversation state across multiple messages', async () => {
      const conversationId = 'persistent-conversation-id';

      mockMessagingClient.sendMessage.mockResolvedValue({
        message: {
          messageId: 'msg-123',
          conversationId,
          content: 'Test response',
        },
        success: true,
      });

      const { result } = renderHook(() => useConversationStateManagement());

      // Send first message
      await act(async () => {
        await result.current.handleSendMessage('First message', 'fallback-id');
      });

      expect(result.current.currentConversationId).toBe(conversationId);

      // Send second message - should use the same conversation ID
      mockMessagingClient.sendMessage.mockClear();

      await act(async () => {
        await result.current.handleSendMessage('Second message', 'fallback-id');
      });

      expect(mockMessagingClient.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          conversationId,
        })
      );
    });
  });
});
