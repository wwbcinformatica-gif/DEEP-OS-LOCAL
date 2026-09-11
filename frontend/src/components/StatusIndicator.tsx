import React from 'react';

interface StatusIndicatorProps {
  provider: string;
  ollamaRunning?: boolean;
  size?: number;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  provider,
  ollamaRunning,
  size = 10,
}) => {
  const getColor = () => {
    if (provider === 'ollama' || provider === 'llamacpp') {
      return ollamaRunning ? '#89d185' : '#f44747';
    }
    return '#89d185';
  };

  return (
    <span
      style={{
        fontFamily: 'inherit',
        fontSize: `${size}px`,
        color: getColor(),
        lineHeight: 1,
      }}
    >
      ●
    </span>
  );
};

export default StatusIndicator;
