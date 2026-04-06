/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { createFileRoute } from '@tanstack/react-router';
import HotelAssistantChat from '../../pages/HotelAssistantChat';

export const Route = createFileRoute('/chat/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <HotelAssistantChat />;
}
