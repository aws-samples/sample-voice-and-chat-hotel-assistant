/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { Button, FormField, Input, Select, SpaceBetween } from '@cloudscape-design/components';
import { forwardRef, useImperativeHandle, useRef, useState } from 'react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  loading?: boolean;
  modelId: string;
  temperature: string;
  onModelChange: (modelId: string) => void;
  onTemperatureChange: (temperature: string) => void;
}

export interface ChatInputRef {
  focus: () => void;
}

export const ChatInput = forwardRef<ChatInputRef, ChatInputProps>(
  (
    {
      onSendMessage,
      disabled = false,
      loading = false,
      modelId,
      temperature,
      onModelChange,
      onTemperatureChange,
    },
    ref
  ) => {
    const [message, setMessage] = useState('');
    const inputRef = useRef<any>(null);

    useImperativeHandle(ref, () => ({
      focus: () => {
        inputRef.current?.focus();
      },
    }));

    const handleSend = () => {
      if (message.trim()) {
        onSendMessage(message);
        setMessage('');
      }
    };

    const handleKeyPress = (event: any) => {
      if (event.detail.key === 'Enter' && !disabled && !loading && message.trim()) {
        handleSend();
      }
    };

    const modelOptions = [
      // Amazon Nova Models
      { label: 'Amazon Nova Lite', value: 'us.amazon.nova-lite-v1:0' },
      { label: 'Amazon Nova Micro', value: 'us.amazon.nova-micro-v1:0' },
      { label: 'Amazon Nova 2 Lite', value: 'global.amazon.nova-2-lite-v1:0' },

      // Anthropic Claude Models (v3+)
      { label: 'Claude 4.5 Haiku', value: 'us.anthropic.claude-haiku-4-5-20251001-v1:0' },
      { label: 'Claude 4.6 Sonnet', value: 'global.anthropic.claude-sonnet-4-6' },
    ];

    const selectedModelOption = modelOptions.find(option => option.value === modelId) || null;

    const handleTemperatureChange = (value: string) => {
      // Allow empty string for clearing
      if (value === '') {
        onTemperatureChange(value);
        return;
      }

      // Ensure temperature is between 0 and 1 with 1 decimal place
      const numValue = parseFloat(value);
      if (!isNaN(numValue) && numValue >= 0 && numValue <= 1) {
        // Round to 1 decimal place
        const rounded = Math.round(numValue * 10) / 10;
        onTemperatureChange(rounded.toString());
      }
    };

    return (
      <SpaceBetween direction="horizontal" size="s" alignItems="end">
        {/* nosemgrep: jsx-not-internationalized - i18n not in prototype scope */}
        <FormField
          label="Message"
          secondaryControl={
            <SpaceBetween direction="horizontal" size="s">
              {/* nosemgrep: jsx-not-internationalized - i18n not in prototype scope */}
              <FormField label="Model">
                <Select
                  selectedOption={selectedModelOption}
                  onChange={({ detail }: any) => onModelChange(detail.selectedOption?.value || '')}
                  options={modelOptions}
                  // nosemgrep: jsx-not-internationalized - i18n not in prototype scope
                  placeholder="Select a model"
                  disabled={disabled || loading}
                />
              </FormField>
              {/* nosemgrep: jsx-not-internationalized - i18n not in prototype scope */}
              <FormField label="Temperature">
                <Input
                  value={temperature}
                  onChange={({ detail }: any) => handleTemperatureChange(detail.value)}
                  type="number"
                  inputMode="decimal"
                  step={0.1}
                  // nosemgrep: jsx-not-internationalized - i18n not in prototype scope
                  placeholder="0.0 - 1.0"
                  disabled={disabled || loading}
                />
              </FormField>
            </SpaceBetween>
          }
        >
          <Input
            ref={inputRef}
            value={message}
            onChange={({ detail }: any) => setMessage(detail.value)}
            onKeyDown={handleKeyPress}
            // nosemgrep: jsx-not-internationalized - i18n not in prototype scope
            placeholder="Type your message..."
            disabled={disabled || loading}
          />
        </FormField>
        {/* nosemgrep: jsx-not-internationalized - i18n not in prototype scope */}
        <Button
          variant="primary"
          onClick={handleSend}
          disabled={disabled || loading || !message.trim()}
          loading={loading}
        >
          Send
        </Button>
      </SpaceBetween>
    );
  }
);

ChatInput.displayName = 'ChatInput';
