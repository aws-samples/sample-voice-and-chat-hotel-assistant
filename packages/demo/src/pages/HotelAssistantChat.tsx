/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { ContentLayout, Header, SpaceBetween } from '@cloudscape-design/components';
import { Chatbot } from '../components/chatbot/Chatbot';

const HotelAssistantChat = () => {
  return (
    <ContentLayout
      header={
        <SpaceBetween size="m">
          <Header variant="h1" description="Chat with your hotel assistant">
            Hotel Assistant Chat
          </Header>
        </SpaceBetween>
      }
    >
      <SpaceBetween size={'xl'}>
        <Chatbot />
      </SpaceBetween>
    </ContentLayout>
  );
};

export default HotelAssistantChat;
