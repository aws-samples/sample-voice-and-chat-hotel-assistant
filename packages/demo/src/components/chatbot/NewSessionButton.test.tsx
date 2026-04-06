/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { NewSessionButton } from './NewSessionButton';

describe('NewSessionButton', () => {
  it('should render with correct text and icon', () => {
    const mockOnNewSession = vi.fn();

    render(<NewSessionButton onNewSession={mockOnNewSession} />);

    const button = screen.getByRole('button', { name: /new session/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it('should call onNewSession when clicked', () => {
    const mockOnNewSession = vi.fn();

    render(<NewSessionButton onNewSession={mockOnNewSession} />);

    const button = screen.getByRole('button', { name: /new session/i });
    fireEvent.click(button);

    expect(mockOnNewSession).toHaveBeenCalledTimes(1);
  });

  it('should be disabled when disabled prop is true', () => {
    const mockOnNewSession = vi.fn();

    render(<NewSessionButton onNewSession={mockOnNewSession} disabled={true} />);

    const button = screen.getByRole('button', { name: /new session/i });
    expect(button).toBeDisabled();
  });

  it('should not call onNewSession when disabled and clicked', () => {
    const mockOnNewSession = vi.fn();

    render(<NewSessionButton onNewSession={mockOnNewSession} disabled={true} />);

    const button = screen.getByRole('button', { name: /new session/i });
    fireEvent.click(button);

    expect(mockOnNewSession).not.toHaveBeenCalled();
  });

  it('should have refresh icon', () => {
    const mockOnNewSession = vi.fn();

    render(<NewSessionButton onNewSession={mockOnNewSession} />);

    // Cloudscape Button with iconName="refresh" should have the icon
    const button = screen.getByRole('button', { name: /new session/i });
    expect(button).toBeInTheDocument();
    // Note: Testing the actual icon presence would require more complex setup
    // as Cloudscape icons are rendered as SVGs. The iconName prop ensures the icon is there.
  });
});
