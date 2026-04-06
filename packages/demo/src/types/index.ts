/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

// Runtime Configuration Types
export interface RuntimeConfig {
  cognitoProps: {
    userPoolId: string;
    userPoolWebClientId: string;
    region: string;
  };
  messagingApiEndpoint: string;
  hotelAssistantClientId: string;
  applicationName: string;
  logo?: string;
}

// Messaging API Types
export interface Message {
  messageId: string;
  conversationId: string;
  senderId: string;
  recipientId: string;
  content: string;
  status: MessageStatus;
  timestamp: string;
  createdAt: string;
  updatedAt: string;
  isUser: boolean;
}

export enum MessageStatus {
  SENT = 'sent',
  DELIVERED = 'delivered',
  READ = 'read',
  FAILED = 'failed',
  WARNING = 'warning',
  DELETED = 'deleted',
}

export interface MessageApiResponse {
  messageId: string;
  conversationId: string;
  senderId: string;
  recipientId: string;
  content: string;
  status: MessageStatus;
  timestamp: string;
  createdAt: string;
  updatedAt: string;
}

export interface SendMessageRequest {
  recipientId: string;
  content: string;
  conversationId?: string;
  modelId?: string;
  temperature?: string;
}

export interface SendMessageResponse {
  message: MessageApiResponse;
  success: boolean;
  error?: string;
}

export interface GetMessagesResponse {
  messages: Message[];
  success: boolean;
  error?: string;
  nextToken?: string;
}

export interface ConversationIdResponse {
  conversationId: string;
  success: boolean;
  error?: string;
}

// Chatbot Configuration Types
export interface ChatbotConfig {
  awsRegion: string;
  messagingApiEndpoint: string;
  hotelAssistantClientId: string;
}

// UI Context Types
export interface FlashItem {
  id?: string;
  type: 'success' | 'error' | 'warning' | 'info';
  content: string;
  dismissible?: boolean;
  action?: {
    text: string;
    onClick: () => void;
  };
}

// Global declarations for Vite defines
declare global {
  const __APP_NAME__: string;
  const __APP_VERSION__: string;
}

export {};
