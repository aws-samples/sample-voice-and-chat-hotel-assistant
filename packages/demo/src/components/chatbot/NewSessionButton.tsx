/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import React from 'react';
import { Button } from '@cloudscape-design/components';

interface NewSessionButtonProps {
  onNewSession: () => void;
  disabled?: boolean;
}

/**
 * Simple button component for starting a new chat session
 *
 * Requirements: 5.1, 5.2
 * - 5.1: Display a "New Session" button in the chat interface
 * - 5.2: Clear current conversation messages from the UI when clicked
 */
export const NewSessionButton: React.FC<NewSessionButtonProps> = ({
  onNewSession,
  disabled = false,
}) => {
  return (
    <Button variant="normal" iconName="refresh" onClick={onNewSession} disabled={disabled}>
      New Session
    </Button>
  );
};
