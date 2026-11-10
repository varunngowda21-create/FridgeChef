import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { endpoints } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { StatusBadge } from '@/components/StatusBadge';
import { Modal } from '@/components/Modal';
import { formatQuantity } from '@/lib/formatting';
import { InventoryItem } from '@/api/schemas';
import {
  Search,
  Plus,
  Trash2,
  AlertTriangle,
  Loader2,
  Package,
} from 'lucide-react';

export const InventoryList: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const activeTab = searchParams.get('status') || 'ALL';
  const [searchQuery, setSearchQuery] = useState('');

  // Modals state
  const [actionItem, setActionItem] = useState<{
    item: InventoryItem;
    type: 'use' | 'waste' | 'edit';
  } | null>(null);
  const [actionQty, setActionQty] = useState<number>(1);

  const [showAddModal, setShowAddModal] = useState(false);
  const [addName, setAddName] = useState('');
  const [addQty, setAddQty] = useState(1);
  const [addUnit, setAddUnit] = useState('piece');
  const [addStorage, setAddStorage] = useState('FRIDGE');
  const [addError, setAddError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['inventory', activeTab],
    queryFn: () => endpoints.getInventory({ status: activeTab === 'ALL' ? undefined : activeTab }),
  });

  const recordUseMutation = useMutation({
    mutationFn: ({ id, qty }: { id: string; qty: number }) => endpoints.useInventoryItem(id, qty),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setActionItem(null);
    },
  });

  const wasteMutation = useMutation({
    mutationFn: ({ id, qty }: { id: string; qty: number }) => endpoints.wasteInventoryItem(id, qty),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setActionItem(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => endpoints.deleteInventoryItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const cid = addName.trim().toLowerCase().replace(/\s+/g, '_');
      return endpoints.createInventoryItem({
        canonical_id: cid,
        quantity: addQty,
        unit: addUnit,
        storage: addStorage,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setShowAddModal(false);
      setAddName('');
      setAddQty(1);
      setAddError(null);
    },
    onError: (err: Error) => {
      setAddError(err.message || 'Failed to add item.');
    },
  });

  const items = data?.items || [];
  const filteredItems = items.filter((item) =>
    item.display_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Title & Add CTA */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">Kitchen Inventory</h2>
          <p className="text-xs text-gray-500 mt-0.5">Track remaining shelf-life and reduce waste</p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => setShowAddModal(true)}
          icon={<Plus className="w-4 h-4" />}
        >
          Add Item
        </Button>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search items in your fridge…"
          className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>

      {/* Freshness Filter Tabs (PRD Section 12.3) */}
      <div className="flex bg-gray-100 p-1 rounded-xl text-xs font-semibold gap-1">
        {[
          { id: 'ALL', label: 'All' },
          { id: 'USE_FIRST', label: 'Use First' },
          { id: 'USE_SOON', label: 'Use Soon' },
          { id: 'SAFE', label: 'Safe' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => {
              if (tab.id === 'ALL') {
                searchParams.delete('status');
              } else {
                searchParams.set('status', tab.id);
              }
              setSearchParams(searchParams);
            }}
            className={`flex-1 py-1.5 px-2 rounded-lg text-center transition-all touch-target cursor-pointer ${
              activeTab === tab.id ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Items List */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
          <p className="text-sm text-gray-500 font-medium">Checking freshness…</p>
        </div>
      ) : error ? (
        <Card className="text-center py-8">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
          <p className="text-sm font-semibold text-gray-800">Error loading inventory</p>
        </Card>
      ) : filteredItems.length === 0 ? (
        <Card className="text-center py-12 px-4">
          <Package className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-800">No items found</h3>
          <p className="text-xs text-gray-500 mt-1 max-w-xs mx-auto">
            {searchQuery
              ? `No ingredients match "${searchQuery}".`
              : activeTab !== 'ALL'
              ? `You have zero items in the ${activeTab.replace('_', ' ')} category.`
              : 'Your fridge is currently empty. Tap "Add Item" or "Scan" to start tracking.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-2.5">
          {filteredItems.map((item) => (
            <Card key={item.id} className="p-3.5 flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-gray-900 truncate">{item.display_name}</h4>
                  <StatusBadge status={item.status} size="sm" />
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                  <span className="font-semibold text-gray-800">
                    {formatQuantity(item.quantity, item.unit)}
                  </span>
                  <span>•</span>
                  <span>{item.storage}</span>
                  <span>•</span>
                  <span className="text-gray-600 font-medium">{item.days_left_display}</span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setActionItem({ item, type: 'use' });
                    setActionQty(item.quantity);
                  }}
                  className="px-2.5 py-1 text-xs"
                >
                  Used
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setActionItem({ item, type: 'waste' });
                    setActionQty(item.quantity);
                  }}
                  className="px-2.5 py-1 text-xs text-amber-700 hover:text-amber-800"
                >
                  Wasted
                </Button>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(item.id)}
                  className="p-2 text-gray-400 hover:text-red-600 rounded-lg touch-target flex items-center justify-center"
                  aria-label={`Delete ${item.display_name}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Action modal for Use or Waste quantity deduction */}
      {actionItem && (
        <Modal
          isOpen={true}
          onClose={() => setActionItem(null)}
          title={actionItem.type === 'use' ? `Used ${actionItem.item.display_name}` : `Wasted ${actionItem.item.display_name}`}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setActionItem(null)}>
                Cancel
              </Button>
              <Button
                variant={actionItem.type === 'use' ? 'primary' : 'danger'}
                size="sm"
                onClick={() => {
                  if (actionItem.type === 'use') {
                    recordUseMutation.mutate({ id: actionItem.item.id, qty: actionQty });
                  } else {
                    wasteMutation.mutate({ id: actionItem.item.id, qty: actionQty });
                  }
                }}
                isLoading={recordUseMutation.isPending || wasteMutation.isPending}
              >
                Confirm
              </Button>
            </div>
          }
        >
          <div className="space-y-4">
            <p className="text-xs text-gray-600">
              {actionItem.type === 'use'
                ? 'Record how much of this item was consumed. Used items before expiry count towards your monthly food waste prevention!'
                : 'Record how much of this item spoiled or was discarded. This helps monitor food waste accurately.'}
            </p>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Quantity ({actionItem.item.unit})
              </label>
              <input
                type="number"
                step="any"
                min="0.1"
                max={actionItem.item.quantity}
                value={actionQty}
                onChange={(e) => setActionQty(parseFloat(e.target.value) || 1)}
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
              />
              <p className="text-[11px] text-gray-400 mt-1">Available in fridge: {actionItem.item.quantity} {actionItem.item.unit}</p>
            </div>
          </div>
        </Modal>
      )}

      {/* Add New Item Modal */}
      {showAddModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowAddModal(false)}
          title="Add Fridge Item"
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowAddModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => createMutation.mutate()}
                isLoading={createMutation.isPending}
              >
                Add Item
              </Button>
            </div>
          }
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
            className="space-y-4"
          >
            {addError && (
              <div className="p-3 rounded-xl bg-red-50 text-red-700 text-xs">{addError}</div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Ingredient</label>
              <input
                type="text"
                required
                value={addName}
                onChange={(e) => setAddName(e.target.value)}
                placeholder="e.g. Tomato, Paneer, Spinach"
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Quantity</label>
                <input
                  type="number"
                  step="any"
                  min="0.1"
                  required
                  value={addQty}
                  onChange={(e) => setAddQty(parseFloat(e.target.value) || 1)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Unit</label>
                <select
                  value={addUnit}
                  onChange={(e) => setAddUnit(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm bg-white"
                >
                  <option value="piece">piece</option>
                  <option value="g">g</option>
                  <option value="ml">ml</option>
                  <option value="packet">packet</option>
                  <option value="container">container</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Storage Location</label>
              <select
                value={addStorage}
                onChange={(e) => setAddStorage(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm bg-white"
              >
                <option value="FRIDGE">FRIDGE</option>
                <option value="FREEZER">FREEZER</option>
                <option value="PANTRY">PANTRY</option>
                <option value="COUNTER">COUNTER</option>
              </select>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
