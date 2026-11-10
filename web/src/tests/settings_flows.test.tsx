import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { SettingsView } from '@/features/settings/SettingsView';
import { AuthProvider } from '@/features/auth/AuthContext';
import { endpoints } from '@/api/endpoints';
import { UserPreferences } from '@/api/schemas';

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getMe: vi.fn(),
    updatePreferences: vi.fn(),
    exportData: vi.fn(),
    deleteAccount: vi.fn(),
    logout: vi.fn(),
  },
}));

const mockUser = {
  id: 'user-settings-1',
  email: 'settings@example.com',
  display_name: 'Settings User',
  created_at: '2026-10-28T00:00:00Z',
};

const mockPreferences: UserPreferences = {
  household_size: 3,
  diet: 'VEGETARIAN',
  spice_level: 'MEDIUM',
  cuisines: ['North Indian', 'South Indian'],
  max_cooking_time: 40,
  allergies: [],
  avoided_ingredients: [],
};

describe('Settings, Preferences Persistence, Data Export & Account Deletion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('updates dietary preferences and household size', async () => {
    vi.mocked(endpoints.getMe).mockResolvedValueOnce({
      ...mockUser,
      preferences: mockPreferences,
    });
    vi.mocked(endpoints.updatePreferences).mockResolvedValueOnce({
      ...mockPreferences,
      household_size: 4,
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <SettingsView />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Settings & Preferences')).toBeInTheDocument();
      expect(screen.getByText(/3 persons/i)).toBeInTheDocument();
    });

    // Increase household size: click "+"
    const plusBtn = screen.getByLabelText(/increase household size/i);
    fireEvent.click(plusBtn);

    await waitFor(() => {
      expect(screen.getByText(/4 persons/i)).toBeInTheDocument();
    });

    // Save preferences
    fireEvent.click(screen.getByRole('button', { name: /save preferences/i }));

    await waitFor(() => {
      expect(endpoints.updatePreferences).toHaveBeenCalledWith(
        expect.objectContaining({
          household_size: 4,
          diet: 'VEGETARIAN',
          spice_level: 'MEDIUM',
        })
      );
    });
  });

  it('triggers JSON data export via GET /api/v1/me/export', async () => {
    vi.mocked(endpoints.getMe).mockResolvedValueOnce({
      ...mockUser,
      preferences: mockPreferences,
    });
    vi.mocked(endpoints.exportData).mockResolvedValueOnce({
      user: mockUser,
      preferences: mockPreferences,
      inventory: [],
      cooking_history: [],
      meal_plans: [],
      waste_logs: [],
    });

    // Mock URL.createObjectURL and URL.revokeObjectURL
    const mockCreateObjectURL = vi.fn().mockReturnValue('blob:mock-url');
    const mockRevokeObjectURL = vi.fn();
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;

    render(
      <BrowserRouter>
        <AuthProvider>
          <SettingsView />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /export all my data/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /export all my data/i }));

    await waitFor(() => {
      expect(endpoints.exportData).toHaveBeenCalled();
      expect(mockCreateObjectURL).toHaveBeenCalled();
    });
  });

  it('submits account deletion with password verification payload in request body', async () => {
    vi.mocked(endpoints.getMe).mockResolvedValueOnce({
      ...mockUser,
      preferences: mockPreferences,
    });
    vi.mocked(endpoints.deleteAccount).mockResolvedValueOnce({
      message: 'Account deletion scheduled.',
      scheduled_deletion_at: '2026-11-28T00:00:00Z',
    });
    vi.mocked(endpoints.logout).mockResolvedValueOnce();

    render(
      <BrowserRouter>
        <AuthProvider>
          <SettingsView />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete account permanently/i })).toBeInTheDocument();
    });

    // Open confirmation modal
    fireEvent.click(screen.getByRole('button', { name: /delete account permanently/i }));

    await waitFor(() => {
      expect(screen.getByText('Delete Account')).toBeInTheDocument();
    });

    // Enter password
    const pwdInput = screen.getByPlaceholderText('••••••••');
    fireEvent.change(pwdInput, { target: { value: 'SecretPass123' } });

    // Confirm deletion
    fireEvent.click(screen.getByRole('button', { name: /delete my account/i }));

    await waitFor(() => {
      expect(endpoints.deleteAccount).toHaveBeenCalledWith('SecretPass123');
    });
  });
});
