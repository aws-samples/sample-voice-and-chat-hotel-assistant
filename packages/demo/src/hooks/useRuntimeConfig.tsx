/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { useContext } from 'react';
import { RuntimeConfigContext } from '../components/RuntimeConfig';
import { RuntimeConfig } from '../types';

export const useRuntimeConfig = (): RuntimeConfig => {
  const runtimeConfig = useContext(RuntimeConfigContext);

  if (!runtimeConfig) {
    throw new Error('useRuntimeConfig must be used within a RuntimeConfigProvider');
  }

  return runtimeConfig;
};
