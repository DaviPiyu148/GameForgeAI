import type { ReactNode } from 'react';
import { Navbar } from './Navbar';
import { Footer } from './Footer';

interface PageContainerProps {
  children: ReactNode;
  className?: string;
}

export const PageContainer: React.FC<PageContainerProps> = ({ children, className = '' }) => {
  return (
    <div className="flex flex-col min-h-screen">
      <div className="scanline-effect"></div>
      <Navbar />
      <main className={`flex-1 relative z-10 flex flex-col container mx-auto px-4 py-8 ${className}`}>
        {children}
      </main>
      <Footer />
    </div>
  );
};
