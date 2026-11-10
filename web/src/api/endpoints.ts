import { api } from './client';
import {
  AuthResponse,
  AuthResponseSchema,
  DashboardData,
  DashboardResponseSchema,
  IngredientCatalogueItem,
  IngredientCatalogueItemSchema,
  InventoryItem,
  InventoryItemSchema,
  InventoryListResponse,
  InventoryListResponseSchema,
  InventoryUseResponse,
  InventoryUseResponseSchema,
  InventoryWasteResponse,
  InventoryWasteResponseSchema,
  MealPlan,
  MealPlanSchema,
  RecipeDetail,
  RecipeDetailSchema,
  RecommendationResponse,
  RecommendationResponseSchema,
  ScanResponse,
  ScanResponseSchema,
  ShoppingList,
  ShoppingListSchema,
  UserProfileResponse,
  UserProfileResponseSchema,
  UserPreferences,
  UserPreferencesSchema,
} from './schemas';
import { z } from 'zod';

export const endpoints = {
  // Auth
  register: (data: { email: string; password: string; display_name: string }) =>
    api.post<AuthResponse>('/auth/register', data, AuthResponseSchema),

  login: (data: { email: string; password: string }) =>
    api.post<AuthResponse>('/auth/login', data, AuthResponseSchema),

  logout: (refreshToken?: string) =>
    api.post<void>('/auth/logout', { refresh_token: refreshToken }),

  // User Profile & Preferences
  getMe: () => api.get<UserProfileResponse>('/me', UserProfileResponseSchema),

  updatePreferences: (preferences: UserPreferences) =>
    api.put<UserPreferences>('/me/preferences', preferences, UserPreferencesSchema),

  exportData: () => api.get<unknown>('/me/export'),

  deleteAccount: (password: string) =>
    api.delete<{ message: string; scheduled_deletion_at: string }>('/me', { password }),

  // Catalogue
  getIngredients: (query?: string, category?: string) => {
    const params = new URLSearchParams();
    if (query) params.set('query', query);
    if (category) params.set('category', category);
    const qs = params.toString();
    return api.get<IngredientCatalogueItem[]>(`/ingredients${qs ? `?${qs}` : ''}`, z.array(IngredientCatalogueItemSchema));
  },

  getRecipe: (recipeId: string, servings?: number) => {
    const qs = servings ? `?servings=${servings}` : '';
    return api.get<RecipeDetail>(`/recipes/${recipeId}${qs}`, RecipeDetailSchema);
  },

  // Inventory
  getInventory: (params?: { status?: string; storage?: string; sort?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.storage) searchParams.set('storage', params.storage);
    if (params?.sort) searchParams.set('sort', params.sort);
    const qs = searchParams.toString();
    return api.get<InventoryListResponse>(`/inventory${qs ? `?${qs}` : ''}`, InventoryListResponseSchema);
  },

  createInventoryItem: (item: {
    canonical_id: string;
    quantity: number;
    unit: string;
    storage: string;
    opened_on?: string | null;
  }) => api.post<InventoryItem>('/inventory', item, InventoryItemSchema),

  updateInventoryItem: (
    id: string,
    partial: { quantity?: number; storage?: string; opened_on?: string | null }
  ) => api.patch<InventoryItem>(`/inventory/${id}`, partial, InventoryItemSchema),

  useInventoryItem: (id: string, quantity: number) =>
    api.post<InventoryUseResponse>(`/inventory/${id}/use`, { quantity }, InventoryUseResponseSchema),

  wasteInventoryItem: (id: string, quantity: number) =>
    api.post<InventoryWasteResponse>(`/inventory/${id}/waste`, { quantity }, InventoryWasteResponseSchema),

  deleteInventoryItem: (id: string) => api.delete<void>(`/inventory/${id}`),

  // Scans
  uploadScan: (imageFile: File) => {
    const formData = new FormData();
    formData.append('image', imageFile);
    return api.upload<ScanResponse>('/scans', formData, ScanResponseSchema);
  },

  getScan: (scanId: string) => api.get<ScanResponse>(`/scans/${scanId}`, ScanResponseSchema),

  confirmScan: (
    scanId: string,
    items: Array<{
      candidate_id?: string | null;
      canonical_id: string;
      name: string;
      quantity: number;
      unit: string;
      storage: string;
      opened_on?: string | null;
    }>
  ) => api.post<{ created: InventoryItem[]; skipped: unknown[] }>(`/scans/${scanId}/confirm`, { items }),

  discardScan: (scanId: string) => api.delete<void>(`/scans/${scanId}`),

  // Recommendations & Cooking
  getRecommendations: (limit?: number, servings?: number) => {
    const searchParams = new URLSearchParams();
    if (limit) searchParams.set('limit', limit.toString());
    if (servings) searchParams.set('servings', servings.toString());
    const qs = searchParams.toString();
    return api.get<RecommendationResponse>(`/recommendations${qs ? `?${qs}` : ''}`, RecommendationResponseSchema);
  },

  recordRecipeCooked: (recipeId: string, data: { servings: number; rating?: number | null }) =>
    api.post<unknown>(`/recipes/${recipeId}/cooked`, data),

  // Meal Plans
  getMealPlan: (planId: string) => api.get<MealPlan>(`/meal-plans/${planId}`, MealPlanSchema),

  getActiveMealPlan: () => api.get<MealPlan>('/meal-plans/active', MealPlanSchema),

  createMealPlan: (data?: {
    start_date?: string | null;
    locked_slots?: Array<{ day: number; meal: string; recipe_id: string }>;
  }) => api.post<MealPlan>('/meal-plans', data || {}, MealPlanSchema),

  regenerateSlot: (planId: string, day: number, meal: string) =>
    api.post<MealPlan>(`/meal-plans/${planId}/slots/${day}/${meal}/regenerate`, {}, MealPlanSchema),

  archiveMealPlan: (planId: string) => api.delete<void>(`/meal-plans/${planId}`),

  // Shopping Lists
  getShoppingList: (listId: string) => api.get<ShoppingList>(`/shopping-lists/${listId}`, ShoppingListSchema),

  createShoppingList: (data: {
    source: 'PLAN' | 'RECIPES' | 'MANUAL';
    plan_id?: string | null;
    recipes?: Array<{ recipe_id: string; servings: number }> | null;
    manual_items?: Array<{ canonical_id: string; qty: number; unit: string }> | null;
  }) => api.post<ShoppingList>('/shopping-lists', data, ShoppingListSchema),

  patchShoppingItem: (
    listId: string,
    canonicalId: string,
    data: { bought: boolean; add_to_inventory?: boolean }
  ) => api.patch<ShoppingList>(`/shopping-lists/${listId}/items/${canonicalId}`, data, ShoppingListSchema),

  // Dashboard
  getDashboard: () => api.get<DashboardData>('/dashboard', DashboardResponseSchema),
};

