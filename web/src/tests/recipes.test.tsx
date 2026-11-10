import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RecipeDetailModal } from '@/features/recipes/RecipeDetailModal';

const baseRecipe = {
  id: 'aloo_gobi',
  title: 'Aloo Gobi',
  cuisine: 'North Indian',
  diet: 'VEGAN',
  spice_level: 'MEDIUM',
  cooking_time_minutes: 30,
  base_servings: 2,
  ingredients: [
    { ingredient_id: 'potato', display_name: 'Potato', qty: 2, unit: 'piece', is_optional: false },
    { ingredient_id: 'cauliflower', display_name: 'Cauliflower', qty: 300, unit: 'g', is_optional: false },
  ],
  steps: [
    { step_number: 1, instruction: 'Chop potato and cauliflower into florets.' },
    { step_number: 2, instruction: 'Heat oil, add cumin seeds, and sauté.' },
  ],
  nutrition: { calories: 220, protein_g: 5, carbs_g: 34, fat_g: 6 },
  source: 'CURATED',
};

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getRecipe: vi.fn().mockImplementation((_id, servings = 2) => {
      const scale = servings / 2;
      return Promise.resolve({
        ...baseRecipe,
        base_servings: servings,
        ingredients: baseRecipe.ingredients.map((ing) => ({
          ...ing,
          qty: ing.qty * scale,
        })),
      });
    }),
    recordRecipeCooked: vi.fn().mockResolvedValue({
      event_id: 'evt-123',
      recipe_id: 'aloo_gobi',
      servings: 4,
    }),
  },
}));

describe('Recipe Detail & Servings Scaler', () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  it('scales ingredient quantities dynamically when servings stepper is adjusted', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <RecipeDetailModal recipeId="aloo_gobi" onClose={() => {}} />
      </QueryClientProvider>
    );

    expect(await screen.findByText('Aloo Gobi')).toBeInTheDocument();

    // Default servings is 2
    expect(screen.getByText('2 pieces')).toBeInTheDocument();
    expect(screen.getByText('300 g')).toBeInTheDocument();

    // Increase servings by clicking '+' button
    const plusBtn = screen.getByLabelText(/Increase servings/i);
    fireEvent.click(plusBtn);

    // Servings increments to 3, triggering getRecipe with servings=3
    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('triggers cooked this action and shows confirmation feedback', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <RecipeDetailModal recipeId="aloo_gobi" onClose={() => {}} />
      </QueryClientProvider>
    );

    expect(await screen.findByText('Aloo Gobi')).toBeInTheDocument();

    const cookBtn = screen.getByRole('button', { name: /Cooked this!/i });
    fireEvent.click(cookBtn);

    expect(await screen.findByText(/Cooked! Inventory updated/i)).toBeInTheDocument();
  });
});

