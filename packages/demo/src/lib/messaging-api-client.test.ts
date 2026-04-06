/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MessagingApiClient } from './messaging-api-client';
import type { MessageApiResponse, SendMessageResponse } from '../types';

// Mock fetch globally
global.fetch = vi.fn();

describe('MessagingApiClient', () => {
  let client: MessagingApiClient;
  let mockGetAuthToken: ReturnType<typeof vi.fn>;
  let mockGetUserId: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    
    mockGetAuthToken = vi.fn().mockResolvedValue('mock-access-token');
    mockGetUserId = vi.fn().mockResolvedValue('test-user-123');
    
    client = new MessagingApiClient(
      'https://api.example.com',
      mockGetAuthToken,
      mockGetUserId
    );
  });

  describe('constructor', () => {
    it('should create client with correct base URL', () => {
      expect(client).toBeInstanceOf(MessagingApiClient);
    });
  });

  describe('sendMessage', () => {
    it('should send message successfully with authentication token', async () => {
      const mockResponse: SendMessageResponse = {
        message: {
          messageId: 'msg-123',
          conversationId: 'conv-123',
          senderId: 'test-user-123',
          recipientId: 'hotel-assistant',
          content: 'Hello',
          status: 'sent' as any,
          timestamp: '2024-01-01T00:00:00Z',
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: '2024-01-01T00:00:00Z',
        },
        success: true,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await client.sendMessage('hotel-assistant', 'Hello');

      expect(mockGetAuthToken).toHaveBeenCalledOnce();
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.example.com/messages',
        {
          method: 'POST',
          headers: {
            Authorization: 'Bearer mock-access-token',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            recipientId: 'hotel-assistant',
            content: 'Hello',
          }),
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should include optional parameters when provided', async () => {
      const mockResponse: SendMessageResponse = {
        message: {} as MessageApiResponse,
        success: true,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      await client.sendMessage('hotel-assistant', 'Hello', 'claude-3', '0.7');

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.example.com/messages',
        expect.objectContaining({
          body: JSON.stringify({
            recipientId: 'hotel-assistant',
            content: 'Hello',
            modelId: 'claude-3',
            temperature: '0.7',
          }),
        })
      );
    });

    it('should include conversationId when provided', async () => {
      const mockResponse: SendMessageResponse = {
        message: {} as MessageApiResponse,
        success: true,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const conversationId = 'test-conversation-uuid';
      await client.sendMessage('hotel-assistant', 'Hello', undefined, undefined, conversationId);

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.example.com/messages',
        expect.objectContaining({
          body: JSON.stringify({
            recipientId: 'hotel-assistant',
            content: 'Hello',
            conversationId,
          }),
        })
      );
    });

    it('should include all optional parameters when provided', async () => {
      const mockResponse: SendMessageResponse = {
        message: {} as MessageApiResponse,
        success: true,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const conversationId = 'test-conversation-uuid';
      await client.sendMessage('hotel-assistant', 'Hello', 'claude-3', '0.7', conversationId);

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.example.com/messages',
        expect.objectContaining({
          body: JSON.stringify({
            recipientId: 'hotel-assistant',
            content: 'Hello',
            modelId: 'claude-3',
            temperature: '0.7',
            conversationId,
          }),
        })
      );
    });

    it('should handle authentication errors', async () => {
      mockGetAuthToken.mockRejectedValueOnce(new Error('Authentication failed'));

      await expect(
        client.sendMessage('hotel-assistant', 'Hello')
      ).rejects.toThrow('Authentication failed');
    });

    it('should handle API errors', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: () => Promise.resolve({ message: 'Invalid token' }),
      });

      await expect(
        client.sendMessage('hotel-assistant', 'Hello')
      ).rejects.toThrow('Authentication failed. Please sign in again.');
    });
  });

  describe('getMessages', () => {
    it('should get messages successfully with computed isUser field', async () => {
      const mockApiResponse = {
        messages: [
          {
            messageId: 'msg-1',
            conversationId: 'conv-123',
            senderId: 'test-user-123',
            recipientId: 'hotel-assistant',
            content: 'Hello',
            status: 'sent',
            timestamp: '2024-01-01T00:00:00Z',
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z',
          },
          {
            messageId: 'msg-2',
            conversationId: 'conv-123',
            senderId: 'hotel-assistant',
            recipientId: 'test-user-123',
            content: 'Hi there!',
            status: 'sent',
            timestamp: '2024-01-01T00:01:00Z',
            createdAt: '2024-01-01T00:01:00Z',
            updatedAt: '2024-01-01T00:01:00Z',
          },
        ],
        nextToken: 'next-123',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockApiResponse),
      });

      const result = await client.getMessages('conv-123');

      expect(mockGetAuthToken).toHaveBeenCalledOnce();
      expect(mockGetUserId).toHaveBeenCalledOnce();
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.example.com/conversations/conv-123/messages?limit=100',
        {
          headers: {
            Authorization: 'Bearer mock-access-token',
            'Content-Type': 'application/json',
          },
        }
      );

      expect(result.success).toBe(true);
      expect(result.messages).toHaveLength(2);
      expect(result.messages[0].isUser).toBe(true); // senderId matches current user
      expect(result.messages[1].isUser).toBe(false); // senderId is hotel-assistant
      expect(result.nextToken).toBe('next-123');
    });

    it('should handle empty messages array', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ messages: [] }),
      });

      const result = await client.getMessages('conv-123');

      expect(result.success).toBe(true);
      expect(result.messages).toHaveLength(0);
    });
  });

  describe('getMessagesSince', () => {
    it('should get messages since timestamp with proper encoding', async () => {
      const mockApiResponse = {
        messages: [],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockApiResponse),
      });

      const since = '2024-01-01T00:00:00Z';
      await client.getMessagesSince('conv-123', since, 50);

      expect(global.fetch).toHaveBeenCalledWith(
        `https://api.example.com/conversations/conv-123/messages?since=${encodeURIComponent(since)}&limit=50`,
        expect.objectContaining({
          headers: {
            Authorization: 'Bearer mock-access-token',
            'Content-Type': 'application/json',
          },
        })
      );
    });
  });

  describe('generateConversationId', () => {
    it('should generate conversation ID using utility function', () => {
      const result = client.generateConversationId('user-123', 'hotel-assistant');
      expect(result).toBe('user-123#hotel-assistant');
    });
  });

  describe('generateNewConversationId', () => {
    it('should generate a new UUID conversation ID', () => {
      // Mock crypto.randomUUID with valid UUID v4 format
      const mockUUID = '123e4567-e89b-42d3-a456-426614174000';
      const originalCrypto = global.crypto;
      global.crypto = {
        ...originalCrypto,
        randomUUID: vi.fn().mockReturnValue(mockUUID),
      } as any;

      const result = client.generateNewConversationId();
      
      expect(result).toBe(mockUUID);
      expect(global.crypto.randomUUID).toHaveBeenCalledOnce();

      // Restore original crypto
      global.crypto = originalCrypto;
    });

    it('should generate different UUIDs on multiple calls', () => {
      // Mock crypto.randomUUID to return different values (valid UUID v4 format)
      const mockUUIDs = [
        '123e4567-e89b-42d3-a456-426614174000',
        '987fcdeb-51a2-43d1-9567-123456789abc'
      ];
      let callCount = 0;
      
      const originalCrypto = global.crypto;
      global.crypto = {
        ...originalCrypto,
        randomUUID: vi.fn().mockImplementation(() => mockUUIDs[callCount++]),
      } as any;

      const uuid1 = client.generateNewConversationId();
      const uuid2 = client.generateNewConversationId();
      
      expect(uuid1).not.toBe(uuid2);
      expect(uuid1).toBe(mockUUIDs[0]);
      expect(uuid2).toBe(mockUUIDs[1]);
      expect(uuid1).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
      expect(uuid2).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);

      // Restore original crypto
      global.crypto = originalCrypto;
    });
  });

  describe('getCurrentUserId', () => {
    it('should return current user ID', async () => {
      const result = await client.getCurrentUserId();
      expect(result).toBe('test-user-123');
      expect(mockGetUserId).toHaveBeenCalledOnce();
    });
  });
});