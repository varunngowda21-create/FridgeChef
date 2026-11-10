import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { StatusBadge } from '@/components/StatusBadge';
import { RecipeDetailModal } from '@/features/recipes/RecipeDetailModal';
import { formatCurrencyINR } from '@/lib/formatting';
import {
  Clock,
  Sparkles,
  AlertTriangle,
  Loader2,
  ChevronRight,
  Filter,
} from 'lucide-react';

export const RecommendationsList: React.FC = () => {
  const [selectedRecipeId, setSelectedRecipeId] = useState<string | null>(null);
  const [maxTimeFilter, setMaxTimeFilter] = useState<number | null>(null);
  const [cuisineFilter, setCuisineFilter] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['recommendations'],
    queryFn: () => endpoints.getRecommendations(10),
  });

  const recipes = data?.items || [];

  const filteredRecipes = recipes.filter((rec) => {
    if (maxTimeFilter && rec.cooking_time_minutes > maxTimeFilter) return false;
    if (cuisineFilter && rec.cuisine.toLowerCase() !== cuisineFilter.toLowerCase()) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">Recipe Recommendations</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Ranked to prioritize ingredients expiring first in your fridge
        </p>
      </div>

      {data?.degraded && (
        <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>Curated recipes only. AI generator is currently in offline mode.</span>
        </div>
      )}

      {/* Filter chips (PRD Section 12.3) */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar text-xs">
        <span className="text-gray-400 flex items-center gap-1 font-medium pl-1">
          <Filter className="w-3.5 h-3.5" /> Filters:
        </span>
        <button
          type="button"
          onClick={() => {
            setMaxTimeFilter(null);
            setCuisineFilter(null);
          }}
          className={`px-3 py-1.5 rounded-full border transition-colors touch-target ${
            !maxTimeFilter && !cuisineFilter
              ? 'bg-brand-600 text-white border-brand-600 font-semibold'
              : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
          }`}
        >
          All
        </button>

        <button
          type="button"
          onClick={() => setMaxTimeFilter(maxTimeFilter === 30 ? null : 30)}
          className={`px-3 py-1.5 rounded-full border transition-colors touch-target ${
            maxTimeFilter === 30
              ? 'bg-brand-600 text-white border-brand-600 font-semibold'
              : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
          }`}
        >
          ≤ 30 mins
        </button>

        {['North Indian', 'South Indian'].map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setCuisineFilter(cuisineFilter === c ? null : c)}
            className={`px-3 py-1.5 rounded-full border transition-colors touch-target ${
              cuisineFilter === c
                ? 'bg-brand-600 text-white border-brand-600 font-semibold'
                : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
          <p className="text-xs text-gray-500 font-medium">Scoring recipes against your pantry…</p>
        </div>
      ) : error ? (
        <Card className="text-center py-8">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
          <p className="text-sm font-semibold text-gray-800">Could not load recommendations</p>
          <Button variant="outline" size="sm" onClick={() => refetch()} className="mt-3">
            Retry
          </Button>
        </Card>
      ) : filteredRecipes.length === 0 ? (
        <Card className="text-center py-12 px-4">
          <Sparkles className="w-10 h-10 text-gray-300 mx-auto mb-2" />
          <h3 className="text-base font-bold text-gray-800">No matching recipes</h3>
          <p className="text-xs text-gray-500 mt-1 max-w-xs mx-auto">
            {maxTimeFilter || cuisineFilter
              ? 'No recipes match your active filter filters. Try resetting the filters.'
              : 'Add more ingredients to your fridge to see customized recipes.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredRecipes.map((rec) => (
            <Card
              key={rec.recipe_id}
              onClick={() => setSelectedRecipeId(rec.recipe_id)}
              className="p-4 hover:border-brand-300 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="text-sm font-bold text-gray-900">{rec.title}</h4>
                  <div className="flex items-center gap-2 text-xs text-gray-500 mt-0.5">
                    <span>{rec.cuisine}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-gray-400" />
                      {rec.cooking_time_minutes} mins
                    </span>
                  </div>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-brand-50 text-brand-700 border border-brand-200">
                  {rec.match_percent}% match
                </span>
              </div>

              {/* Templated Reason string per PRD Section 6.5 & 11.6 */}
              <p className="text-xs text-gray-600 mt-2 bg-gray-50 p-2.5 rounded-xl leading-relaxed">
                {rec.reason}
              </p>

              {/* Expiring Ingredients Used Badges */}
              {rec.uses_expiring && rec.uses_expiring.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {rec.uses_expiring.map((u, i) => (
                    <StatusBadge
                      key={i}
                      status={u.status}
                      label={`Uses ${u.canonical_id.replace('_', ' ')} (${u.days_left === 0 ? 'today' : `${u.days_left}d`})`}
                      size="sm"
                    />
                  ))}
                </div>
              )}

              {/* Missing ingredients count & cost */}
              <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-gray-100 text-xs">
                <span className="text-gray-500">
                  {rec.missing.length === 0 ? (
                    <span className="text-emerald-700 font-semibold">All ingredients in fridge!</span>
                  ) : (
                    <span>
                      Missing {rec.missing.length} items (est.{' '}
                      <span className="font-semibold text-gray-800">
                        {formatCurrencyINR(rec.missing_cost_inr)}
                      </span>
                      )
                    </span>
                  )}
                </span>
                <span className="text-brand-600 font-semibold flex items-center gap-0.5">
                  Cook <ChevronRight className="w-3.5 h-3.5" />
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Recipe Detail Modal */}
      {selectedRecipeId && (
        <RecipeDetailModal
          recipeId={selectedRecipeId}
          onClose={() => setSelectedRecipeId(null)}
        />
      )}
    </div>
  );
};

