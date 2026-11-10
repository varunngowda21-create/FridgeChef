import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { Login } from '@/features/auth/Login';
import { Register } from '@/features/auth/Register';
import { AuthProvider } from '@/features/auth/AuthContext';

// Mock API endpoints
vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getMe: vi.fn().mockRejectedValue(new Error('Unauthenticated')),
    login: vi.fn().mockResolvedValue({
      user: { id: 'u1', email: 'test@example.com', display_name: 'Test Chef', created_at: '2026-10-28' },
      access_token: 'fake-jwt-token',
    }),
    register: vi.fn().mockResolvedValue({
      user: { id: 'u2', email: 'new@example.com', display_name: 'New Chef', created_at: '2026-10-28' },
      access_token: 'fake-jwt-token-2',
    }),
    logout: vi.fn().mockResolvedValue(undefined),
  },
}));

describe('Auth Screens', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login form and validates required fields', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText(/Welcome to FridgeChef/i)).toBeInTheDocument();
    const submitBtn = screen.getByRole('button', { name: /Sign In/i });

    // Submit form without email or password
    const form = submitBtn.closest('form')!;
    fireEvent.submit(form);
    expect(await screen.findByText(/Please enter both your email address and password/i)).toBeInTheDocument();
  });

  it('renders register form and enforces password complexity rule', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Register />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText(/Create your account/i)).toBeInTheDocument();

    const nameInput = screen.getByLabelText(/Your Name/i);
    const emailInput = screen.getByLabelText(/Email Address/i);
    const passwordInput = screen.getByLabelText(/Password/i);
    const submitBtn = screen.getByRole('button', { name: /Create Account/i });

    fireEvent.change(nameInput, { target: { value: 'Aarav' } });
    fireEvent.change(emailInput, { target: { value: 'aarav@example.com' } });
    // Weak password (< 8 chars or no numbers)
    fireEvent.change(passwordInput, { target: { value: 'short' } });
    fireEvent.click(submitBtn);

    expect(
      await screen.findByText(/Password must be at least 8 characters and contain at least one letter and one number/i)
    ).toBeInTheDocument();
  });
});
