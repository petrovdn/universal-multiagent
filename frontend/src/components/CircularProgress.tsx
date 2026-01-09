import React from 'react'

interface CircularProgressProps {
  percent: number       // 0-100
  size?: number         // размер в px (default: 16)
  strokeWidth?: number  // толщина линии (default: 2)
  className?: string
}

/**
 * Круговой индикатор прогресса (pie chart style).
 * Заполняется по часовой стрелке, начиная сверху.
 */
export function CircularProgress({
  percent,
  size = 16,
  strokeWidth = 2,
  className = ''
}: CircularProgressProps) {
  // Ограничиваем percent в диапазоне 0-100
  const clampedPercent = Math.min(100, Math.max(0, percent))
  
  // Радиус круга (с учётом толщины линии)
  const radius = (size - strokeWidth) / 2
  // Длина окружности
  const circumference = 2 * Math.PI * radius
  // Смещение для отображения прогресса (от полного к пустому)
  const strokeDashoffset = circumference - (clampedPercent / 100) * circumference
  
  // Центр круга
  const center = size / 2
  
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`circular-progress ${className}`}
    >
      {/* Фоновый круг */}
      <circle
        className="circular-progress-bg"
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        opacity={0.2}
      />
      
      {/* Прогресс круг */}
      <g style={{ transform: 'rotate(-90deg)', transformOrigin: 'center' }}>
        <circle
          className="circular-progress-fill"
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={clampedPercent === 100 ? 0 : strokeDashoffset}
          style={{
            transition: 'stroke-dashoffset 0.3s ease'
          }}
        />
      </g>
    </svg>
  )
}
