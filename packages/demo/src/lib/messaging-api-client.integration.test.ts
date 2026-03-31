/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MessagingApiClient } from './messaging-api-client';

// Mock fetch globally
global.fetch = vi.fn();

describe('MessagingApiClient Integration', () => {
  let client: MessagingApiClient;
  let mockGetAuthToken: ReturnType<typeof vi.fn>;
  let mockGetUserId: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock authentication functions that would come from react-oidc-context
    mockGetAuthToken = vi.fn().mockResolvedValue('Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...');
    mockGetUserId = vi.fn().mockResolvedValue('user-12345');
    
    client = new MessagingApiClient(
      'https://api.hotel-assistant.com/prod',
      mockGetAuthToken,
      mockGetUserId
    );
  });

  it('should handle complete message flow with authentication', async () => {
    // Mock successful send message response
    const sendResponse = {
      message: {
        messageId: 'msg-123',
        conversationId: 'user-12345#hotel-assistant',
        senderId: 'user-12345',
        recipientId: 'hotel-assistant',
        content: 'Hello, I need help with my reservation',
        status: 'sent',
        timestamp: '2024-01-01T10:00:00Z',
        createdAt: '2024-01-01T10:00:00Z',
        updatedAt: '2024-01-01T10:00:00Z',
      },
      success: true,
    };

    // Mock get messages response
    const getResponse = {
      messages: [
        {
          messageId: 'msg-123',
          conversationId: 'user-12345#hotel-assistant',
          senderId: 'user-12345',
          recipientId: 'hotel-assistant',
          content: 'Hello, I need help with my reservation',
          status: 'sent',
          timestamp: '2024-01-01T10:00:00Z',
          createdAt: '2024-01-01T10:00:00Z',
          updatedAt: '2024-01-01T10:00:00Z',
        },
        {
          messageId: 'msg-124',
          conversationId: 'user-12345#hotel-assistant',
          senderId: 'hotel-assistant',
          recipientId: 'user-12345',
          content: 'I\'d be happy to help you with your reservation. What do you need assistance with?',
          status: 'sent',
          timestamp: '2024-01-01T10:00:30Z',
          createdAt: '2024-01-01T10:00:30Z',
          updatedAt: '2024-01-01T10:00:30Z',
        },
      ],
    };

    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(sendResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(getResponse),
      });

    // Test sending a message
    const sentMessage = await client.sendMessage(
      'hotel-assistant',
      'Hello, I need help with my reservation',
      'claude-3-haiku',
      '0.7'
    );

    expect(sentMessage.success).toBe(true);
    expect(sentMessage.message.content).toBe('Hello, I need help with my reservation');
    expect(mockGetAuthToken).toHaveBeenCalledTimes(1);

    // Test retrieving messages
    const conversationId = client.generateConversationId('user-12345', 'hotel-assistant');
    expect(conversationId).toBe('user-12345#hotel-assistant');

    const messages = await client.getMessages(conversationId);

    expect(messages.success).toBe(true);
    expect(messages.messages).toHaveLength(2);
    expect(messages.messages[0].isUser).toBe(true); // User message
    expect(messages.messages[1].isUser).toBe(false); // Assistant message
    expect(mockGetAuthToken).toHaveBeenCalledTimes(2);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);

    // Verify API calls were made with correct authentication
    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.hotel-assistant.com/prod/messages',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...',
        }),
      })
    );

    expect(global.fetch).toHaveBeenCalledWith(
      'https://api.hotel-assistant.com/prod/conversations/user-12345%23hotel-assistant/messages?limit=100',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...',
        }),
      })
    );
  });

  it('should handle authentication errors gracefully', async () => {
    mockGetAuthToken.mockRejectedValueOnce(new Error('Token expired'));

    await expect(
      client.sendMessage('hotel-assistant', 'Hello')
    ).rejects.toThrow('Token expired');

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should handle API errors with proper error messages', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: () => Promise.resolve({ message: 'Insufficient permissions' }),
    });

    await expect(
      client.sendMessage('hotel-assistant', 'Hello')
    ).rejects.toThrow('Access denied. You may not have permission to perform this action.');
  });

  it('should generate correct conversation IDs for hotel assistant', () => {
    const conversationId1 = client.generateConversationId('user-123', 'hotel-assistant');
    const conversationId2 = client.generateConversationId('user-456', 'hotel-assistant-v2');
    
    expect(conversationId1).toBe('user-123#hotel-assistant');
    expect(conversationId2).toBe('user-456#hotel-assistant');
  });

  it('should handle message polling with timestamp filtering', async () => {
    const mockResponse = {
      messages: [
        {
          messageId: 'msg-new',
          conversationId: 'user-12345#hotel-assistant',
          senderId: 'hotel-assistant',
          recipientId: 'user-12345',
          content: 'New message',
          status: 'sent',
          timestamp: '2024-01-01T10:05:00Z',
          createdAt: '2024-01-01T10:05:00Z',
          updatedAt: '2024-01-01T10:05:00Z',
        },
      ],
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const since = '2024-01-01T10:00:00Z';
    const messages = await client.getMessagesSince('user-12345#hotel-assistant', since, 50);

    expect(messages.success).toBe(true);
    expect(messages.messages).toHaveLength(1);
    expect(messages.messages[0].isUser).toBe(false);

    expect(global.fetch).toHaveBeenCalledWith(
      `https://api.hotel-assistant.com/prod/conversations/user-12345%23hotel-assistant/messages?since=${encodeURIComponent(since)}&limit=50`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...',
        }),
      })
    );
  });
});