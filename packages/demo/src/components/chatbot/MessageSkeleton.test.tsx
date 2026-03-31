/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { render, screen } from '@testing-library/react';
import { MessageSkeleton } from './MessageSkeleton';

describe('MessageSkeleton', () => {
  it('renders assistant message skeleton by default', () => {
    render(<MessageSkeleton />);

    // Should show AI assistant icon
    expect(screen.getByLabelText('AI Assistant')).toBeInTheDocument();

    // Should have skeleton animation elements
    const skeletonElements = document.querySelectorAll('.animate-pulse');
    expect(skeletonElements.length).toBeGreaterThan(0);

    // Should have gray background for assistant messages
    const grayBackground = document.querySelector('.bg-gray-100');
    expect(grayBackground).toBeInTheDocument();
  });

  it('renders user message skeleton when isUser is true', () => {
    render(<MessageSkeleton isUser={true} />);

    // Should show user profile icon
    expect(screen.getByLabelText('User')).toBeInTheDocument();

    // Should have skeleton animation elements
    const skeletonElements = document.querySelectorAll('.animate-pulse');
    expect(skeletonElements.length).toBeGreaterThan(0);

    // Should have blue background for user messages
    const blueBackground = document.querySelector('.bg-blue-100');
    expect(blueBackground).toBeInTheDocument();
  });

  it('has proper accessibility attributes', () => {
    const { rerender } = render(<MessageSkeleton />);

    // Assistant message should have proper aria-label
    expect(screen.getByLabelText('AI Assistant')).toBeInTheDocument();

    rerender(<MessageSkeleton isUser={true} />);

    // User message should have proper aria-label
    expect(screen.getByLabelText('User')).toBeInTheDocument();
  });

  it('uses Cloudscape Design System components', () => {
    const { container } = render(<MessageSkeleton />);

    // Should use Cloudscape Box components (they have specific data attributes)
    const boxElements = container.querySelectorAll('[data-testid], .awsui-box, [class*="awsui"]');
    expect(boxElements.length).toBeGreaterThan(0);
  });
});
