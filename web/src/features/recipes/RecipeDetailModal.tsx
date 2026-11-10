import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { Modal } from '@/components/Modal';
import { Button } from '@/components/Button';
import { formatQuantity } from '@/lib/formatting';
import {
  Clock,
  Users,
  CheckCircle2,
  ChefHat,
  Star,
  Loader2,
  AlertCircle,
  Flame,
} from 'lucide-react';

interface RecipeDetailModalProps {
  recipeId: string | null;
  onClose: () => void;
}

export const RecipeDetailModal: React.FC<RecipeDetailModalProps> = ({ recipeId, onClose }) => {
  const queryClient = useQueryClient();
  const [servings, setServings] = useState<number>(2);
  const [rating, setRating] = useState<number | null>(5);
  const [cookedSuccess, setCookedSuccess] = useState(false);
  const [checkedSteps, setCheckedSteps] = useState<Record<number, boolean>>({});

  const { data: recipe, isLoading, error } = useQuery({
    queryKey: ['recipe', recipeId, servings],
    queryFn: () => {
      if (!recipeId) throw new Error('Missing recipeId');
      return endpoints.getRecipe(recipeId, servings);
    },
    enabled: !!recipeId,
    placeholderData: (prev) => prev,
  });

  const cookMutation = useMutation({
    mutationFn: () => {
      if (!recipeId) throw new Error('No recipe');
      return endpoints.recordRecipeCooked(recipeId, {
        servings,
        rating: rating || undefined,
      });
    },
    onSuccess: () => {
      setCookedSuccess(true);
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
    },
  });

  const toggleStep = (stepIdx: number) => {
    setCheckedSteps((prev) => ({ ...prev, [stepIdx]: !prev[stepIdx] }));
  };

  if (!recipeId) return null;

  return (
    <Modal
      isOpen={!!recipeId}
      onClose={onClose}
      title={recipe?.title || 'Recipe Details'}
      footer={
        cookedSuccess ? (
          <div className="flex items-center justify-between w-full">
            <span className="text-xs font-semibold text-brand-700 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-brand-600" />
              Cooked! Inventory updated.
            </span>
            <Button variant="primary" size="sm" onClick={onClose}>
              Done
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between w-full gap-3">
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  className="p-1 text-gray-300 hover:text-amber-400 touch-target flex items-center justify-center cursor-pointer"
                  aria-label={`Rate ${star} stars`}
                >
                  <Star
                    className={`w-5 h-5 ${
                      (rating || 0) >= star ? 'text-amber-400 fill-amber-400' : 'text-gray-300'
                    }`}
                  />
                </button>
              ))}
            </div>

            <Button
              variant="primary"
              size="md"
              onClick={() => cookMutation.mutate()}
              isLoading={cookMutation.isPending}
              icon={<ChefHat className="w-4 h-4" />}
              className="font-semibold"
            >
              Cooked this!
            </Button>
          </div>
        )
      }
    >
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
          <p className="text-xs text-gray-500 font-medium">Loading recipe details…</p>
        </div>
      ) : error || !recipe ? (
        <div className="text-center py-8">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
          <p className="text-sm font-semibold text-gray-800">Could not load recipe details</p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Metadata chips */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-full bg-gray-100 font-medium text-gray-700">
              {recipe.cuisine}
            </span>
            <span className="px-2.5 py-1 rounded-full bg-gray-100 font-medium text-gray-700 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-gray-500" />
              {recipe.cooking_time_minutes} mins
            </span>
            <span className="px-2.5 py-1 rounded-full bg-brand-50 text-brand-800 font-medium">
              {recipe.diet}
            </span>
          </div>

          {/* Servings Stepper (PRD Section 12.3) */}
          <div className="flex items-center justify-between p-3.5 rounded-2xl bg-gray-50 border border-gray-100">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-brand-600" />
              <span className="text-xs font-semibold text-gray-800">Servings:</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setServings(Math.max(1, servings - 1))}
                className="w-8 h-8 rounded-lg bg-white border border-gray-200 text-gray-800 font-bold flex items-center justify-center touch-target active:bg-gray-100"
                aria-label="Decrease servings"
              >
                -
              </button>
              <span className="w-8 text-center font-bold text-sm text-gray-900" aria-label="Current servings">{servings}</span>
              <button
                type="button"
                onClick={() => setServings(Math.min(24, servings + 1))}
                className="w-8 h-8 rounded-lg bg-white border border-gray-200 text-gray-800 font-bold flex items-center justify-center touch-target active:bg-gray-100"
                aria-label="Increase servings"
              >
                +
              </button>
            </div>
          </div>

          {/* Ingredients Checklist */}
          <div>
            <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-2.5">
              Ingredients ({recipe.ingredients.length})
            </h4>
            <div className="space-y-1.5">
              {recipe.ingredients.map((ing, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between py-1.5 px-3 rounded-xl bg-gray-50/70 text-xs"
                >
                  <span className="font-medium text-gray-800">
                    {ing.display_name} {ing.is_optional && <span className="text-gray-400 text-[10px]">(optional)</span>}
                  </span>
                  <span className="font-bold text-brand-700">
                    {formatQuantity(ing.qty, ing.unit)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Cooking Steps */}
          <div>
            <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-2.5">
              Instructions
            </h4>
            <div className="space-y-2.5">
              {recipe.steps.map((step, idx) => {
                const stepInstruction = typeof step === 'string' ? step : step.instruction;
                const stepNum = typeof step === 'string' ? idx + 1 : step.step_number;

                return (
                  <div
                    key={idx}
                    onClick={() => toggleStep(idx)}
                    className={`p-3 rounded-xl border text-xs cursor-pointer transition-colors flex items-start gap-3 ${
                      checkedSteps[idx]
                        ? 'bg-brand-50/40 border-brand-200 text-gray-500 line-through'
                        : 'bg-white border-gray-200 text-gray-800'
                    }`}
                  >
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                        checkedSteps[idx]
                          ? 'bg-brand-600 text-white'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {stepNum}
                    </span>
                    <span className="flex-1 leading-relaxed">{stepInstruction}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Nutrition Estimate Label (PRD Section 12.3) */}
          {recipe.nutrition_per_serving && (() => {
            const nut = recipe.nutrition_per_serving;
            return (
              <div className="p-3 bg-amber-50/50 rounded-2xl border border-amber-100">
                <div className="text-[11px] font-semibold text-amber-900 mb-1 flex items-center gap-1">
                  <Flame className="w-3.5 h-3.5 text-amber-600" />
                  Nutrition Estimate (per serving)
                </div>
                <div className="grid grid-cols-4 gap-2 text-center text-[11px] text-gray-700 pt-1">
                  <div>
                    <div className="font-bold text-gray-900">{nut?.kcal ?? nut?.calories ?? '—'}</div>
                    <div className="text-[10px] text-gray-500">kcal</div>
                  </div>
                  <div>
                    <div className="font-bold text-gray-900">{nut?.protein_g ? `${nut.protein_g}g` : '—'}</div>
                    <div className="text-[10px] text-gray-500">Protein</div>
                  </div>
                  <div>
                    <div className="font-bold text-gray-900">{nut?.carbs_g ? `${nut.carbs_g}g` : '—'}</div>
                    <div className="text-[10px] text-gray-500">Carbs</div>
                  </div>
                  <div>
                    <div className="font-bold text-gray-900">{nut?.fat_g ? `${nut.fat_g}g` : '—'}</div>
                    <div className="text-[10px] text-gray-500">Fat</div>
                  </div>
                </div>
                <p className="text-[10px] text-gray-400 text-center mt-1.5 italic">
                  Values are reference estimates based on ingredients table.
                </p>
              </div>
            );
          })()}
        </div>
      )}
    </Modal>
  );
};

