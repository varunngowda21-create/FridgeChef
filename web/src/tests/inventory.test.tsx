import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { InventoryList } from '@/features/inventory/InventoryList';
import { InventoryItemSchema, InventoryListResponseSchema } from '@/api/schemas';

const mockItems = [
  {
    id: 'item-1',
    ingredient_id: 'spinach',
    display_name: 'Fresh Spinach',
    quantity: 200,
    unit: 'g',
    storage: 'FRIDGE',
    added_on: '2026-10-26',
    days_left: 1,
    days_left_display: '1 day left',
    status: 'USE_FIRST',
  },
  {
    id: 'item-2',
    ingredient_id: 'tomato',
    display_name: 'Ripe Tomatoes',
    quantity: 4,
    unit: 'piece',
    storage: 'FRIDGE',
    added_on: '2026-10-25',
    days_left: 3,
    days_left_display: '3 days left',
    status: 'USE_SOON',
  },
  {
    id: 'item-3',
    ingredient_id: 'onion',
    display_name: 'Red Onion',
    quantity: 6,
    unit: 'piece',
    storage: 'PANTRY',
    added_on: '2026-10-20',
    days_left: 12,
    days_left_display: '12 days left',
    status: 'SAFE',
  },
];

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getInventory: vi.fn().mockImplementation(() =>
      Promise.resolve({
        items: mockItems,
        next_cursor: null,
      })
    ),
    useInventoryItem: vi.fn().mockResolvedValue({}),
    wasteInventoryItem: vi.fn().mockResolvedValue({}),
    deleteInventoryItem: vi.fn().mockResolvedValue({}),
  },
}));

describe('Inventory Component', () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  it('renders inventory items and filters items by search input', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <InventoryList />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Initial render displays items
    expect(await screen.findByText('Fresh Spinach')).toBeInTheDocument();
    expect(screen.getByText('Ripe Tomatoes')).toBeInTheDocument();
    expect(screen.getByText('Red Onion')).toBeInTheDocument();

    // Test live search filter
    const searchInput = screen.getByPlaceholderText(/Search items in your fridge/i);
    fireEvent.change(searchInput, { target: { value: 'spinach' } });

    expect(screen.getByText('Fresh Spinach')).toBeInTheDocument();
    expect(screen.queryByText('Red Onion')).not.toBeInTheDocument();
  });

  describe('Inventory Schema Quantity Validation', () => {
    it('accepts quantity as number and preserves decimals', () => {
      const parsed = InventoryItemSchema.parse({
        id: 'test-item-1',
        display_name: 'Paneer',
        quantity: 250.5,
        unit: 'g',
        storage: 'FRIDGE',
        added_on: '2026-11-10',
        days_left: 5,
        days_left_display: '5 days left',
        status: 'SAFE',
      });
      expect(parsed.quantity).toBe(250.5);
      expect(typeof parsed.quantity).toBe('number');
    });

    it('coerces backend stringified Decimal quantities to numbers', () => {
      const parsed = InventoryItemSchema.parse({
        id: 'test-item-2',
        display_name: 'Tomatoes',
        quantity: '500.00',
        unit: 'g',
        storage: 'FRIDGE',
        added_on: '2026-11-10',
        days_left: 7,
        days_left_display: '7 days left',
        status: 'SAFE',
      });
      expect(parsed.quantity).toBe(500);
      expect(typeof parsed.quantity).toBe('number');
    });

    it('correctly parses InventoryListResponse with stringified backend decimals', () => {
      const apiResponse = {
        items: [
          {
            id: 'item-101',
            display_name: 'Onions',
            quantity: '300.75',
            unit: 'g',
            storage: 'PANTRY',
            added_on: '2026-11-10',
            days_left: 30,
            days_left_display: '30 days left',
            status: 'SAFE',
          },
        ],
        next_cursor: null,
      };
      const result = InventoryListResponseSchema.safeParse(apiResponse);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.items[0].quantity).toBe(300.75);
        expect(typeof result.data.items[0].quantity).toBe('number');
      }
    });

    it('rejects invalid or negative quantity strings', () => {
      const negativeResult = InventoryItemSchema.safeParse({
        id: 'bad-item',
        display_name: 'Bad',
        quantity: '-10.50',
        unit: 'g',
        storage: 'FRIDGE',
        added_on: '2026-11-10',
        days_left: 1,
        days_left_display: '1 day left',
        status: 'SAFE',
      });
      expect(negativeResult.success).toBe(false);

      const invalidStringResult = InventoryItemSchema.safeParse({
        id: 'bad-item-2',
        display_name: 'Bad',
        quantity: 'not-a-number',
        unit: 'g',
        storage: 'FRIDGE',
        added_on: '2026-11-10',
        days_left: 1,
        days_left_display: '1 day left',
        status: 'SAFE',
      });
      expect(invalidStringResult.success).toBe(false);
    });
  });
});

