import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { PrototypeModal } from '../components/Shared/PrototypeModal';

export default function ProfilePage() {
  const { state, setPrompt, updateBuildParams } = useAppContext();
  const navigate = useNavigate();
  const [showPlayModal, setShowPlayModal] = useState(false);
  const [showLikedGamesModal, setShowLikedGamesModal] = useState(false);
  const [isClosingModal, setIsClosingModal] = useState(false);
  const [displayPrompts, setDisplayPrompts] = useState(0);
  const [displayGames, setDisplayGames] = useState(0);

  const handleCloseModal = () => {
    setIsClosingModal(true);
    setTimeout(() => {
      setShowLikedGamesModal(false);
      setIsClosingModal(false);
    }, 250);
  };

  useEffect(() => {
    const endPrompts = 1337;
    const endGames = state.myGames.length;
    const duration = 1000;
    const startTime = performance.now();

    const updateCounter = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const easeOutQuad = 1 - (1 - progress) * (1 - progress);
      
      setDisplayPrompts(Math.floor(endPrompts * easeOutQuad));
      setDisplayGames(Math.floor(endGames * easeOutQuad));
      
      if (progress < 1) {
        requestAnimationFrame(updateCounter);
      } else {
        setDisplayPrompts(endPrompts);
        setDisplayGames(endGames);
      }
    };
    
    // Check for reduced motion
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mediaQuery.matches) {
      setDisplayPrompts(endPrompts);
      setDisplayGames(endGames);
    } else {
      requestAnimationFrame(updateCounter);
    }
  }, [state.myGames.length]);

  const handleContinueEdit = (desc: string) => {
    setPrompt(desc);
    updateBuildParams({
      engine: 'Custom Forge Engine',
      artDensity: 70,
      physics: 60,
      modules: ['Advanced NPC AI']
    });
    navigate('/build');
  };
  
  return (
    <div className="w-full max-w-6xl mx-auto p-4 md:p-6 lg:p-8 space-y-6 animate-fade-in font-body text-on-surface pb-24">
      {/* Profile Header Console */}
      <div className="relative arcade-border bg-surface-container-low p-6 arcade-panel">
        <div className="absolute top-0 left-0 right-0 h-1 bg-primary/30"></div>
        
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 relative z-10">
          {/* Left: Avatar and Info */}
          <div className="flex items-center gap-6">
            <div className="w-24 h-24 rounded-sm border-4 border-primary bg-surface-container-high flex items-center justify-center shrink-0 glow-box-cyan">
              <span className="material-symbols-outlined text-primary text-[48px]">person</span>
            </div>
            <div className="space-y-2">
              <h1 className="font-display text-xl md:text-2xl text-primary uppercase text-glow-cyan tracking-wider">Player_One</h1>
              <div className="flex items-center gap-2 text-tertiary text-sm md:text-base bg-tertiary/10 px-3 py-1.5 rounded-sm border border-tertiary/20 w-fit">
                <span className="material-symbols-outlined text-[18px]">star</span>
                <span>Level 42 Architect</span>
              </div>
            </div>
          </div>
          
          {/* Right: Stat boxes */}
          <div className="flex flex-wrap gap-4 w-full md:w-auto">
            <div className="bg-surface-container-highest p-4 border border-outline-variant flex-1 md:flex-none min-w-[140px] text-center rounded-sm">
              <div className="text-sm text-on-surface-variant uppercase tracking-wider mb-1">Total Prompts</div>
              <div className="font-display text-primary">{displayPrompts.toLocaleString()}</div>
            </div>
            <div className="bg-surface-container-highest p-4 border border-outline-variant flex-1 md:flex-none min-w-[140px] text-center rounded-sm">
              <div className="text-sm text-on-surface-variant uppercase tracking-wider mb-1">Games Built</div>
              <div className="font-display text-secondary">{displayGames}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column (col-span-1) */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* Stats/Preferences Panel */}
          <div className="relative arcade-border bg-surface-container-low p-5 arcade-panel stagger-enter stagger-1">
            <div className="absolute -top-3 -right-3 bg-primary text-background text-xs font-display px-2 py-1 uppercase tracking-wider shadow-[2px_2px_0px_#000]">Preferences</div>
            
            <div className="flex items-center gap-2 mb-6">
              <span className="material-symbols-outlined text-primary">equalizer</span>
              <h2 className="font-display text-lg uppercase tracking-wide">Stats</h2>
            </div>
            
            <div className="space-y-6">
              {/* Top Genres */}
              <div className="space-y-4">
                <h3 className="text-sm text-on-surface-variant uppercase tracking-wider font-semibold border-b border-outline-variant pb-2">Top Genres</h3>
                
                <div className="space-y-3">
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>RPG</span>
                      <span className="text-primary">85%</span>
                    </div>
                    <div className="h-3 w-full bg-surface-container-highest rounded-full overflow-hidden border border-outline-variant/50">
                      <div className="h-full bg-primary rounded-full stat-bar shadow-[0_0_8px_rgba(76,224,210,0.5)]" style={{"--target-width": "85%"} as React.CSSProperties}></div>
                    </div>
                  </div>
                  
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>Survival</span>
                      <span className="text-secondary-soft">62%</span>
                    </div>
                    <div className="h-3 w-full bg-surface-container-highest rounded-full overflow-hidden border border-outline-variant/50">
                      <div className="h-full bg-secondary-soft rounded-full stat-bar" style={{"--target-width": "62%"} as React.CSSProperties}></div>
                    </div>
                  </div>
                  
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>Strategy</span>
                      <span className="text-tertiary">40%</span>
                    </div>
                    <div className="h-3 w-full bg-surface-container-highest rounded-full overflow-hidden border border-outline-variant/50">
                      <div className="h-full bg-tertiary rounded-full stat-bar" style={{"--target-width": "40%"} as React.CSSProperties}></div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Core Themes */}
              <div className="space-y-4">
                <h3 className="text-sm text-on-surface-variant uppercase tracking-wider font-semibold border-b border-outline-variant pb-2">Core Themes</h3>
                
                <div className="space-y-3">
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span>Cyberpunk</span>
                      <span className="text-primary">90%</span>
                    </div>
                    <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden border border-outline-variant/50">
                      <div className="h-full bg-primary rounded-full stat-bar" style={{"--target-width": "90%"} as React.CSSProperties}></div>
                    </div>
                  </div>
                  
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span>Cozy/Relaxing</span>
                      <span className="text-secondary-soft">75%</span>
                    </div>
                    <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden border border-outline-variant/50">
                      <div className="h-full bg-secondary-soft rounded-full stat-bar" style={{"--target-width": "75%"} as React.CSSProperties}></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Liked Games Panel */}
          <div className="relative arcade-border bg-surface-container-low p-5 arcade-panel stagger-enter stagger-2">
            <div className="flex items-center gap-2 mb-6">
              <span className="material-symbols-outlined text-secondary">favorite</span>
              <h2 className="font-display text-lg uppercase tracking-wide">Liked Games</h2>
            </div>
            
            <div className="space-y-4">
              <div className="flex gap-4 p-3 bg-surface-container-highest/50 border border-outline-variant/50 rounded-sm hover:bg-surface-container-highest hover:border-secondary/30 transition-colors cursor-pointer group">
                <div className="w-12 h-12 bg-primary/20 border border-primary/40 rounded flex items-center justify-center shrink-0 group-hover:bg-primary/30 transition-colors">
                  <span className="material-symbols-outlined text-primary">sports_esports</span>
                </div>
                <div>
                  <h3 className="font-semibold text-on-surface group-hover:text-primary transition-colors">Neon Drifter: Velocity</h3>
                  <p className="text-xs text-on-surface-variant mt-1">Cyberpunk • Racing</p>
                </div>
              </div>
              
              <div className="flex gap-4 p-3 bg-surface-container-highest/50 border border-outline-variant/50 rounded-sm hover:bg-surface-container-highest hover:border-secondary/30 transition-colors cursor-pointer group">
                <div className="w-12 h-12 bg-tertiary-container border border-tertiary/40 rounded flex items-center justify-center shrink-0 group-hover:bg-tertiary/30 transition-colors">
                  <span className="material-symbols-outlined text-tertiary">forest</span>
                </div>
                <div>
                  <h3 className="font-semibold text-on-surface group-hover:text-primary transition-colors">Stardew Valley 2099</h3>
                  <p className="text-xs text-on-surface-variant mt-1">Farming • Sci-Fi</p>
                </div>
              </div>
              
              <button 
                onClick={() => setShowLikedGamesModal(true)}
                className="w-full py-2.5 mt-2 border border-outline-variant text-sm font-semibold hover:bg-surface-container-highest hover:text-primary transition-colors uppercase tracking-wider rounded-sm flex items-center justify-center gap-2 group cursor-pointer btn-interactive"
              >
                View All
                <span className="material-symbols-outlined text-[16px] group-hover:translate-x-1 transition-transform">arrow_forward</span>
              </button>
            </div>
          </div>
          
        </div>
        
        {/* Right Column (col-span-2) */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          
          {/* Generated Games Panel */}
          <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel flex-1 flex flex-col stagger-enter stagger-3">
            <div className="absolute -top-3 -right-3 bg-tertiary text-background text-xs font-display px-2 py-1 uppercase tracking-wider shadow-[2px_2px_0px_#000]">Activity</div>
            
            <div className="flex items-center gap-2 mb-6">
              <span className="material-symbols-outlined text-tertiary">memory</span>
              <h2 className="font-display text-lg uppercase tracking-wide">Generated Games</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-auto">
              {/* Card 1 */}
              <div className="bg-surface border border-outline-variant p-4 flex flex-col rounded-sm relative overflow-hidden group hover:border-tertiary/50 transition-colors">
                <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-bl from-tertiary/10 to-transparent pointer-events-none"></div>
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-bold text-lg group-hover:text-tertiary transition-colors">Chrono-Smith</h3>
                  <span className="bg-surface-container-highest text-xs px-2 py-0.5 rounded border border-outline-variant/50 font-mono text-tertiary">v1.2 Beta</span>
                </div>
                <p className="text-sm text-on-surface-variant line-clamp-3 mb-4 flex-1">
                  A time-bending blacksmith simulator where you forge weapons across different historical eras to prevent an impending temporal collapse.
                </p>
                <div className="flex flex-wrap gap-2 mb-4">
                  <span className="text-xs bg-surface-container-highest px-2 py-1 rounded-sm border border-outline-variant/30">Simulation</span>
                  <span className="text-xs bg-surface-container-highest px-2 py-1 rounded-sm border border-outline-variant/30">RPG</span>
                </div>
                <button 
                  onClick={() => setShowPlayModal(true)}
                  className="flex items-center gap-2 text-sm text-tertiary hover:text-primary transition-colors font-semibold uppercase tracking-wider cursor-pointer btn-interactive origin-left"
                >
                  <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                  Play Prototype
                </button>
              </div>
              
              {/* Card 2 */}
              <div className="bg-surface border border-outline-variant p-4 flex flex-col rounded-sm relative overflow-hidden group hover:border-primary/50 transition-colors">
                <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-bl from-primary/10 to-transparent pointer-events-none"></div>
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-bold text-lg group-hover:text-primary transition-colors">Abyssal Descent</h3>
                  <span className="bg-surface-container-highest text-xs px-2 py-0.5 rounded border border-outline-variant/50 font-mono text-on-surface-variant">Draft</span>
                </div>
                <p className="text-sm text-on-surface-variant line-clamp-3 mb-4 flex-1">
                  Navigate a procedurally generated deep-sea trench in a rickety submarine. Manage dwindling resources while avoiding unspeakable horrors in the dark.
                </p>
                <div className="flex flex-wrap gap-2 mb-4">
                  <span className="text-xs bg-surface-container-highest px-2 py-1 rounded-sm border border-outline-variant/30">Horror</span>
                  <span className="text-xs bg-surface-container-highest px-2 py-1 rounded-sm border border-outline-variant/30">Survival</span>
                </div>
                <button 
                  onClick={() => handleContinueEdit('Navigate a procedurally generated deep-sea trench in a rickety submarine. Manage dwindling resources while avoiding unspeakable horrors in the dark.')}
                  className="flex items-center gap-2 text-sm text-primary hover:text-tertiary transition-colors font-semibold uppercase tracking-wider cursor-pointer btn-interactive origin-left"
                >
                  <span className="material-symbols-outlined text-[18px]">edit_document</span>
                  Continue Edit
                </button>
              </div>
            </div>
          </div>
          
          {/* Recent Discoveries Panel */}
          <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel stagger-enter stagger-4">
            <div className="flex items-center gap-2 mb-6">
              <span className="material-symbols-outlined text-primary">search</span>
              <h2 className="font-display text-lg uppercase tracking-wide">Recent Discoveries</h2>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-start gap-4 p-3 border-l-2 border-primary bg-surface-container-highest/50 hover:bg-surface-container-highest transition-colors">
                <div className="text-xs text-on-surface-variant font-mono whitespace-nowrap pt-1 w-24">Today 14:30</div>
                <div>
                  <div className="font-mono text-sm text-primary mb-1">"procedural generated cozy farming games with mechs"</div>
                  <div className="flex items-center gap-4 text-xs text-on-surface-variant">
                    <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">view_list</span> 4 results</span>
                    <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">timer</span> 1.2s</span>
                  </div>
                </div>
              </div>
              
              <div className="flex items-start gap-4 p-3 border-l-2 border-outline-variant hover:bg-surface-container-highest transition-colors">
                <div className="text-xs text-on-surface-variant font-mono whitespace-nowrap pt-1 w-24">Yesterday</div>
                <div>
                  <div className="font-mono text-sm text-on-surface-variant mb-1">"turn-based strategy matching retro 90s aesthetic"</div>
                  <div className="flex items-center gap-4 text-xs text-on-surface-variant">
                    <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">view_list</span> 12 results</span>
                    <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">timer</span> 2.4s</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
        </div>
      </div>

      {showPlayModal && <PrototypeModal onClose={() => setShowPlayModal(false)} />}
      
      {showLikedGamesModal && (
        <div className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm ${isClosingModal ? 'modal-backdrop-exit' : 'modal-backdrop-enter'}`} onClick={(e) => { if (e.target === e.currentTarget && !isClosingModal) handleCloseModal(); }}>
          <div className={`w-full max-w-lg bg-surface border-2 border-secondary rounded-sm overflow-hidden flex flex-col shadow-[0_0_30px_rgba(255,107,181,0.2)] ${isClosingModal ? 'modal-exit' : 'modal-enter'}`} onClick={e => e.stopPropagation()}>
            <div className="bg-terminal-header border-b border-secondary/30 p-3 flex justify-between items-center">
              <div className="flex items-center gap-2 text-secondary">
                <span className="material-symbols-outlined">favorite</span>
                <span className="font-mono text-sm tracking-widest font-bold uppercase">All Liked Games</span>
              </div>
              <button onClick={handleCloseModal} className="text-on-surface-variant hover:text-secondary p-1 icon-interactive cursor-pointer">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="p-6 bg-terminal-bg max-h-[60vh] overflow-y-auto space-y-4">
              <div className="text-center text-on-surface-variant font-mono text-sm py-8">
                End of liked games list.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
