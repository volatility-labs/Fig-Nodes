// components/Toast.tsx
// Renders a notification from the store and auto-dismisses after 5s.

import { useEffect } from 'react';
import { useGraphStore } from '../stores/graphStore';

export function Toast() {
  const notification = useGraphStore((s) => s.notification);
  const clearNotification = useGraphStore((s) => s.clearNotification);

  useEffect(() => {
    if (!notification) return;
    const timer = setTimeout(clearNotification, 5000);
    return () => clearTimeout(timer);
  }, [notification, clearNotification]);

  if (!notification) return null;

  const colorMap = {
    error: { bg: '#3a1111', border: '#ef5350', text: '#ff8a80' },
    warning: { bg: '#3a2e11', border: '#ff9800', text: '#ffcc80' },
    info: { bg: '#112a3a', border: '#42a5f5', text: '#90caf9' },
  };

  const colors = colorMap[notification.type];

  return (
    <div
      className="fig-toast"
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        padding: '10px 16px',
        borderRadius: 6,
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        color: colors.text,
        fontSize: 13,
        maxWidth: 400,
        zIndex: 5000,
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        cursor: 'pointer',
      }}
      onClick={clearNotification}
    >
      {notification.message}
    </div>
  );
}
