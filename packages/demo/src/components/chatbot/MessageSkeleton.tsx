/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { Box, Icon, SpaceBetween } from '@cloudscape-design/components';

interface MessageSkeletonProps {
  isUser?: boolean;
}

export function MessageSkeleton({ isUser = false }: MessageSkeletonProps) {
  if (isUser) {
    return (
      <Box padding="s" textAlign="right">
        <Box display="inline-block" textAlign="left">
          <SpaceBetween direction="horizontal" size="s" alignItems="start">
            <Box padding="m" float="right" className="rounded-lg bg-blue-100">
              <SpaceBetween direction="vertical" size="xs">
                {/* Skeleton content for user message */}
                <Box>
                  <div className="animate-pulse">
                    <div className="mb-2 h-4 w-3/4 rounded bg-blue-200"></div>
                    <div className="h-4 w-1/2 rounded bg-blue-200"></div>
                  </div>
                </Box>
              </SpaceBetween>
            </Box>
            <Icon name="user-profile" size="large" ariaLabel="User" />
          </SpaceBetween>
        </Box>
      </Box>
    );
  }

  return (
    <Box padding="s">
      <SpaceBetween direction="horizontal" size="s" alignItems="start">
        <Icon name="gen-ai" size="large" ariaLabel="AI Assistant" />
        <Box padding="m" className="rounded-lg bg-gray-100">
          {/* Skeleton content for assistant message */}
          <div className="animate-pulse">
            <div className="mb-2 h-4 w-full rounded bg-gray-200"></div>
            <div className="mb-2 h-4 w-5/6 rounded bg-gray-200"></div>
            <div className="h-4 w-3/4 rounded bg-gray-200"></div>
          </div>
        </Box>
      </SpaceBetween>
    </Box>
  );
}
