import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ShoppingListView } from '@/features/shopping/ShoppingListView';
import { endpoints } from '@/api/endpoints';

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getActiveMealPlan: vi.fn(),
    createShoppingList: vi.fn(),
    patchShoppingItem: vi.fn(),
  },
}));

const mockShoppingList = {
  id: 'shop-list-1',
  user_id: 'user-1',
  source: 'PLAN',
  items: [
    {
      canonical_id: 'tomato',
      display_name: 'Tomato',
      category: 'Vegetables',
      quantity: 500,
      unit: 'g',
      est_cost_inr: 25,
      bought: false,
    },
    {
      canonical_id: 'paneer',
      display_name: 'Paneer',
      category: 'Dairy',
      quantity: 200,
      unit: 'g',
      est_cost_inr: 90,
      bought: true,
    },
  ],
  total_est_cost_inr: 115,
  created_at: '2026-10-28T00:00:00Z',
};

describe('Shopping List Category Grouping & Bought Toggles', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it('renders aggregated items grouped by supermarket category with total cost', async () => {
    vi.mocked(endpoints.getActiveMealPlan).mockResolvedValueOnce({
      id: 'plan-1',
      user_id: 'user-1',
      start_date: '2026-11-01',
      status: 'ACTIVE',
      low_variety: false,
      plan: { slots: [], shopping_list: [], total_waste_prevented_kg: 0 },
      created_at: '2026-10-28T00:00:00Z',
    });
    vi.mocked(endpoints.createShoppingList).mockResolvedValueOnce(mockShoppingList);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ShoppingListView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Shopping List')).toBeInTheDocument();
      expect(screen.getByText('₹115')).toBeInTheDocument();
    });

    // Categories (rendered with item count e.g. "Vegetables (1)")
    expect(screen.getByText(/Vegetables/i)).toBeInTheDocument();
    expect(screen.getByText(/Dairy/i)).toBeInTheDocument();

    // Items
    expect(screen.getByText('Tomato')).toBeInTheDocument();
    expect(screen.getByText('Paneer')).toBeInTheDocument();
  });

  it('marks item as bought and includes auto_add_to_inventory payload', async () => {
    vi.mocked(endpoints.getActiveMealPlan).mockResolvedValueOnce({
      id: 'plan-1',
      user_id: 'user-1',
      start_date: '2026-11-01',
      status: 'ACTIVE',
      low_variety: false,
      plan: { slots: [], shopping_list: [], total_waste_prevented_kg: 0 },
      created_at: '2026-10-28T00:00:00Z',
    });
    vi.mocked(endpoints.createShoppingList).mockResolvedValueOnce(mockShoppingList);
    vi.mocked(endpoints.patchShoppingItem).mockResolvedValueOnce({
      ...mockShoppingList,
      items: mockShoppingList.items.map((i) =>
        i.canonical_id === 'tomato' ? { ...i, bought: true } : i
      ),
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ShoppingListView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Tomato')).toBeInTheDocument();
    });

    // Toggle Tomato checkbox
    const tomatoCheckbox = screen.getByLabelText('Mark Tomato as bought');
    fireEvent.click(tomatoCheckbox);

    await waitFor(() => {
      expect(endpoints.patchShoppingItem).toHaveBeenCalledWith(
        'shop-list-1',
        'tomato',
        {
          bought: true,
          add_to_inventory: true,
        }
      );
    });
  });
});
