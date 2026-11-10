import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { StatusBadge } from '@/components/StatusBadge';
import { formatCurrencyINR } from '@/lib/formatting';
import {
  Camera,
  Flame,
  Clock,
  CheckCircle2,
  Calendar,
  TrendingDown,
  ChevronRight,
  Sparkles,
  Loader2,
  AlertTriangle,
} from 'lucide-react';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: endpoints.getDashboard,
    staleTime: 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
        <p className="text-sm text-gray-500 font-medium">Loading your kitchen dashboard…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <Card className="text-center py-8">
        <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-2" />
        <h3 className="text-base font-semibold text-gray-900">Could not load dashboard</h3>
        <p className="text-sm text-gray-500 mt-1 mb-4">Please check your connection and try again.</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </Card>
    );
  }

  const { status_counts, recommendations, active_plan, impact } = data;

  return (
    <div className="space-y-5">
      {/* Primary Scan Fridge CTA (PRD Section 12.3) */}
      <div className="bg-gradient-to-br from-brand-600 to-brand-800 rounded-3xl p-5 text-white shadow-md">
        <div className="flex items-start justify-between">
          <div>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-white/20 text-white backdrop-blur-xs mb-2">
              <Sparkles className="w-3 h-3" /> Quick Ingestion
            </span>
            <h2 className="text-xl font-bold tracking-tight">Got fresh groceries?</h2>
            <p className="text-xs text-brand-100 mt-0.5 max-w-[220px]">
              Snap a photo of your shelves or counter to auto-detect ingredients.
            </p>
          </div>
          <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center shrink-0">
            <Camera className="w-6 h-6 text-white" />
          </div>
        </div>
        <Button
          variant="secondary"
          size="md"
          onClick={() => navigate('/scan')}
          className="w-full mt-4 bg-white text-brand-800 hover:bg-brand-50 font-semibold shadow-xs"
        >
          Scan Fridge Now
        </Button>
      </div>

      {/* Freshness Status Counts */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Fridge Freshness</h3>
          <button
            onClick={() => navigate('/inventory')}
            className="text-xs font-semibold text-brand-600 flex items-center gap-0.5 hover:underline"
          >
            All Items ({status_counts.TOTAL}) <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="grid grid-cols-3 gap-2.5">
          <Card
            onClick={() => navigate('/inventory?status=USE_FIRST')}
            className="p-3 text-center border-red-100 bg-red-50/40 hover:bg-red-50 transition-colors"
          >
            <div className="w-7 h-7 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-1.5">
              <Flame className="w-4 h-4" />
            </div>
            <div className="text-2xl font-black text-red-700 leading-none">{status_counts.USE_FIRST}</div>
            <div className="text-[11px] font-semibold text-red-800 mt-1">Use First</div>
            <div className="text-[10px] text-red-600">≤ 1 day left</div>
          </Card>

          <Card
            onClick={() => navigate('/inventory?status=USE_SOON')}
            className="p-3 text-center border-amber-100 bg-amber-50/40 hover:bg-amber-50 transition-colors"
          >
            <div className="w-7 h-7 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center mx-auto mb-1.5">
              <Clock className="w-4 h-4" />
            </div>
            <div className="text-2xl font-black text-amber-800 leading-none">{status_counts.USE_SOON}</div>
            <div className="text-[11px] font-semibold text-amber-900 mt-1">Use Soon</div>
            <div className="text-[10px] text-amber-700">2-3 days</div>
          </Card>

          <Card
            onClick={() => navigate('/inventory?status=SAFE')}
            className="p-3 text-center border-emerald-100 bg-emerald-50/40 hover:bg-emerald-50 transition-colors"
          >
            <div className="w-7 h-7 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto mb-1.5">
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div className="text-2xl font-black text-emerald-800 leading-none">{status_counts.SAFE}</div>
            <div className="text-[11px] font-semibold text-emerald-900 mt-1">Safe</div>
            <div className="text-[10px] text-emerald-700">4+ days</div>
          </Card>
        </div>
      </div>

      {/* Month-to-date Impact Card */}
      <Card className="bg-white border-brand-100 p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand-100 text-brand-700 flex items-center justify-center">
              <TrendingDown className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-gray-900 leading-none">Monthly Food & Cost Savings</h4>
              <p className="text-[11px] text-gray-500 mt-0.5">Calculated from your cooked & used items</p>
            </div>
          </div>
          <span className="px-2 py-0.5 text-[10px] font-medium bg-gray-100 text-gray-600 rounded-md">
            Estimate
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-100">
          <div>
            <div className="text-xs text-gray-500">Waste Prevented</div>
            <div className="text-lg font-extrabold text-brand-700 mt-0.5">
              {impact.waste_prevented_kg} kg
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Money Saved</div>
            <div className="text-lg font-extrabold text-emerald-700 mt-0.5">
              {formatCurrencyINR(impact.money_saved_inr)}
            </div>
          </div>
        </div>
      </Card>

      {/* Active Meal Plan Summary */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Today's Meals</h3>
          <button
            onClick={() => navigate('/plan')}
            className="text-xs font-semibold text-brand-600 flex items-center gap-0.5 hover:underline"
          >
            Full Week Plan <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {active_plan && active_plan.today_meals && active_plan.today_meals.length > 0 ? (
          <div className="space-y-2">
            {active_plan.today_meals.map((meal: { meal: string; recipe_id: string; recipe_title: string; servings: number }, idx: number) => (
              <Card
                key={idx}
                onClick={() => navigate(`/recipes/${meal.recipe_id}`)}
                className="p-3.5 flex items-center justify-between hover:border-brand-300 transition-colors"
              >
                <div>
                  <span className="text-[10px] font-bold text-brand-700 uppercase tracking-wider px-2 py-0.5 rounded-full bg-brand-50">
                    {meal.meal}
                  </span>
                  <h4 className="text-sm font-bold text-gray-900 mt-1">{meal.recipe_title}</h4>
                  <p className="text-xs text-gray-500">{meal.servings} servings</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400" />
              </Card>
            ))}
          </div>
        ) : (
          <Card className="text-center py-5">
            <Calendar className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-xs text-gray-600 mb-3">No meals scheduled for today.</p>
            <Button variant="outline" size="sm" onClick={() => navigate('/plan')}>
              Generate 7-Day Plan
            </Button>
          </Card>
        )}
      </div>

      {/* Top Recommendations */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Recommended Tonight</h3>
          <button
            onClick={() => navigate('/recommendations')}
            className="text-xs font-semibold text-brand-600 flex items-center gap-0.5 hover:underline"
          >
            View All <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {recommendations && recommendations.length > 0 ? (
          <div className="space-y-3">
            {recommendations.map((rec) => (
              <Card
                key={rec.recipe_id}
                onClick={() => navigate(`/recipes/${rec.recipe_id}`)}
                className="p-4 hover:border-brand-300 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="text-sm font-bold text-gray-900">{rec.title}</h4>
                    <div className="flex items-center gap-2 text-xs text-gray-500 mt-0.5">
                      <span>{rec.cuisine}</span>
                      <span>•</span>
                      <span>{rec.cooking_time_minutes} mins</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-brand-50 text-brand-700 border border-brand-200">
                      {rec.match_percent}% match
                    </span>
                  </div>
                </div>

                <p className="text-xs text-gray-600 mt-2 bg-gray-50 p-2 rounded-xl">
                  {rec.reason}
                </p>

                {rec.uses_expiring && rec.uses_expiring.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2.5">
                    {rec.uses_expiring.map((u, i) => (
                      <StatusBadge
                        key={i}
                        status={u.status}
                        label={`Uses ${u.canonical_id.replace('_', ' ')}`}
                        size="sm"
                      />
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        ) : (
          <Card className="text-center py-5">
            <p className="text-xs text-gray-500">Scan your fridge or add items to unlock personalized recommendations.</p>
          </Card>
        )}
      </div>
    </div>
  );
};

