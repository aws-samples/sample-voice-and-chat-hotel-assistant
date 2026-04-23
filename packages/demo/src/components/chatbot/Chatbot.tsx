/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { Container, Header, SpaceBetween, Alert } from '@cloudscape-design/components';
import { useMemo, useRef, useState, useCallback } from 'react';
import { useSendMessage, useMessages, useConversationId } from '../../lib/messaging-hooks';
import { useChatbotConfig } from '../../lib/chatbot-config';
import { useGlobalUIContext } from '../../hooks/useGlobalUIContext';
import { useMessagingApiClient } from '../../lib/messaging-api-client';
import { MessageStatus, type Message } from '../../types';
import { ChatInput, type ChatInputRef } from './ChatInput';
import { ChatMessage } from './ChatMessage';
import { MessageSkeleton } from './MessageSkeleton';
import { SubtlePollingIndicator } from './PollingIndicator';
import { NewSessionButton } from './NewSessionButton';

const initialMessage: Message = {
  messageId: crypto.randomUUID(),
  conversationId: '', // Will be set when conversation ID is available
  senderId: 'hotel-assistant',
  recipientId: '', // Will be set when user ID is available
  content:
    '¡Hola! Soy su asistente virtual de hoteles. Estoy aquí para ayudarle con cualquier consulta. ¿En qué puedo asistirle hoy?',
  status: MessageStatus.DELIVERED,
  timestamp: new Date().toISOString(),
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  isUser: false,
};

export function Chatbot() {
  const [modelId, setModelId] = useState('us.anthropic.claude-3-5-haiku-20241022-v1:0');
  const [temperature, setTemperature] = useState('0.2');
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const chatInputRef = useRef<ChatInputRef>(null);

  // Get configuration using the hook
  const config = useChatbotConfig();
  const virtualAssistantClientId = config.virtualAssistantClientId || 'hotel-assistant';
  const apiEndpoint = config.messagingApiEndpoint;

  // Flash notification system
  const { addFlashItem } = useGlobalUIContext();

  // Get messaging API client for generating new conversation IDs
  const messagingClient = useMessagingApiClient(apiEndpoint);

  // Generate conversation ID using current user and hotel assistant (fallback)
  const { data: fallbackConversationId, isLoading: isConversationIdLoading } = useConversationId(
    apiEndpoint,
    virtualAssistantClientId
  );

  // Use current conversation ID or fallback to generated one
  const conversationId = currentConversationId || fallbackConversationId;

  // Get messages for the conversation
  const {
    data: messagesResponse,
    isLoading: isMessagesLoading,
    isFetching: isMessagesFetching,
  } = useMessages(apiEndpoint, conversationId || null, !!conversationId);

  // Send message mutation
  const sendMessageMutation = useSendMessage(apiEndpoint);

  // Combine messages from API with initial message if no messages exist
  const messages = useMemo(() => {
    const response = messagesResponse as { messages?: Message[] } | undefined;

    // If we have a current conversation ID that's different from the fallback,
    // and we don't have messages yet, show only the initial message
    if (
      currentConversationId &&
      currentConversationId !== fallbackConversationId &&
      !response?.messages?.length
    ) {
      return [initialMessage];
    }

    return response?.messages?.length ? response.messages : [initialMessage];
  }, [messagesResponse, currentConversationId, fallbackConversationId]);

  const isLoading = sendMessageMutation.isPending;

  // Error handling is now done in the hooks themselves with flash notifications

  const handleSendMessage = async (messageText: string) => {
    if (!messageText.trim()) {
      return;
    }

    // Use current conversation ID if available, otherwise use fallback
    const conversationIdToUse = currentConversationId || conversationId;

    if (!conversationIdToUse) {
      // This error will be handled by the useConversationId hook
      return;
    }

    try {
      const response = await sendMessageMutation.mutateAsync({
        recipientId: virtualAssistantClientId,
        content: messageText,
        modelId,
        temperature,
        conversationId: conversationIdToUse,
      });

      // Update conversation ID state from API response for first message
      // This ensures we always have the server-confirmed conversation ID
      if (response?.message?.conversationId) {
        setCurrentConversationId(response.message.conversationId);
      }

      // Focus back to input after successful send
      chatInputRef.current?.focus();
    } catch (error) {
      // Error handling is done in the useSendMessage hook
      console.error('Failed to send message:', error);
    }
  };

  const handleNewSession = useCallback(() => {
    // Generate new conversation ID
    const newConversationId = messagingClient.generateNewConversationId();

    // Set new conversation ID
    setCurrentConversationId(newConversationId);

    // Show success flash message
    addFlashItem({
      type: 'success',
      content: 'New conversation started',
      dismissible: true,
    });
  }, [messagingClient, addFlashItem]);

  const handleModelChange = (newModelId: string) => {
    setModelId(newModelId);
  };

  const handleTemperatureChange = (newTemperature: string) => {
    setTemperature(newTemperature);
  };

  // Show loading state while conversation ID is being generated
  if (isConversationIdLoading) {
    return (
      <Container header={<Header variant="h2">Hotel Assistant Chat</Header>}>
        <SpaceBetween direction="vertical" size="l">
          <Container>
            <SpaceBetween direction="vertical" size="s">
              <Alert type="info">Initializing chat...</Alert>
            </SpaceBetween>
          </Container>
        </SpaceBetween>
      </Container>
    );
  }

  // Don't show error state UI since flash notifications handle errors
  // The error is already handled in useEffect above with flash notifications

  return (
    <Container
      header={
        <Header
          variant="h2"
          actions={
            <NewSessionButton onNewSession={handleNewSession} disabled={isConversationIdLoading} />
          }
        >
          Hotel Assistant Chat
        </Header>
      }
    >
      {/* Subtle polling indicator - positioned absolutely to avoid layout disruption */}
      <SubtlePollingIndicator isPolling={isMessagesFetching && !isMessagesLoading} />

      <SpaceBetween direction="vertical" size="l">
        <Container>
          <SpaceBetween direction="vertical" size="s">
            {isMessagesLoading && messages.length === 1 ? (
              // Show skeleton loading for initial message load
              <>
                <MessageSkeleton isUser={false} />
                <MessageSkeleton isUser={true} />
                <MessageSkeleton isUser={false} />
              </>
            ) : (
              messages.map((msg: Message) => (
                <ChatMessage
                  key={msg.messageId}
                  message={msg.content}
                  isUser={msg.isUser}
                  timestamp={new Date(msg.timestamp)}
                  status={msg.status}
                  isError={msg.status === MessageStatus.FAILED}
                />
              ))
            )}
            {isLoading && <MessageSkeleton isUser={false} />}
          </SpaceBetween>
        </Container>

        {/* Message input with model selection and temperature controls */}
        <ChatInput
          ref={chatInputRef}
          onSendMessage={handleSendMessage}
          disabled={isConversationIdLoading}
          loading={isLoading}
          modelId={modelId}
          temperature={temperature}
          onModelChange={handleModelChange}
          onTemperatureChange={handleTemperatureChange}
        />
      </SpaceBetween>
    </Container>
  );
}
