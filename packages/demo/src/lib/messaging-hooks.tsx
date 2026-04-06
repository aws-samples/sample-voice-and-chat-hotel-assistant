/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMessagingApiClient } from './messaging-api-client';
import type { SendMessageResponse } from '../types';

/**
 * Interface for send message mutation variables
 */
export interface SendMessageVariables {
  recipientId: string;
  content: string;
  modelId?: string;
  temperature?: string;
  conversationId?: string;
}

/**
 * Utility function to determine if an error is retryable
 */
export function isRetryableError(error: Error | string): boolean {
  const errorMessage = typeof error === 'string' ? error : error.message;
  const lowerMessage = errorMessage.toLowerCase();

  // Don't retry authentication or authorization errors
  if (lowerMessage.includes('authentication') || 
      lowerMessage.includes('authorization') || 
      lowerMessage.includes('access denied') ||
      lowerMessage.includes('sign in')) {
    return false;
  }

  // Don't retry validation errors
  if (lowerMessage.includes('validation') || lowerMessage.includes('invalid')) {
    return false;
  }

  // Retry network, server, and rate limit errors
  return lowerMessage.includes('network') ||
         lowerMessage.includes('server') ||
         lowerMessage.includes('timeout') ||
         lowerMessage.includes('rate limit') ||
         lowerMessage.includes('too many requests') ||
         lowerMessage.includes('fetch') ||
         lowerMessage.includes('500') ||
         lowerMessage.includes('502') ||
         lowerMessage.includes('503') ||
         lowerMessage.includes('504');
}

/**
 * Utility function to get appropriate retry delay based on error type
 */
function getRetryDelay(error: Error | string, retryCount: number): number {
  const errorMessage = typeof error === 'string' ? error : error.message;
  const lowerMessage = errorMessage.toLowerCase();

  // Longer delay for rate limit errors
  if (lowerMessage.includes('rate limit') || lowerMessage.includes('too many requests')) {
    return 5000 * Math.pow(2, retryCount); // 5s, 10s, 20s, etc.
  }

  // Standard exponential backoff for other errors
  return 1000 * Math.pow(2, retryCount); // 1s, 2s, 4s, etc.
}

/**
 * Hook for sending messages with flash notification error handling
 * 
 * Requirements: 3.3, 3.4, 5.1, 5.4
 * - 3.3: Integrate messaging hooks with React Query and new authentication
 * - 3.4: Test messaging hooks with new authentication system
 * - 5.1: Replace error alerts with GlobalUIContext flash notification system
 * - 5.4: Implement retry functionality through flash notification actions
 */
export function useSendMessage(apiEndpoint: string) {
  const queryClient = useQueryClient();
  const apiClient = useMessagingApiClient(apiEndpoint);

  const mutation = useMutation<SendMessageResponse, Error, SendMessageVariables>({
    mutationFn: async ({ recipientId, content, modelId, temperature, conversationId }) => {
      return apiClient.sendMessage(recipientId, content, modelId, temperature, conversationId);
    },

    // Configure retry behavior based on error type
    retry: (failureCount, error) => {
      // Don't retry if we've exceeded max attempts
      if (failureCount >= 3) {
        return false;
      }
      
      // Only retry retryable errors
      return isRetryableError(error);
    },

    retryDelay: (attemptIndex, error) => {
      return getRetryDelay(error, attemptIndex);
    },

    onSuccess: (data, _variables) => {
      // Only invalidate queries on successful message send and if conversationId is present
      if (data?.message?.conversationId) {
        queryClient.invalidateQueries({ queryKey: ['messages', data.message.conversationId] });
      }
    },


  });

  return mutation;
}

/**
 * Hook for retrieving messages with automatic polling and flash notification error handling
 * 
 * Requirements: 3.3, 3.4, 5.1, 5.4
 * - 3.3: Integrate messaging hooks with React Query and new authentication
 * - 3.4: Test messaging hooks with new authentication system
 * - 5.1: Replace error alerts with GlobalUIContext flash notification system
 * - 5.4: Implement retry functionality through flash notification actions
 */
export function useMessages(
  apiEndpoint: string,
  conversationId: string | null, 
  enabled: boolean = true
) {
  const apiClient = useMessagingApiClient(apiEndpoint);

  const query = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: async () => {
      if (!conversationId) {
        throw new Error('Conversation ID is required');
      }
      return apiClient.getMessages(conversationId);
    },
    enabled: enabled && !!conversationId,
    refetchInterval: 5000, // Poll every 5 seconds
    refetchIntervalInBackground: true, // Continue polling when tab is not active
    staleTime: 0, // Always consider data stale to ensure fresh polling
    gcTime: 5 * 60 * 1000, // Keep data in cache for 5 minutes
    
    // Enhanced retry logic with error type awareness
    retry: (failureCount, error) => {
      // Don't retry if we've exceeded max attempts
      if (failureCount >= 3) {
        return false;
      }
      
      // Only retry retryable errors
      return isRetryableError(error);
    },
    
    retryDelay: (attemptIndex, error) => {
      return getRetryDelay(error, attemptIndex);
    },


  });

  return query;
}

/**
 * Hook for retrieving messages since a specific timestamp (for polling new messages)
 * 
 * This is used for more efficient polling when we only want new messages
 */
export function useMessagesSince(
  apiEndpoint: string,
  conversationId: string | null,
  since: string | null,
  enabled: boolean = true
) {
  const apiClient = useMessagingApiClient(apiEndpoint);

  return useQuery({
    queryKey: ['messages-since', conversationId, since],
    queryFn: async () => {
      if (!conversationId || !since) {
        throw new Error('Conversation ID and since timestamp are required');
      }
      return apiClient.getMessagesSince(conversationId, since);
    },
    enabled: enabled && !!conversationId && !!since,
    refetchInterval: 5000, // Poll every 5 seconds
    refetchIntervalInBackground: true,
    staleTime: 0,
    gcTime: 1 * 60 * 1000, // Shorter cache time for polling queries
    
    // Enhanced retry logic with error type awareness
    retry: (failureCount, error) => {
      // Don't retry if we've exceeded max attempts
      if (failureCount >= 3) {
        return false;
      }
      
      // Only retry retryable errors
      return isRetryableError(error);
    },
    
    retryDelay: (attemptIndex, error) => {
      return getRetryDelay(error, attemptIndex);
    },
  });
}

/**
 * Hook to generate conversation ID for current user and assistant
 */
export function useConversationId(
  apiEndpoint: string,
  assistantClientId: string | null
) {
  const apiClient = useMessagingApiClient(apiEndpoint);

  return useQuery({
    queryKey: ['conversation-id', assistantClientId],
    queryFn: async () => {
      if (!assistantClientId) {
        throw new Error('Assistant client ID is required');
      }
      const currentUserId = await apiClient.getCurrentUserId();
      return apiClient.generateConversationId(currentUserId, assistantClientId);
    },
    enabled: !!assistantClientId,
    staleTime: Infinity, // Conversation ID doesn't change for the same user/assistant pair
    gcTime: Infinity,
    
    retry: (failureCount, error) => {
      // Don't retry if we've exceeded max attempts
      if (failureCount >= 3) {
        return false;
      }
      
      // Only retry retryable errors
      return isRetryableError(error);
    },
    
    retryDelay: (attemptIndex, error) => {
      return getRetryDelay(error, attemptIndex);
    },


  });
}