import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MealPlanView } from '@/features/meal-plan/MealPlanView';
import { endpoints } from '@/api/endpoints';

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getActiveMealPlan: vi.fn(),
    createMealPlan: vi.fn(),
    regenerateSlot: vi.fn(),
    createShoppingList: vi.fn(),
  },
}));

// Build 14 deterministic slots (7 days x 2 meals: LUNCH and DINNER)
const mock14Slots = Array.from({ length: 7 }, (_, i) => {
  const day = i + 1;
  return [
    {
      day,
      date: `2026-11-0${day}`,
      meal: 'LUNCH',
      recipe_id: `recipe-l-${day}`,
      recipe_title: `Lunch Recipe Day ${day}`,
      servings: 2,
      prioritised_ingredients: ['tomato'],
      waste_prevented_g: 100,
    },
    {
      day,
      date: `2026-11-0${day}`,
      meal: 'DINNER',
      recipe_id: `recipe-d-${day}`,
      recipe_title: `Dinner Recipe Day ${day}`,
      servings: 2,
      prioritised_ingredients: ['spinach'],
      waste_prevented_g: 150,
    },
  ];
}).flat();

const mockMealPlan = {
  id: 'plan-14-slots',
  user_id: 'user-1',
  start_date: '2026-11-01',
  status: 'ACTIVE',
  low_variety: false,
  plan: {
    slots: mock14Slots,
    total_waste_prevented_kg: 1.75,
    shopping_list: [],
  },
  created_at: '2026-10-28T00:00:00Z',
};

describe('Meal Plan 14-Slot Grid, Locking & Slot Regeneration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it('renders all 14 supported slots (lunch and dinner across 7 days)', async () => {
    vi.mocked(endpoints.getActiveMealPlan).mockResolvedValueOnce(mockMealPlan);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <MealPlanView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('7-Day Meal Plan')).toBeInTheDocument();
      expect(screen.getByText(/expected waste prevented: 1.75 kg/i)).toBeInTheDocument();
    });

    // Verify 7 day headers
    expect(screen.getAllByText(/day [1-7] of 7/i)).toHaveLength(7);

    // Verify exactly 7 LUNCH and 7 DINNER badges (14 slots total)
    expect(screen.getAllByText('LUNCH')).toHaveLength(7);
    expect(screen.getAllByText('DINNER')).toHaveLength(7);
    expect(screen.getByText('Lunch Recipe Day 1')).toBeInTheDocument();
    expect(screen.getByText('Dinner Recipe Day 7')).toBeInTheDocument();
  });

  it('locks a slot and regenerates single unlocked slot without altering others', async () => {
    vi.mocked(endpoints.getActiveMealPlan).mockResolvedValueOnce(mockMealPlan);
    vi.mocked(endpoints.regenerateSlot).mockResolvedValueOnce({
      ...mockMealPlan,
      plan: {
        ...mockMealPlan.plan,
        slots: mock14Slots.map((s) =>
          s.day === 1 && s.meal === 'DINNER'
            ? { ...s, recipe_title: 'Regenerated Dal Tadka' }
            : s
        ),
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <MealPlanView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Dinner Recipe Day 1')).toBeInTheDocument();
    });

    // Lock Day 1 Lunch
    const lockButtons = screen.getAllByLabelText('Lock slot');
    fireEvent.click(lockButtons[0]);

    // Verify lock button toggled
    expect(screen.getByLabelText('Unlock slot')).toBeInTheDocument();

    // Regenerate Day 1 Dinner
    const regenButtons = screen.getAllByLabelText('Regenerate this slot');
    // Day 1 Dinner is the second slot
    fireEvent.click(regenButtons[1]);

    await waitFor(() => {
      expect(endpoints.regenerateSlot).toHaveBeenCalledWith(
        'plan-14-slots',
        1,
        'DINNER'
      );
    });
  });

  it('displays low variety warning when repetition rules are relaxed', async () => {
    vi.mocked(endpoints.getActiveMealPlan).mockResolvedValueOnce({
      ...mockMealPlan,
      low_variety: true,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <MealPlanView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/low variety mode active/i)
      ).toBeInTheDocument();
    });
  });
});

