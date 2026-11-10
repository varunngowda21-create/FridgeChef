import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/features/auth/AuthContext';
import { endpoints } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { Modal } from '@/components/Modal';
import { UserPreferences } from '@/api/schemas';
import {
  Sliders,
  Download,
  Trash2,
  LogOut,
  Check,
  ShieldCheck,
} from 'lucide-react';

export const SettingsView: React.FC = () => {
  const { user, preferences, updateUserPreferences, logout } = useAuth();
  const navigate = useNavigate();

  const [householdSize, setHouseholdSize] = useState(preferences?.household_size || 2);
  const [diet, setDiet] = useState<UserPreferences['diet']>(preferences?.diet || 'VEGETARIAN');
  const [spiceLevel, setSpiceLevel] = useState<UserPreferences['spice_level']>(preferences?.spice_level || 'MEDIUM');
  const [cuisines, setCuisines] = useState<string[]>(preferences?.cuisines || ['North Indian', 'South Indian']);
  const [maxCookingTime, setMaxCookingTime] = useState(preferences?.max_cooking_time || 45);

  // Sync state when preferences are loaded or updated
  React.useEffect(() => {
    if (preferences) {
      setHouseholdSize(preferences.household_size);
      setDiet(preferences.diet);
      setSpiceLevel(preferences.spice_level);
      setCuisines(preferences.cuisines);
      setMaxCookingTime(preferences.max_cooking_time);
    }
  }, [preferences]);

  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const availableCuisines = ['North Indian', 'South Indian', 'Maharashtrian', 'Gujarati', 'Punjabi', 'Bengali'];

  const toggleCuisine = (c: string) => {
    if (cuisines.includes(c)) {
      if (cuisines.length > 1) {
        setCuisines(cuisines.filter((x) => x !== c));
      }
    } else {
      setCuisines([...cuisines, c]);
    }
  };

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      await updateUserPreferences({
        household_size: householdSize,
        diet,
        spice_level: spiceLevel,
        cuisines,
        max_cooking_time: maxCookingTime,
        allergies: preferences?.allergies || [],
        avoided_ingredients: preferences?.avoided_ingredients || [],
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      // ignore
    } finally {
      setIsSaving(false);
    }
  };

  const handleExportData = async () => {
    setIsExporting(true);
    try {
      const data = await endpoints.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fridgechef-data-${user?.email || 'user'}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to export data.';
      alert(message);
    } finally {
      setIsExporting(false);
    }
  };

  const handleDeleteAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeleteError(null);
    if (!deletePassword) {
      setDeleteError('Please enter your password to confirm deletion.');
      return;
    }

    setIsDeleting(true);
    try {
      await endpoints.deleteAccount(deletePassword);
      await logout();
      navigate('/login');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete account.';
      setDeleteError(message);
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-5 pb-12">
      <div>
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">Settings & Preferences</h2>
        <p className="text-xs text-gray-500 mt-0.5">Customize your household, diet, and manage privacy</p>
      </div>

      {/* User profile card */}
      <Card className="p-4 flex items-center gap-3">
        <div className="w-12 h-12 rounded-2xl bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-lg">
          {user?.display_name?.charAt(0).toUpperCase() || 'U'}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-bold text-gray-900 truncate">{user?.display_name}</h3>
          <p className="text-xs text-gray-500 truncate">{user?.email}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={async () => {
            await logout();
            navigate('/login');
          }}
          icon={<LogOut className="w-3.5 h-3.5" />}
        >
          Sign Out
        </Button>
      </Card>

      {/* Preferences Form */}
      <Card className="p-4 space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider flex items-center gap-1.5">
            <Sliders className="w-4 h-4 text-brand-600" /> Meal Preferences
          </h3>
          {saveSuccess && (
            <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" /> Saved!
            </span>
          )}
        </div>

        <form onSubmit={handleSavePreferences} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Household Size: <span className="font-bold text-brand-700">{householdSize} persons</span>
            </label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setHouseholdSize(Math.max(1, householdSize - 1))}
                className="w-10 h-10 rounded-xl bg-gray-100 text-gray-800 font-bold flex items-center justify-center touch-target"
                aria-label="Decrease household size"
              >
                -
              </button>
              <div className="flex-1 text-center font-bold text-lg text-gray-900 bg-gray-50 py-1.5 rounded-xl border border-gray-200">
                {householdSize}
              </div>
              <button
                type="button"
                onClick={() => setHouseholdSize(Math.min(10, householdSize + 1))}
                className="w-10 h-10 rounded-xl bg-gray-100 text-gray-800 font-bold flex items-center justify-center touch-target"
                aria-label="Increase household size"
              >
                +
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5">Dietary Choice</label>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {[
                { id: 'VEGETARIAN', label: 'Vegetarian' },
                { id: 'NON_VEGETARIAN', label: 'Non-Vegetarian' },
                { id: 'EGGLESS', label: 'Eggless' },
                { id: 'VEGAN', label: 'Vegan' },
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setDiet(item.id as UserPreferences['diet'])}
                  className={`p-2.5 rounded-xl border text-center touch-target cursor-pointer ${
                    diet === item.id
                      ? 'border-brand-600 bg-brand-50 text-brand-900 font-bold'
                      : 'border-gray-200 bg-white text-gray-700'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5">Spice Level</label>
            <div className="grid grid-cols-3 gap-2 text-xs">
              {['MILD', 'MEDIUM', 'HOT'].map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setSpiceLevel(lvl as UserPreferences['spice_level'])}
                  className={`py-2 px-1 rounded-xl border text-center touch-target cursor-pointer ${
                    spiceLevel === lvl
                      ? 'border-brand-600 bg-brand-50 text-brand-900 font-bold'
                      : 'border-gray-200 bg-white text-gray-700'
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5">Preferred Cuisines</label>
            <div className="grid grid-cols-2 gap-1.5 text-xs">
              {availableCuisines.map((c) => {
                const selected = cuisines.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleCuisine(c)}
                    className={`p-2 rounded-xl border text-left flex items-center justify-between touch-target ${
                      selected
                        ? 'border-brand-600 bg-brand-50 text-brand-900 font-semibold'
                        : 'border-gray-200 bg-white text-gray-600'
                    }`}
                  >
                    <span>{c}</span>
                    {selected && <Check className="w-3.5 h-3.5 text-brand-600 shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Max Cooking Time: <span className="font-bold text-brand-700">{maxCookingTime} mins</span>
            </label>
            <input
              type="range"
              min="15"
              max="90"
              step="15"
              value={maxCookingTime}
              onChange={(e) => setMaxCookingTime(parseInt(e.target.value, 10))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isSaving}
            className="w-full font-semibold"
            onClick={handleSavePreferences}
          >
            Save Preferences
          </Button>

          {saveSuccess && (
            <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 text-xs font-semibold flex items-center justify-center gap-1.5">
              <Check className="w-4 h-4 text-emerald-600" />
              Preferences updated successfully!
            </div>
          )}
        </form>
      </Card>

      {/* Privacy and Account Actions (PRD Section 11.2 & NFR-030) */}
      <Card className="p-4 space-y-3">
        <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider border-b border-gray-100 pb-2 flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-emerald-600" /> Data Privacy & Account
        </h3>

        <div className="space-y-2 pt-1">
          <Button
            variant="outline"
            size="md"
            onClick={handleExportData}
            isLoading={isExporting}
            className="w-full justify-start text-xs font-semibold"
            icon={<Download className="w-4 h-4 text-brand-600" />}
          >
            Export All My Data (JSON)
          </Button>

          <Button
            variant="outline"
            size="md"
            onClick={() => setShowDeleteModal(true)}
            className="w-full justify-start text-xs font-semibold text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
            icon={<Trash2 className="w-4 h-4 text-red-500" />}
          >
            Delete Account Permanently
          </Button>
        </div>
      </Card>

      {/* Delete Account Modal */}
      {showDeleteModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowDeleteModal(false)}
          title="Delete Account"
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowDeleteModal(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteAccount}
                isLoading={isDeleting}
              >
                Delete My Account
              </Button>
            </div>
          }
        >
          <form onSubmit={handleDeleteAccount} className="space-y-3">
            {deleteError && (
              <div className="p-3 rounded-xl bg-red-50 text-red-700 text-xs">{deleteError}</div>
            )}
            <p className="text-xs text-gray-600 leading-relaxed">
              Are you sure you want to delete your account? All inventory data, meal plans, and scan images will be immediately and permanently purged per PRD NFR-030.
            </p>
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Enter your password to confirm:
              </label>
              <input
                type="password"
                required
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
              />
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};

