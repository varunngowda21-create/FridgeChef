import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { Login } from '@/features/auth/Login';
import { Register } from '@/features/auth/Register';
import { AuthProvider, useAuth } from '@/features/auth/AuthContext';
import { ProtectedRoute } from '@/app/Router';
import { endpoints } from '@/api/endpoints';
import { queryClient } from '@/lib/queryClient';

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getMe: vi.fn(),
    updatePreferences: vi.fn(),
  },
}));

describe('Authentication & Session Flows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handles login success and session establishment', async () => {
    vi.mocked(endpoints.login).mockResolvedValueOnce({
      access_token: 'fake-jwt-token',
      refresh_token: 'fake-refresh-token',
      user: {
        id: 'u-1',
        email: 'chef@example.com',
        display_name: 'Chef User',
        created_at: '2026-10-28T00:00:00Z',
      },
    });

    vi.mocked(endpoints.getMe).mockResolvedValueOnce({
      id: 'u-1',
      email: 'chef@example.com',
      display_name: 'Chef User',
      created_at: '2026-10-28T00:00:00Z',
      preferences: {
        household_size: 2,
        diet: 'VEGETARIAN',
        spice_level: 'MEDIUM',
        cuisines: ['North Indian'],
        max_cooking_time: 45,
        allergies: [],
        avoided_ingredients: [],
      },
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<div>Dashboard Home</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'chef@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'Password123' },
    });

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(endpoints.login).toHaveBeenCalledWith({
        email: 'chef@example.com',
        password: 'Password123',
      });
    });
  });

  it('displays user-facing error message on login failure', async () => {
    vi.mocked(endpoints.login).mockRejectedValueOnce(
      new Error('Invalid email or password.')
    );
    vi.mocked(endpoints.getMe).mockRejectedValueOnce(new Error('Unauthorized'));

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'wrong@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'WrongPass1' },
    });

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password.')).toBeInTheDocument();
    });
  });

  it('handles registration success and redirects to onboarding', async () => {
    vi.mocked(endpoints.register).mockResolvedValueOnce({
      access_token: 'fake-jwt-token-2',
      refresh_token: 'fake-refresh-token-2',
      user: {
        id: 'u-2',
        email: 'newchef@example.com',
        display_name: 'New Chef',
        created_at: '2026-10-28T00:00:00Z',
      },
    });

    render(
      <MemoryRouter initialEntries={['/register']}>
        <AuthProvider>
          <Routes>
            <Route path="/register" element={<Register />} />
            <Route path="/onboarding" element={<div>Onboarding Wizard Screen</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/your name/i), {
      target: { value: 'Pooja Patel' },
    });
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'pooja@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'SecurePass1' },
    });

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(endpoints.register).toHaveBeenCalledWith({
        display_name: 'Pooja Patel',
        email: 'pooja@example.com',
        password: 'SecurePass1',
      });
      expect(screen.getByText('Onboarding Wizard Screen')).toBeInTheDocument();
    });
  });

  it('blocks unauthenticated access in ProtectedRoute and redirects to /login', async () => {
    vi.mocked(endpoints.getMe).mockRejectedValue(new Error('Unauthorized'));

    const TestProtected = () => <div>Secret Protected Content</div>;

    render(
      <MemoryRouter initialEntries={['/inventory']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/inventory"
              element={
                <ProtectedRoute>
                  <TestProtected />
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div>Redirected Login Screen</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Redirected Login Screen')).toBeInTheDocument();
      expect(screen.queryByText('Secret Protected Content')).not.toBeInTheDocument();
    });
  });

  it('restores user session and preferences on application launch', async () => {
    vi.mocked(endpoints.getMe).mockResolvedValueOnce({
      id: 'u-42',
      email: 'restored@example.com',
      display_name: 'Restored User',
      created_at: '2026-10-28T00:00:00Z',
      preferences: {
        household_size: 4,
        diet: 'VEGETARIAN',
        spice_level: 'HOT',
        cuisines: ['South Indian'],
        max_cooking_time: 30,
        allergies: ['peanuts'],
        avoided_ingredients: [],
      },
    });

    const ProfileDisplay = () => {
      const { user, preferences, isLoading } = useAuth();
      if (isLoading) return <div>Restoring session...</div>;
      return (
        <div>
          <span>User: {user?.display_name}</span>
          <span>Diet: {preferences?.diet}</span>
        </div>
      );
    };

    render(
      <MemoryRouter>
        <AuthProvider>
          <ProfileDisplay />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('User: Restored User')).toBeInTheDocument();
      expect(screen.getByText('Diet: VEGETARIAN')).toBeInTheDocument();
    });
  });

  it('clears queryClient cache when signing out', async () => {
    queryClient.setQueryData(['inventory', 'ALL'], [{ id: '1', name: 'Secret Item' }]);
    expect(queryClient.getQueryData(['inventory', 'ALL'])).toBeDefined();

    vi.mocked(endpoints.getMe).mockResolvedValueOnce({
      id: 'u-1',
      email: 'chef@example.com',
      display_name: 'Chef User',
      created_at: '2026-10-28T00:00:00Z',
      preferences: null,
    });
    vi.mocked(endpoints.logout).mockResolvedValueOnce(undefined);

    const SignOutButton = () => {
      const { logout } = useAuth();
      return <button onClick={logout}>Log Out</button>;
    };

    render(
      <MemoryRouter>
        <AuthProvider>
          <SignOutButton />
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /log out/i }));

    await waitFor(() => {
      expect(endpoints.logout).toHaveBeenCalled();
      expect(queryClient.getQueryData(['inventory', 'ALL'])).toBeUndefined();
    });
  });
});
