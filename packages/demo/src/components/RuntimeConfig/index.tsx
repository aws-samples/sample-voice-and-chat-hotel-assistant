/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { Alert, Spinner, Button } from '@cloudscape-design/components';
import React, { createContext, PropsWithChildren, useEffect, useState } from 'react';
import type { RuntimeConfig } from '../../types';
import { useGlobalUIContext } from '../../hooks/useGlobalUIContext';

/**
 * Context for storing the runtimeConfig.
 */
export const RuntimeConfigContext = createContext<RuntimeConfig | undefined>(undefined);

/**
 * Sets up the runtimeConfig for Hotel Assistant.
 *
 * This supports both runtime-config.json (for deployment) and environment variables (for development).
 */
const RuntimeConfigProvider: React.FC<PropsWithChildren> = ({ children }) => {
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | undefined>();
  const [error, setError] = useState<string | undefined>();
  const { addFlashItem } = useGlobalUIContext();

  useEffect(() => {
    // Try to load from runtime-config.json first (deployment)
    fetch('/runtime-config.json')
      .then(response => {
        if (!response.ok) {
          throw new Error('Runtime config not found');
        }
        return response.json();
      })
      .then(_runtimeConfig => {
        setRuntimeConfig(_runtimeConfig as RuntimeConfig);
      })
      .catch(() => {
        // Fallback to environment variables (development)
        const envConfig: RuntimeConfig = {
          cognitoProps: {
            userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
            userPoolWebClientId: import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID,
            region: import.meta.env.VITE_AWS_REGION,
          },
          messagingApiEndpoint: import.meta.env.VITE_MESSAGING_API_ENDPOINT,
          virtualAssistantClientId: import.meta.env.VITE_HOTEL_ASSISTANT_CLIENT_ID,
          applicationName: import.meta.env.VITE_APP_NAME || 'Hotel Assistant',
          logo: import.meta.env.VITE_APP_LOGO_URL,
        };

        // Validate required environment variables
        if (
          !envConfig.cognitoProps.userPoolId ||
          !envConfig.cognitoProps.userPoolWebClientId ||
          !envConfig.cognitoProps.region ||
          !envConfig.messagingApiEndpoint ||
          !envConfig.virtualAssistantClientId
        ) {
          const errorMessage =
            'Missing required configuration. Please check runtime-config.json or environment variables.';
          setError(errorMessage);

          // Show flash notification for configuration error
          addFlashItem({
            type: 'error',
            content: errorMessage,
            action: <Button onClick={() => window.location.reload()}>Retry</Button>,
          });
          return;
        }

        setRuntimeConfig(envConfig);
      });
  }, [setRuntimeConfig]);

  return error ? (
    <Alert type="error" header="Configuration error">
      Please check the notification above for details and retry options.
    </Alert>
  ) : runtimeConfig ? (
    <RuntimeConfigContext.Provider value={runtimeConfig}>{children}</RuntimeConfigContext.Provider>
  ) : (
    <Spinner />
  );
};

export default RuntimeConfigProvider;
