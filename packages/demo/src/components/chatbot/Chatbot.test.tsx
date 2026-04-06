/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Chatbot } from './Chatbot';
import * as messagingHooks from '../../lib/messaging-hooks';
import * as messagingApiClient from '../../lib/messaging-api-client';
import { vi } from 'vitest';

// Mock the hooks and dependencies
vi.mock('../../lib/messaging-hooks');
vi.mock('../../lib/messaging-api-client');
vi.mock('../RuntimeConfig', () => {
  return {
    default: ({ children }: { children: React.ReactNode }) =>
      React.createElement('div', {}, children),
    RuntimeConfigContext: React.createContext(null),
  };
});
vi.mock('../../hooks/useRuntimeConfig', () => ({
  useRuntimeConfig: () => ({
    applicationName: 'Test App',
    hotelAssistantClientId: 'test-client',
    messagingApiEndpoint: 'https://api.test.com',
    cognitoProps: {
      region: 'us-east-1',
      userPoolId: 'test-pool',
      userPoolWebClientId: 'test-client',
    },
  }),
}));
vi.mock('../GlobalUIContextProvider', () => {
  return {
    default: ({ children }: { children: React.ReactNode }) =>
      React.createElement('div', {}, children),
    GlobalUIContextProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement('div', {}, children),
    GlobalUIContext: React.createContext({
      flashItems: [],
      setFlashItems: () => {},
      addFlashItem: () => {},
      toolsOpen: false,
      setToolsOpen: () => {},
      helpPanelTopic: 'default',
      setHelpPanelTopic: () => {},
      makeHelpPanelHandler: () => {},
      appLayoutRef: { current: null },
    }),
  };
});
vi.mock('@tanstack/react-query', () => {
  return {
    QueryClient: vi.fn(),
    QueryClientProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement('div', {}, children),
    useQueryClient: () => ({}),
  };
});

// Mock the useGlobalUIContext hook
const mockAddFlashItem = vi.fn();
vi.mock('../../hooks/useGlobalUIContext', () => ({
  useGlobalUIContext: () => ({
    addFlashItem: mockAddFlashItem,
  }),
}));

const mockMessagingHooks = messagingHooks as any;
const mockMessagingApiClient = messagingApiClient as any;

describe('Chatbot', () => {
  let mockSendMessage: any;

  beforeEach(() => {
    vi.clearAllMocks();
    mockAddFlashItem.mockClear();

    // Mock API client
    const mockApiClient = {
      generateNewConversationId: vi.fn(() => 'new-uuid-5678'),
    };
    mockMessagingApiClient.useMessagingApiClient.mockReturnValue(mockApiClient);

    // Mock hooks with simple defaults
    mockSendMessage = vi.fn();
    mockMessagingHooks.useSendMessage.mockReturnValue({
      mutateAsync: mockSendMessage,
      isPending: false,
    });

    mockMessagingHooks.useMessages.mockReturnValue({
      data: { messages: [] },
      isLoading: false,
    });

    mockMessagingHooks.useConversationId.mockReturnValue({
      data: 'test-conversation-id',
      isLoading: false,
    });
  });

  it('should render basic chatbot interface', () => {
    render(<Chatbot />);

    expect(screen.getByText('Hotel Assistant Chat')).toBeInTheDocument();
    expect(screen.getByText('New Session')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('should handle message sending', () => {
    render(<Chatbot />);

    const input = screen.getByRole('textbox');
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    expect(mockSendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        content: 'Hello',
        conversationId: 'test-conversation-id',
      })
    );
  });

  it('should handle new session', () => {
    render(<Chatbot />);

    const newSessionButton = screen.getByRole('button', { name: /new session/i });
    fireEvent.click(newSessionButton);

    // Verify that the flash notification was added
    expect(mockAddFlashItem).toHaveBeenCalledWith({
      type: 'success',
      content: 'New conversation started',
      dismissible: true,
    });
  });

  it('should not send empty messages', () => {
    render(<Chatbot />);

    const input = screen.getByRole('textbox');
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: '   ' } }); // Only whitespace
    fireEvent.click(sendButton);

    expect(mockSendMessage).not.toHaveBeenCalled();
  });
});
