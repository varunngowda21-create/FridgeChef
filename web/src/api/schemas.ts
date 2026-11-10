import { z } from 'zod';

// Auth & User
export const UserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  display_name: z.string(),
  created_at: z.string(),
});

export const AuthResponseSchema = z.object({
  user: UserSchema,
  access_token: z.string(),
  refresh_token: z.string().nullable().optional(),
});

export const UserPreferencesSchema = z.object({
  household_size: z.number().int().min(1).max(10),
  diet: z.enum(['VEGAN', 'VEGETARIAN', 'EGGLESS', 'NON_VEGETARIAN']),
  spice_level: z.enum(['MILD', 'MEDIUM', 'HOT']),
  cuisines: z.array(z.string()),
  max_cooking_time: z.number().int().positive(),
  allergies: z.array(z.string()),
  avoided_ingredients: z.array(z.string()),
  version: z.number().optional(),
});

export const UserProfileResponseSchema = z.object({
  id: z.string(),
  email: z.string(),
  display_name: z.string(),
  created_at: z.string(),
  preferences: UserPreferencesSchema.nullable().optional(),
});

// Catalogue
export const IngredientCatalogueItemSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  category: z.string(),
  default_unit: z.string(),
  price_inr_per_kg: z.number().default(0),
  aliases: z.array(z.string()).default([]),
});

// Robust non-negative decimal number parser accepting number or stringified decimal
export const decimalNumber = z
  .union([
    z.number(),
    z.string().trim().regex(/^-?\d+(\.\d+)?$/, 'Must be a valid decimal number').transform((val) => parseFloat(val)),
  ])
  .pipe(z.number().nonnegative());

// Inventory
export const InventoryItemSchema = z.object({
  id: z.string(),
  user_id: z.string().optional(),
  ingredient_id: z.string().nullable().optional(),
  display_name: z.string(),
  quantity: decimalNumber,
  unit: z.string(),
  storage: z.enum(['FRIDGE', 'FREEZER', 'PANTRY', 'COUNTER']),
  added_on: z.string(),
  opened_on: z.string().nullable().optional(),
  shelf_life_days_estimate: z.number().nullable().optional(),
  expires_on: z.string().nullable().optional(),
  days_left: z.number(),
  days_left_display: z.string(),
  status: z.enum(['USE_FIRST', 'USE_SOON', 'SAFE']),
  archived_at: z.string().nullable().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});

export const InventoryListResponseSchema = z.object({
  items: z.array(InventoryItemSchema),
  next_cursor: z.string().nullable().optional(),
});

export const InventoryUseResponseSchema = z.object({
  item: InventoryItemSchema,
  action_logged: z.string().nullable().optional(),
  quantity_used: decimalNumber,
  is_archived: z.boolean(),
});

export const InventoryWasteResponseSchema = z.object({
  item: InventoryItemSchema,
  action_logged: z.string(),
  quantity_wasted: decimalNumber,
  estimated_value_inr: decimalNumber,
  is_archived: z.boolean(),
});

export type InventoryUseResponse = z.infer<typeof InventoryUseResponseSchema>;
export type InventoryWasteResponse = z.infer<typeof InventoryWasteResponseSchema>;

// Scanning
export const ScanCandidateSchema = z.object({
  candidate_id: z.string(),
  name: z.string(),
  canonical_id: z.string().nullable(),
  quantity: decimalNumber.nullable().optional(),
  unit: z.string().default('piece'),
  storage_guess: z.string().default('FRIDGE'),
  confidence: z.enum(['HIGH', 'MEDIUM', 'LOW']),
  needs_review: z.boolean().default(false),
  visible_note: z.string().nullable().optional(),
});

export const ScanResponseSchema = z.object({
  scan_id: z.string(),
  status: z.string().optional(),
  expires_at: z.string(),
  image_quality: z.string(),
  image_quality_note: z.string().nullable().optional(),
  candidates: z.array(ScanCandidateSchema),
});

// Recipes & Recommendations
export const UsesExpiringItemSchema = z.object({
  canonical_id: z.string(),
  status: z.string(),
  days_left: z.number(),
});

export const MissingIngredientSchema = z.object({
  canonical_id: z.string(),
  qty: decimalNumber,
  unit: z.string(),
  est_cost_inr: decimalNumber,
});

export const RecommendationItemSchema = z.object({
  recipe_id: z.string(),
  title: z.string(),
  cuisine: z.string(),
  cooking_time_minutes: z.number(),
  servings: z.number(),
  match_percent: z.number(),
  source: z.string(),
  uses_expiring: z.array(UsesExpiringItemSchema).default([]),
  missing: z.array(MissingIngredientSchema).default([]),
  missing_cost_inr: decimalNumber,
  reason: z.string(),
});

