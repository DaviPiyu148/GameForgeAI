import type { ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className = '',
  children,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-mono uppercase tracking-wider transition-all duration-200 border border-transparent disabled:opacity-50 disabled:cursor-not-allowed';
  
  const variants = {
    primary: 'bg-secondary text-white hover:glow-magenta border-secondary',
    secondary: 'bg-transparent text-primary border-primary hover:bg-primary/10 hover:glow-cyan',
    ghost: 'bg-transparent text-on-surface-variant hover:text-primary hover:bg-surface-container',
    danger: 'bg-transparent text-error border-error hover:bg-error/10 hover:glow-magenta', // Using magenta glow for errors in this aesthetic
  };

  const sizes = {
    sm: 'text-xs px-3 py-1.5',
    md: 'text-sm px-6 py-2.5',
    lg: 'text-base px-8 py-3',
  };

  const width = fullWidth ? 'w-full' : '';

  return (
    <button 
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${width} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};
