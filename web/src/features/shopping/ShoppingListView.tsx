import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { formatCurrencyINR, formatQuantity } from '@/lib/formatting';
import { ShoppingListItem } from '@/api/schemas';
import {
  CheckCircle2,
  Loader2,
  PackagePlus,
} from 'lucide-react';

export const ShoppingListView: React.FC = () => {
  const queryClient = useQueryClient();
  const [autoAddInventory, setAutoAddInventory] = useState(true);

  // We fetch the most recent shopping list from user or active plan
  const { data: plan } = useQuery({
    queryKey: ['active-meal-plan'],
    queryFn: endpoints.getActiveMealPlan,
  });

  const { data: shoppingList, isLoading } = useQuery({
    queryKey: ['shopping-list', plan?.id],
    queryFn: async () => {
      if (!plan) return null;
      // Generate or retrieve list from plan
      return endpoints.createShoppingList({ source: 'PLAN', plan_id: plan.id });
    },
    enabled: !!plan?.id,
  });

  const toggleBoughtMutation = useMutation({
    mutationFn: ({
      listId,
      canonicalId,
      bought,
    }: {
      listId: string;
      canonicalId: string;
      bought: boolean;
    }) =>
      endpoints.patchShoppingItem(listId, canonicalId, {
        bought,
        add_to_inventory: bought ? autoAddInventory : false,
      }),
    onSuccess: (updatedList) => {
      queryClient.setQueryData(['shopping-list', plan?.id], updatedList);
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
        <p className="text-sm text-gray-500 font-medium">Aggregating shopping requirements…</p>
      </div>
    );
  }

  const items = shoppingList?.items || [];

  // Group items by category (PRD Section 6.7)
  const categoryMap: Record<string, ShoppingListItem[]> = {};
  items.forEach((item) => {
    const cat = item.category || 'General';
    if (!categoryMap[cat]) categoryMap[cat] = [];
    categoryMap[cat].push(item);
  });

  const boughtCount = items.filter((i) => i.bought).length;

  return (
    <div className="space-y-4 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">Shopping List</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {boughtCount} of {items.length} items purchased
          </p>
        </div>
      </div>

      {/* Auto-Add to inventory switch (PRD Section 6.7 & FR-062) */}
      <div className="p-3 bg-brand-50 border border-brand-200 rounded-2xl flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <PackagePlus className="w-4 h-4 text-brand-700 shrink-0" />
          <span className="text-brand-900 font-medium">
            Auto-add bought groceries to fridge inventory
          </span>
        </div>
        <input
          type="checkbox"
          checked={autoAddInventory}
          onChange={(e) => setAutoAddInventory(e.target.checked)}
          className="w-4 h-4 rounded text-brand-600 focus:ring-brand-500 cursor-pointer accent-brand-600"
          aria-label="Auto add to inventory"
        />
      </div>

      {items.length === 0 ? (
        <Card className="text-center py-12 px-4">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-2" />
          <h3 className="text-base font-bold text-gray-900">All Set!</h3>
          <p className="text-xs text-gray-500 mt-1 max-w-xs mx-auto">
            You currently have all required ingredients in your fridge for your scheduled meals.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {Object.entries(categoryMap).map(([category, catItems]) => (
            <div key={category} className="space-y-2">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider px-1">
                {category} ({catItems.length})
              </h3>
              <div className="space-y-1.5">
                {catItems.map((item) => (
                  <Card
                    key={item.canonical_id}
                    className={`p-3 flex items-center justify-between gap-3 transition-colors ${
                      item.bought ? 'bg-gray-50 border-gray-100 opacity-60' : 'bg-white border-gray-200'
                    }`}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <input
                        type="checkbox"
                        checked={item.bought}
                        onChange={() => {
                          if (!shoppingList) return;
                          toggleBoughtMutation.mutate({
                            listId: shoppingList.id,
                            canonicalId: item.canonical_id,
                            bought: !item.bought,
                          });
                        }}
                        className="w-5 h-5 rounded-md border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer accent-brand-600 shrink-0"
                        aria-label={`Mark ${item.display_name} as bought`}
                      />

                      <div className="flex-1 min-w-0">
                        <h4
                          className={`text-sm font-semibold text-gray-900 truncate ${
                            item.bought ? 'line-through text-gray-500' : ''
                          }`}
                        >
                          {item.display_name}
                        </h4>
                        <p className="text-xs text-gray-500">
                          {formatQuantity(item.quantity, item.unit)}
                        </p>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-xs font-bold text-gray-800">
                        {formatCurrencyINR(item.est_cost_inr)}
                      </span>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          ))}

          {/* Sticky Total Bar */}
          <div className="viewport-footer pt-3 bg-gray-50">
            <Card className="p-4 bg-brand-900 text-white flex items-center justify-between border-0 shadow-md">
              <div>
                <span className="text-xs text-brand-200">Total Estimated Cost</span>
                <div className="text-xl font-black text-white">
                  {formatCurrencyINR(shoppingList?.total_est_cost_inr || 0)}
                </div>
              </div>
              <span className="text-xs text-brand-200 font-medium">
                {items.length - boughtCount} items to buy
              </span>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
};

