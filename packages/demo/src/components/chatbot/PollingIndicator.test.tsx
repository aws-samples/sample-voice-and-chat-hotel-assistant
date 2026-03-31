/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { render, screen } from '@testing-library/react';
import { PollingIndicator, SubtlePollingIndicator } from './PollingIndicator';

describe('PollingIndicator', () => {
  it('shows indicator when polling starts', () => {
    render(<PollingIndicator isPolling={true} />);

    // Should show the polling message
    expect(screen.getByText('Checking for new messages...')).toBeDefined();

    // Should show refresh icon (check for SVG element)
    const svgElement = document.querySelector('svg');
    expect(svgElement).toBeDefined();
  });

  it('hides indicator when not polling', () => {
    render(<PollingIndicator isPolling={false} />);

    // Should not show the polling message
    expect(screen.queryByText('Checking for new messages...')).toBeNull();
  });

  it('uses Cloudscape Design System components', () => {
    const { container } = render(<PollingIndicator isPolling={true} />);

    // Should use Cloudscape Box and Icon components
    const cloudscapeElements = container.querySelectorAll('[class*="awsui"]');
    expect(cloudscapeElements.length).toBeGreaterThan(0);
  });
});

describe('SubtlePollingIndicator', () => {
  it('shows subtle indicator when polling', () => {
    const { container } = render(<SubtlePollingIndicator isPolling={true} />);

    // Should show the pulsing dot
    const pulsingDot = container.querySelector('.animate-pulse');
    expect(pulsingDot).toBeDefined();
    expect(pulsingDot?.classList.contains('bg-blue-500')).toBe(true);
  });

  it('hides indicator when not polling', () => {
    const { container } = render(<SubtlePollingIndicator isPolling={false} />);

    // Should not show the pulsing dot
    const pulsingDot = container.querySelector('.animate-pulse');
    expect(pulsingDot).toBeNull();
  });

  it('is positioned fixed in top-right corner', () => {
    const { container } = render(<SubtlePollingIndicator isPolling={true} />);

    const indicator = container.querySelector('.fixed');
    expect(indicator).toBeDefined();
    expect(indicator?.classList.contains('right-4')).toBe(true);
    expect(indicator?.classList.contains('top-4')).toBe(true);
    expect(indicator?.classList.contains('z-50')).toBe(true);
  });
});
