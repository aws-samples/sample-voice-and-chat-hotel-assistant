/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { Box, Icon } from '@cloudscape-design/components';
import { useEffect, useState } from 'react';

interface PollingIndicatorProps {
  isPolling: boolean;
  lastPolled?: Date;
}

export function PollingIndicator({ isPolling }: PollingIndicatorProps) {
  const [showIndicator, setShowIndicator] = useState(false);

  // Only show the indicator briefly when polling starts
  useEffect(() => {
    if (isPolling) {
      setShowIndicator(true);
      // Hide the indicator after a short time to avoid disruption
      const timer = setTimeout(() => {
        setShowIndicator(false);
      }, 1000); // Show for 1 second

      return () => clearTimeout(timer);
    } else {
      setShowIndicator(false);
      return undefined;
    }
  }, [isPolling]);

  // Don't show anything if not polling or if we're hiding the indicator
  if (!isPolling || !showIndicator) {
    return null;
  }

  return (
    <Box
      padding={{ horizontal: 's', vertical: 'xs' }}
      className="fixed right-4 top-4 z-50 rounded-lg border border-gray-200 bg-white shadow-sm"
    >
      <div className="flex items-center space-x-2">
        <Icon name="refresh" size="small" />
        <span className="text-xs text-gray-600">Checking for new messages...</span>
      </div>
    </Box>
  );
}

/**
 * A more subtle version that shows as a small dot indicator
 */
export function SubtlePollingIndicator({ isPolling }: { isPolling: boolean }) {
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    if (isPolling) {
      setPulse(true);
      const timer = setTimeout(() => {
        setPulse(false);
      }, 500);

      return () => clearTimeout(timer);
    } else {
      setPulse(false);
      return undefined;
    }
  }, [isPolling]);

  if (!isPolling || !pulse) {
    return null;
  }

  return (
    <Box className="fixed right-4 top-4 z-50">
      <div className="h-2 w-2 animate-pulse rounded-full bg-blue-500"></div>
    </Box>
  );
}
