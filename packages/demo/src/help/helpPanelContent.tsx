/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { HelpPanel } from '@cloudscape-design/components';
import { ReactNode } from 'react';

type HelpPanelContent = {
  [key: string]: ReactNode;
};

const helpPanelContent: HelpPanelContent = {
  default: (
    <HelpPanel>
      <div>
        <p>There is no additional help content on this page.</p>
      </div>
    </HelpPanel>
  ),
};

export default helpPanelContent;
