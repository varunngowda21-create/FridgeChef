import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Home,
  Package,
  Camera,
  UtensilsCrossed,
  Calendar,
  ShoppingCart,
  Settings as SettingsIcon,
} from 'lucide-react';
export const Layout: React.FC = () => {
  const navigate = useNavigate();

  const navItems = [
    { to: '/', label: 'Home', icon: Home },
    { to: '/inventory', label: 'Inventory', icon: Package },
    { to: '/scan', label: 'Scan', icon: Camera, highlight: true },
    { to: '/recommendations', label: 'Recipes', icon: UtensilsCrossed },
    { to: '/plan', label: 'Plan', icon: Calendar },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 text-gray-900 pb-20">
      {/* Top Header */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-xs border-b border-gray-100 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/')}>
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-lg shadow-xs">
            FC
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-900 tracking-tight leading-none">FridgeChef</h1>
            <p className="text-[10px] text-gray-500 font-medium">Smart AI Kitchen</p>
          </div>
        </div>

        {/* Top bar actions: Shopping and Settings */}
        <div className="flex items-center gap-1">
          <NavLink
            to="/shopping"
            className={({ isActive }) =>
              `p-2.5 rounded-xl touch-target flex items-center justify-center transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
              }`
            }
            aria-label="Shopping list"
          >
            <ShoppingCart className="w-5 h-5" />
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `p-2.5 rounded-xl touch-target flex items-center justify-center transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
              }`
            }
            aria-label="Settings"
          >
            <SettingsIcon className="w-5 h-5" />
          </NavLink>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-lg mx-auto w-full px-4 py-4">
        <Outlet />
      </main>

      {/* Mobile-first Bottom Navigation Bar (PRD Section 12.4) */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-gray-200 px-2 py-1 max-w-lg mx-auto"
        aria-label="Main Navigation"
      >
        <div className="flex items-center justify-around">
          {navItems.map((item) => {
            const Icon = item.icon;
            if (item.highlight) {
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className="flex flex-col items-center justify-center -mt-5"
                  aria-label={item.label}
                >
                  <div className="w-12 h-12 rounded-full bg-brand-600 text-white flex items-center justify-center shadow-lg active:scale-95 transition-transform touch-target">
                    <Icon className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-medium text-gray-700 mt-0.5">{item.label}</span>
                </NavLink>
              );
            }

            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex flex-col items-center justify-center py-1.5 px-2 rounded-lg touch-target min-w-[56px] transition-colors ${
                    isActive ? 'text-brand-600 font-semibold' : 'text-gray-500 hover:text-gray-900'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={`w-5 h-5 ${isActive ? 'stroke-[2.5]' : 'stroke-2'}`} />
                    <span className="text-[10px] mt-1">{item.label}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </nav>
    </div>
  );
};

