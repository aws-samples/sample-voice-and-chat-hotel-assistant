/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import { ChatMessage } from './ChatMessage';
import { MessageStatus } from '../../types';

describe('ChatMessage', () => {
  const mockTimestamp = new Date('2023-01-01T12:00:00Z');

  it('should render user message with correct styling and status', async () => {
    render(
      <ChatMessage
        message="Hello, this is a user message"
        isUser={true}
        timestamp={mockTimestamp}
        status={MessageStatus.SENT}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Hello, this is a user message')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('User')).toBeInTheDocument();
    expect(screen.getByLabelText('Message sent')).toBeInTheDocument();
    expect(screen.getByText(/You •/)).toBeInTheDocument();
  });

  it('should render assistant message with correct styling', async () => {
    render(
      <ChatMessage
        message="Hello, this is an assistant message"
        isUser={false}
        timestamp={mockTimestamp}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Hello, this is an assistant message')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('AI Assistant')).toBeInTheDocument();
    expect(screen.getByText(/Hotel Assistant •/)).toBeInTheDocument();
  });

  it('should render loading state for assistant message', async () => {
    render(
      <ChatMessage message="Loading..." isUser={false} timestamp={mockTimestamp} isLoading={true} />
    );

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
    // Verify spinner is rendered (Cloudscape Spinner uses span with size class)
    expect(document.querySelector('[class*="spinner"]') ?? document.querySelector('[class*="size-normal"]')).toBeInTheDocument();
  });

  it('should render error state for assistant message', async () => {
    render(
      <ChatMessage
        message="Error occurred"
        isUser={false}
        timestamp={mockTimestamp}
        isError={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Error occurred')).toBeInTheDocument();
    });
    // Error styling should be applied via CSS classes
  });

  it('should render different message statuses correctly', async () => {
    const { rerender } = render(
      <ChatMessage
        message="Test message"
        isUser={true}
        timestamp={mockTimestamp}
        status={MessageStatus.DELIVERED}
      />
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Message delivered')).toBeInTheDocument();
    });

    await act(async () => {
      rerender(
        <ChatMessage
          message="Test message"
          isUser={true}
          timestamp={mockTimestamp}
          status={MessageStatus.READ}
        />
      );
    });

    await waitFor(() => {
      expect(screen.getByLabelText('Message read')).toBeInTheDocument();
    });

    await act(async () => {
      rerender(
        <ChatMessage
          message="Test message"
          isUser={true}
          timestamp={mockTimestamp}
          status={MessageStatus.FAILED}
        />
      );
    });

    await waitFor(() => {
      expect(screen.getByLabelText('Message failed')).toBeInTheDocument();
    });
  });

  it('should not render status for assistant messages', async () => {
    await act(async () => {
      render(
        <ChatMessage
          message="Assistant message"
          isUser={false}
          timestamp={mockTimestamp}
          status={MessageStatus.SENT}
        />
      );
    });

    await waitFor(() => {
      expect(screen.getByText('Assistant message')).toBeInTheDocument();
    });

    expect(screen.queryByLabelText('Message sent')).not.toBeInTheDocument();
  });
});
