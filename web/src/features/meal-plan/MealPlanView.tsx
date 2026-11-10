import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { endpoints } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { RecipeDetailModal } from '@/features/recipes/RecipeDetailModal';
import {
  Calendar,
  RefreshCw,
  Lock,
  Unlock,
  ShoppingCart,
  TrendingDown,
  AlertCircle,
  Loader2,
  Sparkles,
} from 'lucide-react';

export const MealPlanView: React.FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [selectedRecipeId, setSelectedRecipeId] = useState<string | null>(null);
  const [lockedSlots, setLockedSlots] = useState<Record<string, boolean>>({});

  const { data: plan, isLoading, error } = useQuery({
    queryKey: ['active-meal-plan'],
    queryFn: endpoints.getActiveMealPlan,
    retry: false,
  });

  const generatePlanMutation = useMutation({
    mutationFn: () => {
      // Build locked slots if any
      const lockedList: Array<{ day: number; meal: string; recipe_id: string }> = [];
      if (plan) {
        plan.plan.slots.forEach((s) => {
          const key = `${s.day}-${s.meal}`;
          if (lockedSlots[key]) {
            lockedList.push({ day: s.day, meal: s.meal, recipe_id: s.recipe_id });
          }
        });
      }
      return endpoints.createMealPlan({ locked_slots: lockedList.length ? lockedList : undefined });
    },
    onSuccess: (newPlan) => {
      queryClient.setQueryData(['active-meal-plan'], newPlan);
      queryClient.invalidateQueries({ queryKey: ['active-meal-plan'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const regenSlotMutation = useMutation({
    mutationFn: ({ day, meal }: { day: number; meal: string }) => {
      if (!plan) throw new Error('No plan');
      return endpoints.regenerateSlot(plan.id, day, meal);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['active-meal-plan'], updated);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const createShoppingMutation = useMutation({
    mutationFn: () => {
      if (!plan) throw new Error('No plan');
      return endpoints.createShoppingList({ source: 'PLAN', plan_id: plan.id });
    },
    onSuccess: () => {
      navigate('/shopping');
    },
  });

  const toggleLock = (day: number, meal: string) => {
    const key = `${day}-${meal}`;
    setLockedSlots((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
        <p className="text-sm text-gray-500 font-medium">Generating greedy lookahead plan…</p>
      </div>
    );
  }

  if (error || !plan) {
    return (
      <div className="space-y-4 text-center py-12 px-4">
        <Calendar className="w-12 h-12 text-brand-600 mx-auto mb-2" />
        <h2 className="text-xl font-bold text-gray-900">No Active Meal Plan</h2>
        <p className="text-xs text-gray-500 max-w-sm mx-auto">
          Generate an intelligent 7-day meal plan that uses expiring items first and minimizes food waste.
        </p>
        <Button
          variant="primary"
          size="lg"
          onClick={() => generatePlanMutation.mutate()}
          isLoading={generatePlanMutation.isPending}
          className="font-semibold mt-2"
          icon={<Sparkles className="w-5 h-5" />}
        >
          Generate 7-Day Plan
        </Button>
      </div>
    );
  }

  const slots = plan.plan.slots || [];
  // Group slots by day
  const daysMap: Record<number, typeof slots> = {};
  slots.forEach((s) => {
    if (!daysMap[s.day]) daysMap[s.day] = [];
    daysMap[s.day].push(s);
  });

  return (
    <div className="space-y-4 pb-12">
      {/* Title & Summary */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">7-Day Meal Plan</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Starts {new Date(plan.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => generatePlanMutation.mutate()}
          isLoading={generatePlanMutation.isPending}
          icon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          New Plan
        </Button>
      </div>

      {/* Expected Waste Prevented banner */}
      <div className="p-3.5 bg-brand-50 border border-brand-200 rounded-2xl flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-brand-600" />
          <span className="text-brand-900 font-semibold">
            Expected waste prevented: {plan.plan.total_waste_prevented_kg || 0} kg
          </span>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => createShoppingMutation.mutate()}
          isLoading={createShoppingMutation.isPending}
          icon={<ShoppingCart className="w-3.5 h-3.5" />}
          className="text-xs py-1 px-2.5"
        >
          Get Shopping List
        </Button>
      </div>

      {plan.low_variety && (
        <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>Low variety mode active: repetition rules were relaxed to fit your inventory and preferences.</span>
        </div>
      )}

      {/* 7-Day Grid (14 slots: Lunch and Dinner) */}
      <div className="space-y-3">
        {slots.length === 0 ? (
          <Card className="p-8 text-center text-gray-500">
            <p className="text-sm">No meal slots found in this plan.</p>
          </Card>
        ) : (
          Object.entries(daysMap)
            .sort(([a], [b]) => Number(a) - Number(b))
            .map(([dayStr, daySlots]) => {
          const dayNum = parseInt(dayStr, 10);
          const firstSlot = daySlots[0];
          const dateStr = firstSlot?.date
            ? new Date(firstSlot.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
            : `Day ${dayNum}`;

          return (
            <Card key={dayNum} className="p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <span className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                  {dateStr}
                </span>
                <span className="text-[11px] text-gray-400 font-medium">Day {dayNum} of 7</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {daySlots.map((slot) => {
                  const key = `${slot.day}-${slot.meal}`;
                  const isLocked = !!lockedSlots[key];
                  const isRegenerating =
                    regenSlotMutation.isPending &&
                    regenSlotMutation.variables?.day === slot.day &&
                    regenSlotMutation.variables?.meal === slot.meal;

                  return (
                    <div
                      key={slot.meal}
                      className="p-3 rounded-xl bg-gray-50 border border-gray-100 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-brand-700 uppercase tracking-wider px-2 py-0.5 rounded-full bg-brand-100">
                            {slot.meal}
                          </span>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => toggleLock(slot.day, slot.meal)}
                              className={`p-1.5 rounded-lg touch-target flex items-center justify-center cursor-pointer ${
                                isLocked ? 'text-brand-600 bg-brand-50' : 'text-gray-400 hover:text-gray-600'
                              }`}
                              aria-label={isLocked ? 'Unlock slot' : 'Lock slot'}
                            >
                              {isLocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
                            </button>
                            <button
                              type="button"
                              disabled={isLocked || isRegenerating}
                              onClick={() => regenSlotMutation.mutate({ day: slot.day, meal: slot.meal })}
                              className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 disabled:opacity-30 touch-target flex items-center justify-center cursor-pointer"
                              aria-label="Regenerate this slot"
                            >
                              <RefreshCw className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin text-brand-600' : ''}`} />
                            </button>
                          </div>
                        </div>

                        <h4
                          onClick={() => setSelectedRecipeId(slot.recipe_id)}
                          className="text-xs font-bold text-gray-900 mt-2 cursor-pointer hover:text-brand-700 truncate"
                        >
                          {slot.recipe_title}
                        </h4>
                        <p className="text-[11px] text-gray-500 mt-0.5">{slot.servings} servings</p>
                      </div>

                      {slot.prioritised_ingredients && slot.prioritised_ingredients.length > 0 && (
                        <div className="mt-2 text-[10px] text-amber-800 bg-amber-50/70 px-2 py-1 rounded-lg">
                          Prioritizes: {slot.prioritised_ingredients.join(', ')}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          );
        })
      )}
      </div>

      {selectedRecipeId && (
        <RecipeDetailModal
          recipeId={selectedRecipeId}
          onClose={() => setSelectedRecipeId(null)}
        />
      )}
    </div>
  );
};

