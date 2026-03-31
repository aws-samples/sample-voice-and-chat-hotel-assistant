/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import React, { PropsWithChildren, useEffect } from 'react';
import { AuthProvider, AuthProviderProps, useAuth } from 'react-oidc-context';
import { Alert, Spinner, Button } from '@cloudscape-design/components';
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig';
import { useGlobalUIContext } from '../../hooks/useGlobalUIContext';

/**
 * Sets up the Cognito auth for Hotel Assistant.
 *
 * This supports both runtime-config.json (deployment) and environment variables (development).
 * The cognitoProps must be configured with Hotel Assistant Cognito settings.
 */
const CognitoAuth: React.FC<PropsWithChildren> = ({ children }) => {
  const { cognitoProps } = useRuntimeConfig();

  if (!cognitoProps) {
    return (
      <Alert type="error" header="Authentication configuration error">
        The cognitoProps have not been configured. Please check your runtime-config.json or
        environment variables.
      </Alert>
    );
  }

  const cognitoAuthConfig: AuthProviderProps = {
    authority: `https://cognito-idp.${cognitoProps.region}.amazonaws.com/${cognitoProps.userPoolId}`,
    client_id: cognitoProps.userPoolWebClientId,
    redirect_uri: window.location.origin,
    response_type: 'code',
    scope: 'aws.cognito.signin.user.admin openid profile chatbot-messaging/write',
  };

  return (
    <AuthProvider {...cognitoAuthConfig}>
      <CognitoAuthInternal>{children}</CognitoAuthInternal>
    </AuthProvider>
  );
};

const CognitoAuthInternal: React.FC<PropsWithChildren> = ({ children }) => {
  const auth = useAuth();
  const { addFlashItem } = useGlobalUIContext();

  useEffect(() => {
    if (!auth.isAuthenticated && !auth.isLoading) {
      auth.signinRedirect();
    }
  }, [auth]);

  // Handle authentication errors with flash notifications
  useEffect(() => {
    if (auth.error) {
      addFlashItem({
        type: 'error',
        content:
          'Error contacting Cognito. Please check your Hotel Assistant configuration is correct in runtime-config.json or environment variables.',
        action: <Button onClick={() => window.location.reload()}>Retry</Button>,
      });
    }
  }, [auth.error, addFlashItem]);

  if (auth.isAuthenticated) {
    return children;
  } else if (auth.error) {
    // Show minimal error state since flash notification handles the error
    return (
      <Alert type="error" header="Authentication error">
        Please check the notification above for details and retry options.
      </Alert>
    );
  } else {
    return <Spinner />;
  }
};

export default CognitoAuth;
