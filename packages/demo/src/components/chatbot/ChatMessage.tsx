/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { Box, Icon, SpaceBetween, Spinner } from '@cloudscape-design/components';
import { MarkdownContent } from '../common/MarkdownContent';
import { MessageStatusIcon } from './MessageStatusIcon';
import { MessageStatus } from '../../types';

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  timestamp: Date;
  isError?: boolean;
  isLoading?: boolean;
  status?: MessageStatus;
}

export function ChatMessage({
  message,
  isUser,
  timestamp,
  isError: _isError,
  isLoading,
  status,
}: ChatMessageProps) {
  return (
    <Box padding="s">
      {isUser ? (
        <SpaceBetween direction="vertical" size="xs">
          {/* User message with timestamp on the right */}
          <Box textAlign="right">
            <Box display="inline-block" textAlign="left">
              <SpaceBetween direction="vertical" size="xs">
                {/* Header with sender and timestamp */}
                <Box fontSize="body-s" color="text-status-inactive" textAlign="right">
                  You • {timestamp.toLocaleTimeString()}
                </Box>
                <SpaceBetween direction="horizontal" size="s" alignItems="start">
                  <Box padding="m" float="right">
                    <SpaceBetween direction="vertical" size="xs">
                      <MarkdownContent>{message}</MarkdownContent>
                      {status && (
                        <Box textAlign="right">
                          <MessageStatusIcon status={status} />
                        </Box>
                      )}
                    </SpaceBetween>
                  </Box>
                  <Icon name="user-profile" size="large" ariaLabel="User" />
                </SpaceBetween>
              </SpaceBetween>
            </Box>
          </Box>
        </SpaceBetween>
      ) : (
        <SpaceBetween direction="vertical" size="xs">
          {/* Header with sender and timestamp for assistant */}
          <Box fontSize="body-s" color="text-status-inactive">
            Hotel Assistant • {timestamp.toLocaleTimeString()}
          </Box>
          {/* Assistant message content */}
          <SpaceBetween direction="horizontal" size="s" alignItems="start">
            <Icon name="gen-ai" size="large" ariaLabel="AI Assistant" />
            <Box padding="m">
              {isLoading ? (
                <SpaceBetween direction="horizontal" size="s" alignItems="center">
                  <Spinner size="normal" />
                  <MarkdownContent>{message}</MarkdownContent>
                </SpaceBetween>
              ) : (
                <MarkdownContent>{message}</MarkdownContent>
              )}
            </Box>
          </SpaceBetween>
        </SpaceBetween>
      )}
    </Box>
  );
}
