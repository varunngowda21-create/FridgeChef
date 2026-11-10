import React, { createContext, useContext, useEffect, useState } from 'react';
import { endpoints } from '@/api/endpoints';
import { tokenStorage, subscribeAuthChange } from '@/api/client';
import { queryClient } from '@/lib/queryClient';
import { User, UserPreferences } from '@/api/schemas';

interface AuthContextType {
  user: User | null;
  preferences: UserPreferences | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  updateUserPreferences: (prefs: UserPreferences) => Promise<void>;
  refetchUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchProfile = async () => {
    try {
      const data = await endpoints.getMe();
      setUser({
        id: data.id,
        email: data.email,
        display_name: data.display_name,
        created_at: data.created_at,
      });
      setPreferences(data.preferences || null);
    } catch {
      setUser(null);
      setPreferences(null);
      tokenStorage.clear();
      queryClient.clear();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Attempt initial session restore via httpOnly cookie or active in-memory token
    fetchProfile();

    const unsubscribe = subscribeAuthChange((isAuthed) => {
      if (!isAuthed) {
        setUser(null);
        setPreferences(null);
        queryClient.clear();
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const login = async (email: string, password: string) => {
    const res = await endpoints.login({ email, password });
    tokenStorage.setAccessToken(res.access_token);
    setUser(res.user);
    // Fetch profile and preferences
    try {
      const profile = await endpoints.getMe();
      setPreferences(profile.preferences || null);
    } catch {
      // ignore
    }
  };

  const register = async (email: string, password: string, displayName: string) => {
    const res = await endpoints.register({ email, password, display_name: displayName });
    tokenStorage.setAccessToken(res.access_token);
    setUser(res.user);
  };

  const logout = async () => {
    try {
      await endpoints.logout();
    } catch {
      // ignore
    } finally {
      tokenStorage.clear();
      setUser(null);
      setPreferences(null);
      queryClient.clear();
    }
  };

  const updateUserPreferences = async (newPrefs: UserPreferences) => {
    const updated = await endpoints.updatePreferences(newPrefs);
    setPreferences(updated);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        preferences,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        updateUserPreferences,
        refetchUser: fetchProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

