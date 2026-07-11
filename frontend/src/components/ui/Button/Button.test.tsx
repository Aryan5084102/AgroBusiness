import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('renders its label', () => {
    render(<Button>Save invoice</Button>);
    expect(screen.getByRole('button', { name: 'Save invoice' })).toBeInTheDocument();
  });

  it('calls onClick when pressed', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Finalize</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Finalize' }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('is disabled and busy while loading, and does not fire onClick', async () => {
    const onClick = vi.fn();
    render(
      <Button isLoading onClick={onClick}>
        Processing
      </Button>,
    );
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
