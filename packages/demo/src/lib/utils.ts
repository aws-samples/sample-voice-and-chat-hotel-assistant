/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import type { Message, MessageApiResponse } from '../types';

export const getErrorMessage = (error: unknown): string => {
  let message: string;

  if (error instanceof Error) {
    message = error.message;
  } else if (error && typeof error === "object" && "message" in error) {
    message = String(error.message);
  } else if (typeof error === "string") {
    message = error;
  } else {
    message = "Unknown error";
  }

  return message;
};

// Message utility functions

/**
 * Convert MessageApiResponse to Message by computing the isUser field
 * @param messageData - Raw message data from API
 * @param currentUserId - Current user's ID to determine if message is from user
 * @returns Message with computed isUser field
 */
export const createMessageFromApiResponse = (
  messageData: MessageApiResponse,
  currentUserId: string
): Message => {
  return {
    ...messageData,
    isUser: messageData.senderId === currentUserId,
  };
};

/**
 * Convert array of MessageApiResponse to Message array
 * @param messagesData - Array of raw message data from API
 * @param currentUserId - Current user's ID to determine if messages are from user
 * @returns Array of Messages with computed isUser fields
 */
export const createMessagesFromApiResponse = (
  messagesData: MessageApiResponse[],
  currentUserId: string
): Message[] => {
  return messagesData.map(messageData => 
    createMessageFromApiResponse(messageData, currentUserId)
  );
};

/**
 * Generate conversation ID from user ID and assistant client ID
 * Uses lexicographic sorting for consistent conversation ID format
 * @param userId - Current user's ID
 * @param assistantClientId - Hotel assistant client ID
 * @returns Formatted conversation ID
 */
export const generateConversationId = (
  userId: string,
  assistantClientId: string
): string => {
  if (!userId || !userId.trim()) {
    throw new Error('User ID cannot be empty');
  }
  if (!assistantClientId || !assistantClientId.trim()) {
    throw new Error('Assistant client ID cannot be empty');
  }

  const trimmedUserId = userId.trim();
  const trimmedAssistantId = assistantClientId.trim();

  // For conversations with hotel-assistant, always use userId#hotel-assistant format
  if (trimmedAssistantId === 'hotel-assistant' || trimmedAssistantId.startsWith('hotel-assistant-')) {
    return `${trimmedUserId}#hotel-assistant`;
  }

  // For other conversations, use lexicographic ordering for consistency
  const participants = [trimmedUserId, trimmedAssistantId].sort();
  return `${participants[0]}#${participants[1]}`;
};