import React, { useEffect, useRef } from 'react';
import { useAppSettings } from './AppSettingsContext';

const SpaceBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { space } = useAppSettings();
  const spaceRef = useRef(space);
  const starsRef = useRef<{ x: number; y: number; z: number; prevX: number; prevY: number }[]>([]);
  
  useEffect(() => {
    spaceRef.current = space;
  }, [space]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const initStars = () => {
      starsRef.current = [];
      const numStars = spaceRef.current.starCount;
      for (let i = 0; i < numStars; i++) {
        starsRef.current.push({
          x: (Math.random() - 0.5) * canvas.width * 2,
          y: (Math.random() - 0.5) * canvas.height * 2,
          z: Math.random() * 2000,
          prevX: 0,
          prevY: 0,
        });
      }
    };

    const animate = () => {
      if (!spaceRef.current.enabled) {
        ctx.fillStyle = '#050510';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        animationId = requestAnimationFrame(animate);
        return;
      }

      ctx.fillStyle = 'rgba(5, 5, 15, 0.25)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const speed = spaceRef.current.speed;

      starsRef.current.forEach((star) => {
        star.prevX = (star.x / star.z) * 300 + centerX;
        star.prevY = (star.y / star.z) * 300 + centerY;

        star.z -= speed;

        if (star.z <= 1) {
          star.x = (Math.random() - 0.5) * canvas.width * 2;
          star.y = (Math.random() - 0.5) * canvas.height * 2;
          star.z = 2000;
          star.prevX = centerX;
          star.prevY = centerY;
        }

        const x = (star.x / star.z) * 300 + centerX;
        const y = (star.y / star.z) * 300 + centerY;
        const size = Math.max(0.5, (1 - star.z / 2000) * 3);
        const brightness = Math.min(1, 1 - star.z / 2000);

        if (star.prevX !== 0 && star.prevY !== 0) {
          ctx.beginPath();
          ctx.strokeStyle = `rgba(180, 200, 255, ${brightness * 0.4})`;
          ctx.lineWidth = size * 0.5;
          ctx.moveTo(star.prevX, star.prevY);
          ctx.lineTo(x, y);
          ctx.stroke();
        }

        ctx.beginPath();
        ctx.fillStyle = `rgba(255, 255, 255, ${brightness})`;
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();

        if (size > 1.5) {
          const gradient = ctx.createRadialGradient(x, y, 0, x, y, size * 4);
          gradient.addColorStop(0, `rgba(200, 220, 255, ${brightness * 0.6})`);
          gradient.addColorStop(0.5, `rgba(150, 180, 255, ${brightness * 0.2})`);
          gradient.addColorStop(1, 'rgba(100, 150, 255, 0)');
          ctx.fillStyle = gradient;
          ctx.beginPath();
          ctx.arc(x, y, size * 4, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      animationId = requestAnimationFrame(animate);
    };

    resize();
    initStars();
    animate();

    const handleResize = () => {
      resize();
      initStars();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // Re-init stars when starCount changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    starsRef.current = [];
    const numStars = space.starCount;
    for (let i = 0; i < numStars; i++) {
      starsRef.current.push({
        x: (Math.random() - 0.5) * canvas.width * 2,
        y: (Math.random() - 0.5) * canvas.height * 2,
        z: Math.random() * 2000,
        prevX: 0,
        prevY: 0,
      });
    }
  }, [space.starCount]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: -1,
        background: '#050510',
        pointerEvents: 'none',
      }}
    />
  );
};

export default SpaceBackground;