export const RecommendationResponseSchema = z.object({
  degraded: z.boolean().default(false),
  generated_at: z.string().optional(),
  cache: z.string().optional(),
  items: z.array(RecommendationItemSchema),
});

export const RecipeIngredientDetailSchema = z.object({
  canonical_id: z.string().optional(),
  ingredient_id: z.string().optional(),
  display_name: z.string(),
  qty: decimalNumber,
  unit: z.string(),
  is_optional: z.boolean().default(false),
});

export const RecipeStepSchema = z.object({
  step_number: z.number(),
  instruction: z.string(),
  time_minutes: z.number().nullable().optional(),
});

export const RecipeNutritionSchema = z.object({
  kcal: z.number().optional(),
  calories: z.number().optional(),
  protein_g: z.number().optional(),
  carbs_g: z.number().optional(),
  fat_g: z.number().optional(),
  fiber_g: z.number().optional(),
}).passthrough();

export const RecipeDetailSchema = z.object({
  id: z.string(),
  title: z.string(),
  cuisine: z.string(),
  diet: z.string(),
  spice_level: z.string(),
  cooking_time_minutes: z.number(),
  base_servings: z.number(),
  scaled_servings: z.number().optional(),
  ingredients: z.array(RecipeIngredientDetailSchema),
  steps: z.union([z.array(z.string()), z.array(RecipeStepSchema)]),
  nutrition_per_serving: RecipeNutritionSchema.optional().nullable(),
  tags: z.array(z.string()).default([]),
  source: z.string().optional(),
});

// Meal Planning
export const MealSlotSchema = z.object({
  day: z.number(),
  date: z.string(),
  meal: z.string(),
  recipe_id: z.string(),
  recipe_title: z.string(),
  servings: z.number(),
  prioritised_ingredients: z.array(z.string()).default([]),
  waste_prevented_g: z.number().default(0),
});

export const MealPlanSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  start_date: z.string(),
  status: z.string(),
  low_variety: z.boolean(),
  plan: z.object({
    slots: z.array(MealSlotSchema).default([]),
    shopping_list: z.array(z.any()).default([]),
    total_waste_prevented_kg: z.number().default(0),
  }),
  created_at: z.string(),
});

// Shopping List
export const ShoppingListItemSchema = z.object({
  canonical_id: z.string(),
  display_name: z.string(),
  category: z.string(),
  quantity: decimalNumber,
  unit: z.string(),
  est_cost_inr: decimalNumber,
  bought: z.boolean().default(false),
});

export const ShoppingListSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  source: z.string(),
  items: z.array(ShoppingListItemSchema).default([]),
  total_est_cost_inr: decimalNumber.default(0),
  created_at: z.string(),
});

// Dashboard
export const DashboardResponseSchema = z.object({
  status_counts: z.object({
    USE_FIRST: z.number().default(0),
    USE_SOON: z.number().default(0),
    SAFE: z.number().default(0),
    TOTAL: z.number().default(0),
  }),
  recommendations: z.array(RecommendationItemSchema).default([]),
  active_plan: z.object({
    id: z.string(),
    start_date: z.string(),
    days_count: z.number().default(7),
    low_variety: z.boolean().default(false),
    today_meals: z.array(z.any()).default([]),
  }).nullable().optional(),
  impact: z.object({
    waste_prevented_kg: z.number().default(0),
    food_wasted_kg: z.number().default(0),
    money_saved_inr: z.number().default(0),
    is_estimate: z.boolean().default(true),
  }),
});

export type User = z.infer<typeof UserSchema>;
export type AuthResponse = z.infer<typeof AuthResponseSchema>;
export type UserPreferences = z.infer<typeof UserPreferencesSchema>;
export type UserProfileResponse = z.infer<typeof UserProfileResponseSchema>;
export type IngredientCatalogueItem = z.infer<typeof IngredientCatalogueItemSchema>;
export type InventoryItem = z.infer<typeof InventoryItemSchema>;
export type InventoryListResponse = z.infer<typeof InventoryListResponseSchema>;
export type ScanCandidate = z.infer<typeof ScanCandidateSchema>;
export type ScanResponse = z.infer<typeof ScanResponseSchema>;
export type RecommendationItem = z.infer<typeof RecommendationItemSchema>;
export type RecommendationResponse = z.infer<typeof RecommendationResponseSchema>;
export type RecipeDetail = z.infer<typeof RecipeDetailSchema>;
export type MealSlot = z.infer<typeof MealSlotSchema>;
export type MealPlan = z.infer<typeof MealPlanSchema>;
export type ShoppingListItem = z.infer<typeof ShoppingListItemSchema>;
export type ShoppingList = z.infer<typeof ShoppingListSchema>;
export type DashboardData = z.infer<typeof DashboardResponseSchema>;

