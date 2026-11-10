import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { Modal } from '@/components/Modal';
import {
  Check,
  Plus,
  Trash2,
  Edit2,
  AlertCircle,
  Loader2,
} from 'lucide-react';

interface EditableCandidate {
  id: string;
  candidate_id?: string | null;
  name: string;
  canonical_id: string;
  quantity: number;
  unit: string;
  storage: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  selected: boolean;
  visible_note?: string | null;
}

export const VerifyCandidates: React.FC = () => {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();

  const [candidates, setCandidates] = useState<EditableCandidate[]>([]);
  const [editingItem, setEditingItem] = useState<EditableCandidate | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [manualName, setManualName] = useState('');
  const [manualCanonicalId, setManualCanonicalId] = useState('');
  const [manualQty, setManualQty] = useState(1);
  const [manualUnit, setManualUnit] = useState('piece');
  const [manualStorage, setManualStorage] = useState('FRIDGE');

  const [confirmError, setConfirmError] = useState<string | null>(null);

  const { isLoading, error } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: async () => {
      if (!scanId) throw new Error('Missing scanId');
      const data = await endpoints.getScan(scanId);
      // Map candidates: pre-uncheck LOW confidence per PRD Section 6.3 & 12.3
      const mapped: EditableCandidate[] = data.candidates.map((c, idx) => ({
        id: `cand-${idx}`,
        candidate_id: c.candidate_id,
        name: c.name,
        canonical_id: c.canonical_id || '',
        quantity: c.quantity || 1,
        unit: c.unit || 'piece',
        storage: c.storage_guess || 'FRIDGE',
        confidence: c.confidence,
        selected: c.confidence !== 'LOW',
        visible_note: c.visible_note,
      }));
      setCandidates(mapped);
      return data;
    },
    enabled: !!scanId,
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!scanId) return;
      const selected = candidates.filter((c) => c.selected);
      if (selected.length === 0) {
        throw new Error('Please select at least one item to save.');
      }
      const missingCanonical = selected.find((c) => !c.canonical_id || !c.canonical_id.trim());
      if (missingCanonical) {
        throw new Error(`Item "${missingCanonical.name}" requires a valid canonical ingredient ID before saving.`);
      }
      return endpoints.confirmScan(
        scanId,
        selected.map((item) => ({
          candidate_id: item.candidate_id,
          canonical_id: item.canonical_id,
          name: item.name,
          quantity: item.quantity,
          unit: item.unit,
          storage: item.storage,
        }))
      );
    },
    onSuccess: () => {
      navigate('/inventory');
    },
    onError: (err: Error) => {
      setConfirmError(err.message || 'Failed to confirm items.');
    },
  });

  const discardMutation = useMutation({
    mutationFn: async () => {
      if (!scanId) return;
      return endpoints.discardScan(scanId);
    },
    onSuccess: () => {
      navigate('/');
    },
  });

  const toggleSelect = (id: string) => {
    setCandidates((prev) =>
      prev.map((c) => (c.id === id ? { ...c, selected: !c.selected } : c))
    );
  };

  const removeCandidate = (id: string) => {
    setCandidates((prev) => prev.filter((c) => c.id !== id));
  };

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem) return;
    setCandidates((prev) =>
      prev.map((c) => (c.id === editingItem.id ? editingItem : c))
    );
    setEditingItem(null);
  };

  const handleAddManual = (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualName.trim()) return;
    const newItem: EditableCandidate = {
      id: `manual-${Date.now()}`,
      candidate_id: null,
      name: manualName.trim(),
      canonical_id: (manualCanonicalId || manualName).trim().toLowerCase().replace(/\s+/g, '_'),
      quantity: manualQty,
      unit: manualUnit,
      storage: manualStorage,
      confidence: 'HIGH',
      selected: true,
    };
    setCandidates((prev) => [...prev, newItem]);
    setShowAddModal(false);
    setManualName('');
    setManualCanonicalId('');
    setManualQty(1);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
        <Loader2 className="w-8 h-8 text-brand-600 animate-spin" />
        <p className="text-sm text-gray-500 font-medium">Loading detected items…</p>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="text-center py-8">
        <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-2" />
        <h3 className="text-base font-semibold text-gray-900">Scan expired or not found</h3>
        <p className="text-xs text-gray-500 mt-1 mb-4">Please take a new photo to scan your fridge.</p>
        <Button variant="primary" size="md" onClick={() => navigate('/scan')}>
          New Scan
        </Button>
      </Card>
    );
  }

  const selectedCount = candidates.filter((c) => c.selected).length;

  return (
    <div className="space-y-4 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 tracking-tight">Verify Items</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {selectedCount} of {candidates.length} items selected to add
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowAddModal(true)}
          icon={<Plus className="w-4 h-4" />}
        >
          Add Item
        </Button>
      </div>

      {confirmError && (
        <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
          <span>{confirmError}</span>
        </div>
      )}

      {/* Candidates list */}
      <div className="space-y-2">
        {candidates.map((item) => (
          <Card
            key={item.id}
            className={`p-3.5 transition-colors border ${
              item.selected ? 'border-brand-200 bg-white' : 'border-gray-200 bg-gray-50/60 opacity-75'
            }`}
          >
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={item.selected}
                onChange={() => toggleSelect(item.id)}
                className="mt-1 w-5 h-5 rounded-md border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer accent-brand-600"
                aria-label={`Select ${item.name}`}
              />

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-gray-900 truncate">{item.name}</h4>
                  <span
                    className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-md uppercase ${
                      item.confidence === 'HIGH'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : item.confidence === 'MEDIUM'
                        ? 'bg-amber-50 text-amber-700 border border-amber-200'
                        : 'bg-gray-100 text-gray-600 border border-gray-200'
                    }`}
                  >
                    {item.confidence}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                  <span className="font-medium text-gray-700">
                    {item.quantity} {item.unit}
                  </span>
                  <span>•</span>
                  <span>{item.storage}</span>
                </div>

                {item.visible_note && (
                  <p className="text-[11px] text-gray-400 mt-0.5 italic truncate">{item.visible_note}</p>
                )}
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => setEditingItem(item)}
                  className="p-2 text-gray-400 hover:text-gray-700 rounded-lg touch-target flex items-center justify-center"
                  aria-label={`Edit ${item.name}`}
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => removeCandidate(item.id)}
                  className="p-2 text-gray-400 hover:text-red-600 rounded-lg touch-target flex items-center justify-center"
                  aria-label={`Delete ${item.name}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Sticky Action Footer */}
      <div className="viewport-footer pt-3 bg-gray-50 flex items-center gap-2.5">
        <Button
          variant="outline"
          size="lg"
          onClick={() => discardMutation.mutate()}
          isLoading={discardMutation.isPending}
          className="flex-1"
          aria-label="Discard scan"
        >
          Discard Scan
        </Button>
        <Button
          variant="primary"
          size="lg"
          onClick={() => confirmMutation.mutate()}
          isLoading={confirmMutation.isPending}
          disabled={selectedCount === 0}
          className="flex-2 font-semibold"
          icon={<Check className="w-5 h-5" />}
        >
          Save ({selectedCount}) to Fridge
        </Button>
      </div>

      {/* Edit Candidate Modal */}
      {editingItem && (
        <Modal
          isOpen={true}
          onClose={() => setEditingItem(null)}
          title={`Edit ${editingItem.name}`}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditingItem(null)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={handleSaveEdit}>
                Done
              </Button>
            </div>
          }
        >
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Item Name</label>
              <input
                type="text"
                required
                value={editingItem.name}
                onChange={(e) => setEditingItem({ ...editingItem, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
              />
            </div>

            <div>
              <label htmlFor="edit-canonical-id" className="block text-xs font-semibold text-gray-700 mb-1">
                Canonical Ingredient ID
              </label>
              <input
                id="edit-canonical-id"
                aria-label="Canonical Ingredient ID"
                type="text"
                required
                value={editingItem.canonical_id}
                onChange={(e) => setEditingItem({ ...editingItem, canonical_id: e.target.value.toLowerCase() })}
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm bg-gray-50"
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
                  value={editingItem.quantity}
                  onChange={(e) => setEditingItem({ ...editingItem, quantity: parseFloat(e.target.value) || 1 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Unit</label>
                <select
                  value={editingItem.unit}
                  onChange={(e) => setEditingItem({ ...editingItem, unit: e.target.value })}
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
                value={editingItem.storage}
                onChange={(e) => setEditingItem({ ...editingItem, storage: e.target.value })}
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

      {/* Manual Add Item Modal */}
      {showAddModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowAddModal(false)}
          title="Add Missing Item"
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowAddModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={handleAddManual}>
                Add to List
              </Button>
            </div>
          }
        >
          <form onSubmit={handleAddManual} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Ingredient Name</label>
              <input
                type="text"
                required
                value={manualName}
                onChange={(e) => {
                  setManualName(e.target.value);
                  setManualCanonicalId(e.target.value.toLowerCase().replace(/\s+/g, '_'));
                }}
                placeholder="e.g. Ginger"
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
                  value={manualQty}
                  onChange={(e) => setManualQty(parseFloat(e.target.value) || 1)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Unit</label>
                <select
                  value={manualUnit}
                  onChange={(e) => setManualUnit(e.target.value)}
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
                value={manualStorage}
                onChange={(e) => setManualStorage(e.target.value)}
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

