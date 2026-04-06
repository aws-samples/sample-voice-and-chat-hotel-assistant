/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { useContext } from 'react';
import { AppLayoutContext } from '../components/AppLayout';

export const useAppLayout = (): AppLayoutContext =>
  useContext(AppLayoutContext);
