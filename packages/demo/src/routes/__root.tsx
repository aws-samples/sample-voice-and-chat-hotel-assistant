/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { createRootRoute } from '@tanstack/react-router';
import AppLayout from '../components/AppLayout';

export const Route = createRootRoute({
  component: () => <AppLayout />,
});
