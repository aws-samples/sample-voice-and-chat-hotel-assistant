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
      { label: 'Amazon Nova Pro', value: 'us.amazon.nova-pro-v1:0' },
      { label: 'Amazon Nova Premier', value: 'us.amazon.nova-premier-v1:0' },

      // Anthropic Claude Models (v3+)
      { label: 'Claude 3 Haiku', value: 'us.anthropic.claude-3-haiku-20240307-v1:0' },
      { label: 'Claude 3 Sonnet', value: 'us.anthropic.claude-3-sonnet-20240229-v1:0' },
      { label: 'Claude 3.5 Haiku', value: 'us.anthropic.claude-3-5-haiku-20241022-v1:0' },
      {
        label: 'Claude 3.5 Sonnet',
        value: 'us.anthropic.claude-3-5-sonnet-20240620-v1:0',
      },
      {
        label: 'Claude 3.5 Sonnet v2',
        value: 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
      },
      {
        label: 'Claude 3.7 Sonnet',
        value: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
      },
      { label: 'Claude 4 Sonnet', value: 'us.anthropic.claude-sonnet-4-20250514-v1:0' },
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
