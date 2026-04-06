/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { useAuth } from 'react-oidc-context';
import type { 
  MessageApiResponse, 
  SendMessageRequest, 
  SendMessageResponse, 
  GetMessagesResponse
} from '../types';
import { createMessagesFromApiResponse, generateConversationId } from './utils';

/**
 * Client for communicating with the messaging backend API
 * Updated to use react-oidc-context instead of AWS Amplify
 */
export class MessagingApiClient {
  private baseUrl: string;
  private getAuthToken: () => Promise<string>;
  private getUserId: () => Promise<string>;

  constructor(
    apiEndpoint: string,
    getAuthToken: () => Promise<string>,
    getUserId: () => Promise<string>
  ) {
    this.baseUrl = `${apiEndpoint}`;
    this.getAuthToken = getAuthToken;
    this.getUserId = getUserId;
  }

  /**
   * Generate conversation ID using lexicographic sorting
   */
  public generateConversationId(
    userId: string,
    assistantClientId: string
  ): string {
    return generateConversationId(userId, assistantClientId);
  }

  /**
   * Generate a new UUID for conversation ID
   */
  public generateNewConversationId(): string {
    return crypto.randomUUID();
  }

  /**
   * Handle API response errors with authentication-specific error handling
   */
  private async handleApiError(response: Response): Promise<never> {
    const status = response.status;
    const statusText = response.statusText;

    // Handle authentication errors specifically
    if (status === 401) {
      throw new Error('Authentication failed. Please sign in again.');
    }
    
    if (status === 403) {
      throw new Error('Access denied. You may not have permission to perform this action.');
    }

    // Handle other common errors
    if (status >= 500) {
      throw new Error('Server error. Please try again later.');
    }

    if (status === 429) {
      throw new Error('Too many requests. Please wait a moment and try again.');
    }

    // Try to get error details from response body
    try {
      const errorData = await response.json();
      const errorMessage = errorData.message || errorData.error || statusText;
      throw new Error(`API Error: ${errorMessage}`);
    } catch {
      // If we can't parse the error response, use the status
      throw new Error(`API Error: ${status} ${statusText}`);
    }
  }

  /**
   * Send a message to the messaging backend
   */
  async sendMessage(
    recipientId: string,
    content: string,
    modelId?: string,
    temperature?: string,
    conversationId?: string
  ): Promise<SendMessageResponse> {
    try {
      const token = await this.getAuthToken();

      const requestBody: SendMessageRequest = {
        recipientId,
        content,
        ...(modelId && { modelId }),
        ...(temperature && { temperature }),
        ...(conversationId && { conversationId }),
      };

      const response = await fetch(`${this.baseUrl}/messages`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        await this.handleApiError(response);
      }

      return response.json();
    } catch (error) {
      // Re-throw authentication and API errors as-is
      if (error instanceof Error) {
        throw error;
      }
      // Handle unexpected errors
      throw new Error('Failed to send message. Please try again.');
    }
  }

  /**
   * Get messages for a conversation
   */
  async getMessages(conversationId: string, limit: number = 100): Promise<GetMessagesResponse> {
    try {
      const token = await this.getAuthToken();
      const encodedId = encodeURIComponent(conversationId);

      const response = await fetch(
        `${this.baseUrl}/conversations/${encodedId}/messages?limit=${limit}`,
        {
          headers: { 
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        await this.handleApiError(response);
      }

      const data = await response.json();
      
      // Convert API response to Message objects with computed isUser field
      const currentUserId = await this.getUserId();
      const messagesApiData: MessageApiResponse[] = data.messages || [];
      const messages = createMessagesFromApiResponse(messagesApiData, currentUserId);

      return {
        messages,
        success: true,
        nextToken: data.nextToken,
      };
    } catch (error) {
      // Re-throw authentication and API errors as-is
      if (error instanceof Error) {
        throw error;
      }
      // Handle unexpected errors
      throw new Error('Failed to retrieve messages. Please try again.');
    }
  }

  /**
   * Get messages with timestamp filtering
   */
  async getMessagesSince(
    conversationId: string,
    since: string,
    limit: number = 100
  ): Promise<GetMessagesResponse> {
    try {
      const token = await this.getAuthToken();
      const encodedId = encodeURIComponent(conversationId);

      const response = await fetch(
        `${this.baseUrl}/conversations/${encodedId}/messages?since=${encodeURIComponent(since)}&limit=${limit}`,
        {
          headers: { 
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        await this.handleApiError(response);
      }

      const data = await response.json();
      
      // Convert API response to Message objects with computed isUser field
      const currentUserId = await this.getUserId();
      const messagesApiData: MessageApiResponse[] = data.messages || [];
      const messages = createMessagesFromApiResponse(messagesApiData, currentUserId);

      return {
        messages,
        success: true,
        nextToken: data.nextToken,
      };
    } catch (error) {
      // Re-throw authentication and API errors as-is
      if (error instanceof Error) {
        throw error;
      }
      // Handle unexpected errors
      throw new Error('Failed to retrieve messages. Please try again.');
    }
  }

  /**
   * Get current user ID for conversation ID generation
   */
  async getCurrentUserId(): Promise<string> {
    return this.getUserId();
  }
}

/**
 * Hook to create a MessagingApiClient instance with react-oidc-context authentication
 */
export const useMessagingApiClient = (apiEndpoint: string): MessagingApiClient => {
  const auth = useAuth();

  const getAuthToken = async (): Promise<string> => {
    try {
      if (!auth.user?.access_token) {
        throw new Error('No authentication token available. Please sign in again.');
      }

      // Validate that the token has the required scope for messaging
      const scopes = auth.user.scope?.split(' ') || [];
      
      if (!scopes.includes('chatbot-messaging/write')) {
        throw new Error('Insufficient permissions. Missing chatbot-messaging/write scope.');
      }

      return auth.user.access_token;
    } catch (error) {
      // Handle authentication errors gracefully
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Authentication failed. Please sign in again.');
    }
  };

  const getUserId = async (): Promise<string> => {
    try {
      const userId = auth.user?.profile?.['cognito:username'];
      
      if (!userId) {
        throw new Error('No user ID available. Please sign in again.');
      }
      
      return userId as string;
    } catch (error) {
      // Handle authentication errors gracefully
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Failed to get user information. Please sign in again.');
    }
  };

  return new MessagingApiClient(apiEndpoint, getAuthToken, getUserId);
};