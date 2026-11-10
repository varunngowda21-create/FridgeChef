import React from 'react';
import { AlertCircle, Clock, CheckCircle2 } from 'lucide-react';

export type FreshnessStatusType = 'USE_FIRST' | 'USE_SOON' | 'SAFE' | string;

interface StatusBadgeProps {
  status: FreshnessStatusType;
  label?: string;
  className?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  className = '',
  size = 'md',
}) => {
  const normStatus = (status || '').toUpperCase();

  const isFirst = normStatus === 'USE_FIRST';
  const isSoon = normStatus === 'USE_SOON';
  const isSafe = normStatus === 'SAFE';

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs gap-1' : 'px-2.5 py-1 text-xs gap-1.5 font-medium';

  let badgeColor = 'bg-gray-100 text-gray-800 border-gray-200';
  let icon = <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />;
  let defaultText = 'Safe';

  if (isFirst) {
    badgeColor = 'bg-red-50 text-red-700 border-red-200';
    icon = <AlertCircle className="w-3.5 h-3.5 text-red-600" aria-hidden="true" />;
    defaultText = 'Use First';
  } else if (isSoon) {
    badgeColor = 'bg-amber-50 text-amber-800 border-amber-200';
    icon = <Clock className="w-3.5 h-3.5 text-amber-600" aria-hidden="true" />;
    defaultText = 'Use Soon';
  } else if (isSafe) {
    badgeColor = 'bg-emerald-50 text-emerald-800 border-emerald-200';
    icon = <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" aria-hidden="true" />;
    defaultText = 'Safe';
  }

  const displayText = label || defaultText;

  return (
    <span
      className={`inline-flex items-center rounded-full border ${sizeClasses} ${badgeColor} ${className}`}
      role="status"
      aria-label={`Freshness status: ${displayText}`}
    >
      {icon}
      <span>{displayText}</span>
    </span>
  );
};

