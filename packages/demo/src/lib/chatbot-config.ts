/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

/**
 * Configuration file for the Hotel Assistant Chatbot
 * 
 * This configuration integrates with the runtime config system used by the demo package.
 * It supports both runtime-config.json (for deployment) and environment variables (for development).
 */

import { useRuntimeConfig } from '../hooks/useRuntimeConfig';
import type { ChatbotConfig } from '../types';

/**
 * Hook to get chatbot configuration from the runtime config system
 * 
 * @returns ChatbotConfig object with AWS region, messaging API endpoint, and client ID
 */
export const useChatbotConfig = (): ChatbotConfig => {
  const runtimeConfig = useRuntimeConfig();

  return {
    awsRegion: runtimeConfig.cognitoProps.region,
    messagingApiEndpoint: runtimeConfig.messagingApiEndpoint,
    virtualAssistantClientId: runtimeConfig.virtualAssistantClientId,
  };
};

/**
 * Legacy configuration object for backward compatibility
 * 
 * @deprecated Use useChatbotConfig() hook instead for proper integration with runtime config system
 */
export const getChatbotConfig = (): ChatbotConfig | null => {
  // This function can't access React context, so it returns null
  // Components should use the useChatbotConfig hook instead
  console.warn('getChatbotConfig is deprecated. Use useChatbotConfig() hook instead.');
  return null;
};

export default useChatbotConfig;