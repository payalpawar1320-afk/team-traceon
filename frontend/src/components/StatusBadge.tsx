import React from 'react';

interface StatusBadgeProps {
  status: string;
  variant?: 'success' | 'warning' | 'danger' | 'neutral';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, variant }) => {
  let resolvedVariant = variant;

  if (!resolvedVariant) {
    const s = status.toLowerCase();
    if (s.includes('match') || s.includes('healthy') || s.includes('no indicator') || s.includes('success')) {
      resolvedVariant = 'success';
    } else if (s.includes('detected') || s.includes('mismatch') || s.includes('danger') || s.includes('fail')) {
      resolvedVariant = 'danger';
    } else if (s.includes('warning') || s.includes('degraded') || s.includes('unavailable')) {
      resolvedVariant = 'warning';
    } else {
      resolvedVariant = 'neutral';
    }
  }

  return <span className={`badge badge-${resolvedVariant}`}>{status}</span>;
};
