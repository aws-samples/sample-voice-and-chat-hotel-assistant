/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { StatusIndicator } from '@cloudscape-design/components';
import { MessageStatus } from '../../types';

interface MessageStatusIconProps {
  status: MessageStatus;
}

/**
 * Message status icon component using CloudScape StatusIndicator
 * Maps message statuses to appropriate visual indicators with accessibility labels
 */
export function MessageStatusIcon({ status }: MessageStatusIconProps) {
  switch (status) {
    case MessageStatus.SENT:
      return <StatusIndicator type="pending" iconAriaLabel="Message sent" />;
    case MessageStatus.DELIVERED:
      return <StatusIndicator type="in-progress" iconAriaLabel="Message delivered" />;
    case MessageStatus.READ:
      return <StatusIndicator type="success" iconAriaLabel="Message read" />;
    case MessageStatus.FAILED:
      return <StatusIndicator type="error" iconAriaLabel="Message failed" />;
    case MessageStatus.WARNING:
      return <StatusIndicator type="warning" iconAriaLabel="Message warning" />;
    case MessageStatus.DELETED:
      return <StatusIndicator type="stopped" iconAriaLabel="Message deleted" />;
    default:
      return null;
  }
}
