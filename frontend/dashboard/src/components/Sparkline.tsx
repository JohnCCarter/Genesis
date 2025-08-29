import React from 'react';

export function Sparkline({ data, width = 120, height = 28, color = '#228BE6', fill = 'transparent', strokeWidth = 2 }: { data: number[]; width?: number; height?: number; color?: string; fill?: string; strokeWidth?: number }) {
  if (!Array.isArray(data) || data.length < 2) {
    return <svg width={width} height={height}></svg>;
  }
  const w = width;
  const h = height;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = w / (data.length - 1);
  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = h - ((v - min) / span) * h;
    return `${x},${y}`;
  });
  const polyline = points.join(' ');
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline
        fill={fill}
        stroke={color}
        strokeWidth={strokeWidth}
        points={polyline}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
