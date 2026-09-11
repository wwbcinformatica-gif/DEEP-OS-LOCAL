import React, { useEffect, useState } from 'react';

interface ToastMessage {
  id: number;
  text: string;
  type: 'info' | 'success' | 'error';
}

let toastId = 0;
let addToastFn: ((msg: Omit<ToastMessage, 'id'>) => void) | null = null;

export function showToast(text: string, type: 'info' | 'success' | 'error' = 'info') {
  addToastFn?.({ text, type });
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    addToastFn = (msg) => {
      const id = ++toastId;
      setToasts((prev) => [...prev, { ...msg, id }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 3000);
    };
    return () => {
      addToastFn = null;
    };
  }, []);

  if (toasts.length === 0) return null;

  const colors: Record<string, string> = {
    info: 'var(--accent)',
    success: 'var(--teal)',
    error: 'var(--red)',
  };

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 36,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 99999,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        alignItems: 'center',
      }}
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          style={{
            background: 'var(--bg-2)',
            border: `1px solid ${colors[t.type]}`,
            borderRadius: 6,
            padding: '8px 18px',
            color: colors[t.type],
            fontSize: 12,
            fontWeight: 600,
            fontFamily: 'inherit',
            boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
            whiteSpace: 'nowrap',
            animation: 'fadeInUp 0.2s ease-out',
          }}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
