import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/features/auth/AuthContext';
import { Button } from '@/components/Button';
import { Check, ChevronRight, ChevronLeft, AlertCircle } from 'lucide-react';
import { UserPreferences } from '@/api/schemas';

export const Onboarding: React.FC = () => {
  const { preferences, updateUserPreferences } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [householdSize, setHouseholdSize] = useState(preferences?.household_size || 2);
  const [diet, setDiet] = useState<UserPreferences['diet']>(preferences?.diet || 'VEGETARIAN');
  const [spiceLevel, setSpiceLevel] = useState<UserPreferences['spice_level']>(preferences?.spice_level || 'MEDIUM');
  const [cuisines, setCuisines] = useState<string[]>(preferences?.cuisines?.length ? preferences.cuisines : ['North Indian', 'South Indian']);
  const [maxCookingTime, setMaxCookingTime] = useState(preferences?.max_cooking_time || 45);
  const [allergies, setAllergies] = useState<string[]>(preferences?.allergies || []);
  const [avoided, setAvoided] = useState<string[]>(preferences?.avoided_ingredients || []);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const availableCuisines = ['North Indian', 'South Indian', 'Maharashtrian', 'Gujarati', 'Punjabi', 'Bengali'];
  const commonAllergens = [
    { id: 'dairy', label: 'Dairy / Milk' },
    { id: 'peanuts', label: 'Peanuts' },
    { id: 'gluten', label: 'Gluten / Wheat' },
    { id: 'eggs', label: 'Eggs' },
    { id: 'soy', label: 'Soy' },
  ];
  const commonAvoided = [
    { id: 'onion', label: 'Onion' },
    { id: 'garlic', label: 'Garlic' },
    { id: 'mushroom', label: 'Mushroom' },
    { id: 'brinjal', label: 'Brinjal / Eggplant' },
  ];

  const toggleCuisine = (c: string) => {
    if (cuisines.includes(c)) {
      if (cuisines.length > 1) {
        setCuisines(cuisines.filter((x) => x !== c));
      }
    } else {
      setCuisines([...cuisines, c]);
    }
  };

  const toggleAllergy = (id: string) => {
    setAllergies((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleAvoided = (id: string) => {
    setAvoided((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleFinish = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      const payload: UserPreferences = {
        household_size: householdSize,
        diet,
        spice_level: spiceLevel,
        cuisines,
        max_cooking_time: maxCookingTime,
        allergies,
        avoided_ingredients: avoided,
      };
      await updateUserPreferences(payload);
      navigate('/');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save preferences. Please try again.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center px-4 py-8 max-w-md mx-auto">
      {/* Progress header */}
      <div className="mb-6">
        <div className="flex items-center justify-between text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          <span>Step {step} of 3</span>
          <span>{step === 1 ? 'Household & Diet' : step === 2 ? 'Cuisines & Spice' : 'Allergies & Time'}</span>
        </div>
        <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
          <div
            className="bg-brand-600 h-full transition-all duration-300"
            style={{ width: `${(step / 3) * 100}%` }}
          />
        </div>
      </div>

      <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100">
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* STEP 1: Household & Diet */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Household & Dietary Habits</h2>
              <p className="text-sm text-gray-500 mt-1">This helps us scale recipe portions and filter appropriate recipes.</p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">
                Household Size: <span className="text-brand-600 font-bold">{householdSize} {householdSize === 1 ? 'person' : 'people'}</span>
              </label>
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => setHouseholdSize(Math.max(1, householdSize - 1))}
                  className="w-12 h-12 text-lg font-bold"
                  aria-label="Decrease household size"
                >
                  -
                </Button>
                <div className="flex-1 text-center font-bold text-2xl text-gray-900 bg-gray-50 py-2 rounded-xl border border-gray-200">
                  {householdSize}
                </div>
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => setHouseholdSize(Math.min(10, householdSize + 1))}
                  className="w-12 h-12 text-lg font-bold"
                  aria-label="Increase household size"
                >
                  +
                </Button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">Dietary Choice</label>
              <div className="grid grid-cols-2 gap-2.5">
                {[
                  { id: 'VEGETARIAN', label: 'Vegetarian', desc: 'No meat or fish' },
                  { id: 'NON_VEGETARIAN', label: 'Non-Vegetarian', desc: 'Chicken, fish, meat' },
                  { id: 'EGGLESS', label: 'Eggless', desc: 'Veg + no eggs' },
                  { id: 'VEGAN', label: 'Vegan', desc: '100% plant based' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setDiet(item.id as UserPreferences['diet'])}
                    className={`p-3 rounded-xl border text-left transition-all touch-target cursor-pointer ${
                      diet === item.id
                        ? 'border-brand-600 bg-brand-50/70 text-brand-900 font-semibold ring-1 ring-brand-500'
                        : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <div className="text-sm font-medium">{item.label}</div>
                    <div className="text-[11px] text-gray-500 mt-0.5">{item.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Cuisines & Spice */}
        {step === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Flavors & Regional Cuisines</h2>
              <p className="text-sm text-gray-500 mt-1">Select the Indian regional styles you cook most often.</p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">Favorite Regional Cuisines</label>
              <div className="grid grid-cols-2 gap-2">
                {availableCuisines.map((c) => {
                  const selected = cuisines.includes(c);
                  return (
                    <button
                      key={c}
                      type="button"
                      onClick={() => toggleCuisine(c)}
                      className={`p-2.5 rounded-xl border text-sm flex items-center justify-between touch-target cursor-pointer ${
                        selected
                          ? 'border-brand-600 bg-brand-50 text-brand-900 font-medium'
                          : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <span>{c}</span>
                      {selected && <Check className="w-4 h-4 text-brand-600 shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">Spice Level Tolerance</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'MILD', label: 'Mild', icon: '🟢' },
                  { id: 'MEDIUM', label: 'Medium', icon: '🟠' },
                  { id: 'HOT', label: 'Spicy / Hot', icon: '🔴' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSpiceLevel(item.id as UserPreferences['spice_level'])}
                    className={`py-3 px-2 rounded-xl border text-center touch-target cursor-pointer ${
                      spiceLevel === item.id
                        ? 'border-brand-600 bg-brand-50 text-brand-900 font-semibold ring-1 ring-brand-500'
                        : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <div className="text-lg mb-1">{item.icon}</div>
                    <div className="text-xs">{item.label}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Allergies & Cooking Time */}
        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Allergies & Time Constraints</h2>
              <p className="text-sm text-gray-500 mt-1">We guarantee recipes never include your allergens or avoided ingredients.</p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">Common Allergens to Exclude</label>
              <div className="flex flex-wrap gap-2">
                {commonAllergens.map((alg) => {
                  const selected = allergies.includes(alg.id);
                  return (
                    <button
                      key={alg.id}
                      type="button"
                      onClick={() => toggleAllergy(alg.id)}
                      className={`px-3 py-1.5 rounded-full border text-xs font-medium transition-colors cursor-pointer ${
                        selected
                          ? 'bg-red-50 text-red-700 border-red-300 ring-1 ring-red-400'
                          : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {alg.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">Ingredients to Avoid (e.g. Jain style)</label>
              <div className="flex flex-wrap gap-2">
                {commonAvoided.map((av) => {
                  const selected = avoided.includes(av.id);
                  return (
                    <button
                      key={av.id}
                      type="button"
                      onClick={() => toggleAvoided(av.id)}
                      className={`px-3 py-1.5 rounded-full border text-xs font-medium transition-colors cursor-pointer ${
                        selected
                          ? 'bg-amber-50 text-amber-800 border-amber-300 ring-1 ring-amber-400'
                          : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {av.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-2">
                Max Weeknight Cooking Time: <span className="text-brand-600 font-bold">{maxCookingTime} mins</span>
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
              <div className="flex justify-between text-[11px] text-gray-400 mt-1">
                <span>15 mins</span>
                <span>30 mins</span>
                <span>45 mins</span>
                <span>60 mins</span>
                <span>90 mins</span>
              </div>
            </div>
          </div>
        )}

        {/* Navigation buttons */}
        <div className="flex items-center justify-between mt-8 pt-4 border-t border-gray-100">
          {step > 1 ? (
            <Button
              variant="outline"
              size="md"
              onClick={() => setStep(step - 1)}
              icon={<ChevronLeft className="w-4 h-4" />}
            >
              Back
            </Button>
          ) : (
            <div />
          )}

          {step < 3 ? (
            <Button
              variant="primary"
              size="md"
              onClick={() => setStep(step + 1)}
              className="gap-1 font-semibold"
            >
              <span>Next</span>
              <ChevronRight className="w-4 h-4" />
            </Button>
          ) : (
            <Button
              variant="primary"
              size="md"
              isLoading={isSubmitting}
              onClick={handleFinish}
              className="font-semibold"
            >
              Complete Setup
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

