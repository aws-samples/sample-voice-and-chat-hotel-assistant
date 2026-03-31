/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useChatbotConfig, getChatbotConfig } from './chatbot-config';
import RuntimeConfigProvider from '../components/RuntimeConfig';
import type { RuntimeConfig } from '../types';

// Mock fetch for runtime config
global.fetch = vi.fn();

const mockRuntimeConfig: RuntimeConfig = {
  cognitoProps: {
    userPoolId: 'us-east-1_test123',
    userPoolWebClientId: 'test-client-id',
    region: 'us-east-1',
  },
  messagingApiEndpoint: 'https://api.test.com',
  hotelAssistantClientId: 'test-assistant-id',
  applicationName: 'Hotel Assistant Test',
};

describe('chatbot configuration', () => {
  describe('useChatbotConfig', () => {
    it('should return chatbot config from runtime config', async () => {
      // Mock successful fetch
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRuntimeConfig),
      });

      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <RuntimeConfigProvider>{children}</RuntimeConfigProvider>
      );

      let result: any;
      await act(async () => {
        const hookResult = renderHook(() => useChatbotConfig(), { wrapper });
        result = hookResult.result;
      });

      // Wait for the runtime config to load
      await vi.waitFor(() => {
        expect(result.current).toEqual({
          awsRegion: 'us-east-1',
          messagingApiEndpoint: 'https://api.test.com',
          hotelAssistantClientId: 'test-assistant-id',
        });
      });
    });

    it('should throw error when used outside RuntimeConfigProvider', () => {
      // Suppress console.error for this test since we expect an error
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      expect(() => {
        renderHook(() => useChatbotConfig());
      }).toThrow('useRuntimeConfig must be used within a RuntimeConfigProvider');
      
      consoleSpy.mockRestore();
    });
  });

  describe('getChatbotConfig', () => {
    it('should return null and log deprecation warning', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const result = getChatbotConfig();

      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        'getChatbotConfig is deprecated. Use useChatbotConfig() hook instead.'
      );

      consoleSpy.mockRestore();
    });
  });
});