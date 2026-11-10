import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RecipeDetailModal } from '@/features/recipes/RecipeDetailModal';
import { endpoints } from '@/api/endpoints';

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getRecipe: vi.fn(),
    recordRecipeCooked: vi.fn(),
  },
}));

const mockRecipe = {
  id: 'paneer-bhurji',
  title: 'Paneer Bhurji',
  cuisine: 'North Indian',
  diet: 'VEGETARIAN',
  spice_level: 'MEDIUM',
  cooking_time_minutes: 20,
  base_servings: 2,
  scaled_servings: 2,
  ingredients: [
    {
      canonical_id: 'paneer',
      display_name: 'Paneer',
      qty: 200,
      unit: 'g',
      is_optional: false,
    },
    {
      canonical_id: 'onion',
      display_name: 'Onion',
      qty: 1,
      unit: 'piece',
      is_optional: false,
    },
  ],
  steps: ['Crumble paneer.', 'Sauté onions and spices.', 'Fold in paneer.'],
  nutrition_per_serving: {
    kcal: 280,
    protein_g: 16,
    carbs_g: 8,
    fat_g: 20,
    fiber_g: 2,
  },
  tags: ['quick', 'high-protein'],
  source: 'CURATED',
};

describe('Recipe Cooking Actions & Servings Bounds', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    vi.clearAllMocks();
  });

  it('records cooking event with chosen servings and 5-star rating', async () => {
    vi.mocked(endpoints.getRecipe).mockResolvedValue(mockRecipe);
    vi.mocked(endpoints.recordRecipeCooked).mockResolvedValueOnce({
      event_id: 'cook-evt-1',
      recipe_id: 'paneer-bhurji',
      servings: 2,
      rating: 5,
      decremented_items_count: 2,
      waste_prevented_logged: true,
      created_at: '2026-10-28T12:00:00Z',
    });

    render(
      <QueryClientProvider client={queryClient}>
        <RecipeDetailModal recipeId="paneer-bhurji" onClose={vi.fn()} />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Paneer Bhurji')).toBeInTheDocument();
    });

    // Select 5-star rating
    const star5 = screen.getByLabelText('Rate 5 stars');
    fireEvent.click(star5);

    // Click "Cooked this!"
    fireEvent.click(screen.getByRole('button', { name: /cooked this!/i }));

    await waitFor(() => {
      expect(endpoints.recordRecipeCooked).toHaveBeenCalledWith('paneer-bhurji', {
        servings: 2,
        rating: 5,
      });
      expect(screen.getByText(/cooked! inventory updated/i)).toBeInTheDocument();
    });
  });

  it('enforces servings bounds between 1 and 24', async () => {
    vi.mocked(endpoints.getRecipe).mockResolvedValue(mockRecipe);

    render(
      <QueryClientProvider client={queryClient}>
        <RecipeDetailModal recipeId="paneer-bhurji" onClose={vi.fn()} />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Paneer Bhurji')).toBeInTheDocument();
    });

    const decreaseBtn = screen.getByLabelText(/decrease servings/i);
    // Base servings is 2. Click decrease once -> 1
    fireEvent.click(decreaseBtn);
    await waitFor(() => {
      expect(screen.getByLabelText(/current servings/i)).toHaveTextContent('1');
    });
  });
});
