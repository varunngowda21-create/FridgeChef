import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/features/auth/AuthContext';
import { Layout } from './Layout';
import { Login } from '@/features/auth/Login';
import { Register } from '@/features/auth/Register';
import { Onboarding } from '@/features/onboarding/Onboarding';
import { Dashboard } from '@/features/dashboard/Dashboard';
import { ScanCamera } from '@/features/scan/ScanCamera';
import { VerifyCandidates } from '@/features/scan/VerifyCandidates';
import { InventoryList } from '@/features/inventory/InventoryList';
import { RecommendationsList } from '@/features/recommendations/RecommendationsList';
import { MealPlanView } from '@/features/meal-plan/MealPlanView';
import { ShoppingListView } from '@/features/shopping/ShoppingListView';
import { SettingsView } from '@/features/settings/SettingsView';
import { Loader2 } from 'lucide-react';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, preferences } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 gap-3">
        <Loader2 className="w-10 h-10 text-brand-600 animate-spin" />
        <p className="text-sm font-semibold text-gray-600">Loading FridgeChef…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Redirect to onboarding if preferences not yet configured
  if (!preferences && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
};

export const AppRouter: React.FC = () => {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        {/* Public auth routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Onboarding flow */}
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute>
              <Onboarding />
            </ProtectedRoute>
          }
        />

        {/* Authenticated Application Shell */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="inventory" element={<InventoryList />} />
          <Route path="scan" element={<ScanCamera />} />
          <Route path="scan/:scanId/verify" element={<VerifyCandidates />} />
          <Route path="recommendations" element={<RecommendationsList />} />
          <Route path="recipes/:recipeId" element={<RecommendationsList />} />
          <Route path="plan" element={<MealPlanView />} />
          <Route path="shopping" element={<ShoppingListView />} />
          <Route path="settings" element={<SettingsView />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

