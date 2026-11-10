import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { InventoryList } from '@/features/inventory/InventoryList';
import { endpoints } from '@/api/endpoints';
import { InventoryItem } from '@/api/schemas';

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getInventory: vi.fn(),
    useInventoryItem: vi.fn(),
    wasteInventoryItem: vi.fn(),
    deleteInventoryItem: vi.fn(),
    createInventoryItem: vi.fn(),
  },
}));

const mockInventoryItem: InventoryItem = {
  id: 'item-spinach',
  user_id: 'u-1',
  ingredient_id: 'spinach',
  display_name: 'Palak (Spinach)',
  quantity: 200,
  unit: 'g',
  storage: 'FRIDGE',
  added_on: '2026-10-25',
  opened_on: null,
  days_left: 1,
  days_left_display: '1 day left',
  status: 'USE_FIRST',
};

describe('Inventory Actions & Mutation Error Handling', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it('triggers item use modal and submits quantity used', async () => {
    vi.mocked(endpoints.getInventory).mockResolvedValueOnce({
      items: [mockInventoryItem],
      next_cursor: null,
    });
    vi.mocked(endpoints.useInventoryItem).mockResolvedValueOnce({
      item: { ...mockInventoryItem, quantity: 100 },
      action_logged: null,
      quantity_used: 100,
      is_archived: false,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <InventoryList />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Palak (Spinach)')).toBeInTheDocument();
    });

    // Click "Used" button
    fireEvent.click(screen.getByRole('button', { name: /used/i }));

    // Modal opens with title "Used Palak (Spinach)"
    await waitFor(() => {
      expect(screen.getByText(/used palak \(spinach\)/i)).toBeInTheDocument();
    });

    // Submit usage
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(endpoints.useInventoryItem).toHaveBeenCalledWith('item-spinach', 200);
    });
  });

  it('triggers waste modal and submits waste log with API error handling', async () => {
    vi.mocked(endpoints.getInventory).mockResolvedValueOnce({
      items: [mockInventoryItem],
      next_cursor: null,
    });
    vi.mocked(endpoints.wasteInventoryItem).mockRejectedValueOnce(
      new Error('Failed to log food waste.')
    );

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <InventoryList />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Palak (Spinach)')).toBeInTheDocument();
    });

    // Click "Wasted" button
    fireEvent.click(screen.getByRole('button', { name: /wasted/i }));

    await waitFor(() => {
      expect(screen.getByText(/wasted palak \(spinach\)/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(endpoints.wasteInventoryItem).toHaveBeenCalledWith('item-spinach', 200);
    });
  });

  it('deletes inventory item when trash button is clicked', async () => {
    vi.mocked(endpoints.getInventory).mockResolvedValueOnce({
      items: [mockInventoryItem],
      next_cursor: null,
    });
    vi.mocked(endpoints.deleteInventoryItem).mockResolvedValueOnce(undefined);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <InventoryList />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Palak (Spinach)')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText('Delete Palak (Spinach)'));

    await waitFor(() => {
      expect(endpoints.deleteInventoryItem).toHaveBeenCalledWith('item-spinach');
    });
  });
});
