import { Navbar } from '../components/Shared/Navbar';
import { useAppContext } from '../context/AppContext';
import { useNavigate } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';

const BuilderPage = () => {
  const { state, setPrompt, updateBuildParams, compileProject, cancelCurrentBuild, clearCompilerLogs } = useAppContext();
  const navigate = useNavigate();
  const logsEndRef = useRef<HTMLDivElement>(null);
  
  const [copyFeedback, setCopyFeedback] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [state.compilerLogs]);

  const handleModuleToggle = (modName: string) => {
    const currentModules = state.currentBuildParams.modules;
    const isEnabled = currentModules.includes(modName);
    const newModules = isEnabled 
      ? currentModules.filter(m => m !== modName)
      : [...currentModules, modName];
    
    updateBuildParams({ modules: newModules });
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(state.currentPrompt);
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2000);
    } catch (err) {
      console.warn('Failed to copy text', err);
    }
  };

  // Derive history uniquely from past generated games
  const promptHistory = Array.from(new Set(state.myGames.map(g => g.prompt))).filter(Boolean);

  // Derive active Game DNA summary if available
  const userGameDNA =
    state.preferences?.has_sufficient_data && state.preferences.top_genres.length > 0
      ? state.preferences.top_genres.slice(0, 3).map(g => g.genre).join(' • ')
      : null;

  return (
    <div className="min-h-screen bg-surface flex flex-col antialiased text-on-surface select-none relative overflow-hidden">
      {/* Nav - uses custom builder nav matching reference */}
      <Navbar />

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col relative z-10 p-2 md:p-4 overflow-hidden">
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_380px] grid-rows-[1fr_240px_auto] lg:grid-rows-[1fr_240px_auto] gap-0 border pane-border bg-surface-container/50 backdrop-blur-md overflow-hidden relative shadow-2xl">
          
          {/* ═══ Code / Logic Editor (Top Left, Row 1) ═══ */}
          <div className="col-start-1 col-end-2 row-start-1 row-end-2 border-r pane-border flex flex-col overflow-hidden">
            <div className="h-full flex flex-col bg-surface-container-lowest/90">
              {/* Editor Header */}
              <div className="bg-terminal-header border-b border-primary/20 px-4 py-2 flex justify-between items-center relative">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm text-primary">terminal</span>
                  <span className="font-mono text-xs text-primary font-bold tracking-wider uppercase">Natural Logic Editor</span>
                  <span className="bg-primary/10 border border-primary/30 text-primary font-mono text-[9px] px-1.5 py-0.5 rounded-xs ml-2">PROMPT MODE</span>
                  {userGameDNA && (
                    <div
                      className="hidden sm:flex items-center gap-1 px-2 py-0.5 rounded bg-primary/10 border border-primary/30 text-primary text-[10px] font-mono ml-2"
                      title="AI generation subtly incorporates your Game DNA preferences as secondary flavor"
                    >
                      <span className="material-symbols-outlined text-xs">genetics</span>
                      <span>Personalized: {userGameDNA}</span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <button 
                    onClick={() => setShowHistory(!showHistory)} 
                    className="text-primary/70 hover:text-primary font-mono text-[10px] flex items-center gap-1 uppercase transition-colors cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[14px]">history</span>
                    History ({promptHistory.length})
                  </button>
                  <button 
                    onClick={handleCopy} 
                    className="text-primary/70 hover:text-primary font-mono text-[10px] flex items-center gap-1 uppercase transition-colors cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[14px]">{copyFeedback ? 'check' : 'content_copy'}</span>
                    {copyFeedback ? 'Copied' : 'Copy'}
                  </button>
                </div>
                
                {/* History Popover */}
                {showHistory && (
                  <div className="absolute top-full right-4 mt-2 w-72 bg-surface-container border border-primary/50 shadow-lg z-30 flex flex-col max-h-64 rounded-sm modal-enter">
                    <div className="bg-terminal-header border-b border-primary/30 px-3 py-2 flex justify-between items-center">
                      <span className="font-mono text-[10px] text-primary uppercase">Prompt History</span>
                      <button onClick={() => setShowHistory(false)} className="text-primary/70 hover:text-primary">
                        <span className="material-symbols-outlined text-[14px]">close</span>
                      </button>
                    </div>
                    <div className="overflow-y-auto p-2 flex flex-col gap-1">
                      {promptHistory.length === 0 ? (
                        <div className="text-on-surface-variant font-mono text-xs text-center py-4">
                          NO PROMPT HISTORY
                        </div>
                      ) : (
                        promptHistory.map((histPrompt, idx) => (
                          <button
                            key={idx}
                            onClick={() => { setPrompt(histPrompt); setShowHistory(false); }}
                            className="text-left font-mono text-xs text-on-surface-variant hover:text-primary hover:bg-primary/10 p-2 truncate border border-transparent hover:border-primary/30 transition-colors cursor-pointer rounded-sm"
                            title={histPrompt}
                          >
                            {histPrompt}
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Editor Body */}
              <div className="flex-1 relative flex">
                <div className="w-12 bg-terminal-header border-r border-primary/20 flex flex-col text-primary/40 font-mono text-[10px] py-4 px-2 items-end select-none shrink-0">
                  {[1,2,3,4,5,6,7,8].map(n => <span key={n}>{n}</span>)}
                </div>
                <textarea
                  className="w-full h-full bg-transparent text-primary font-mono text-sm leading-relaxed p-4 resize-none focus:outline-none border-none"
                  placeholder={`> Initialize environment setup...\n> Define mechanics here...`}
                  value={state.currentPrompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={state.buildStatus === 'COMPILING'}
                />
              </div>

              {/* Editor Footer */}
              <div className="px-4 py-3 border-t border-primary/20 bg-terminal-header flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="text-primary/60 font-mono text-[10px]">TOKENS: {state.currentPrompt.length} / 8192</div>
                  {userGameDNA && (
                    <div className="hidden md:inline-flex items-center gap-1 font-mono text-[10px] text-primary/80 bg-primary/5 px-2 py-0.5 rounded border border-primary/20">
                      <span className="material-symbols-outlined text-[12px] text-primary">auto_awesome</span>
                      <span>Using Game DNA</span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {state.buildStatus === 'COMPILING' && (
                    <button
                      onClick={cancelCurrentBuild}
                      className="bg-error/20 hover:bg-error/30 text-error border border-error/50 px-4 py-2 font-mono text-xs uppercase tracking-wide flex items-center gap-1.5 btn-interactive cursor-pointer transition-colors"
                    >
                      <span className="material-symbols-outlined text-sm">cancel</span>
                      Cancel Build
                    </button>
                  )}
                  <button 
                    onClick={() => compileProject(navigate)}
                    disabled={state.buildStatus === 'COMPILING'}
                    className={`bg-secondary-container hover:bg-secondary-soft/30 text-on-surface border border-secondary-soft px-6 py-2 font-mono text-xs uppercase tracking-wide flex items-center gap-2 btn-interactive energy-sweep glow-magenta ${state.buildStatus === 'COMPILING' ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
                  >
                    <span className="material-symbols-outlined text-sm">{state.buildStatus === 'COMPILING' ? 'sync' : 'play_arrow'}</span>
                    {state.buildStatus === 'COMPILING' ? 'Compiling...' : 'Compile Scene'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* ═══ Configuration Panel (Right Sidebar, Rows 1-2) ═══ */}
          <div className="order-2 lg:col-start-2 lg:col-end-3 lg:row-start-1 lg:row-end-3 flex flex-col pane-border bg-surface-container-low overflow-y-auto">
            <div className="p-4 border-b pane-border">
              <h3 className="font-mono text-[10px] text-secondary-soft mb-3 flex items-center gap-2 uppercase tracking-wide">
                <span className="material-symbols-outlined text-[14px]">preview</span>
                Live Preview (Wireframe)
              </h3>
              <div className="bg-terminal-bg border border-secondary-soft/30 aspect-video relative overflow-hidden flex items-center justify-center">
                <div className="absolute inset-0" style={{
                  backgroundImage: 'linear-gradient(rgba(105, 248, 234, 0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(105, 248, 234, 0.2) 1px, transparent 1px)',
                  backgroundSize: '20px 20px',
                  opacity: 0.5
                }}></div>
                <div className="relative z-10 text-center">
                  <span className="material-symbols-outlined text-2xl text-primary mb-1 opacity-80 ai-pulse">view_in_ar</span>
                  <p className="font-mono text-[10px] text-primary/80 uppercase tracking-widest">Awaiting_Render_Data</p>
                </div>
              </div>
            </div>

            <div className="p-4 flex-1">
              <h3 className="font-mono text-[10px] text-primary mb-4 flex items-center gap-2 uppercase tracking-wide">
                <span className="material-symbols-outlined text-[14px]">tune</span>
                Parameters
              </h3>
              <div className="space-y-5">
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="block font-mono text-[10px] text-on-surface-variant uppercase">Prototype Profile Preset</label>
                    <span className="font-mono text-[9px] text-primary/70 bg-primary/10 px-1.5 py-0.5 border border-primary/30 rounded-xs uppercase">Phaser 2D</span>
                  </div>
                  <select 
                    className="w-full bg-terminal-bg border border-primary/40 p-2 text-primary font-mono text-xs cursor-pointer focus:ring-1 focus:ring-primary outline-none"
                    value={state.currentBuildParams.engine || 'Top-Down Action'}
                    onChange={(e) => updateBuildParams({ engine: e.target.value })}
                  >
                    <option value="Top-Down Action">Top-Down Action (Combat & Evade)</option>
                    <option value="Arena Survival">Arena Survival (Escalating Waves)</option>
                    <option value="2D Platformer">2D Platformer (Jump & Checkpoint)</option>
                    <option value="Data Collector">Data Collector (Resource Node Sweep)</option>
                  </select>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="block font-mono text-[10px] text-on-surface-variant uppercase">World Architecture Mode</label>
                    <span className="font-mono text-[9px] text-primary/80 bg-primary/10 px-1.5 py-0.5 border border-primary/30 rounded-xs uppercase">
                      {state.currentBuildParams.world_mode === 'open_world' ? 'Open World' : state.currentBuildParams.world_mode === 'campaign' ? 'Campaign' : 'Linear'}
                    </span>
                  </div>
                  <select 
                    className="w-full bg-terminal-bg border border-primary/40 p-2 text-primary font-mono text-xs cursor-pointer focus:ring-1 focus:ring-primary outline-none"
                    value={state.currentBuildParams.world_mode || 'linear'}
                    onChange={(e) => updateBuildParams({ world_mode: e.target.value as 'linear' | 'campaign' | 'open_world' })}
                  >
                    <option value="linear">Linear Arena / Single Stage</option>
                    <option value="campaign">Sequential Multi-Stage Campaign</option>
                    <option value="open_world">Generalized Open World (Districts & Vehicles)</option>
                  </select>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="block font-mono text-[10px] text-on-surface-variant uppercase">Game Scale / Budget Tier</label>
                    <span className="font-mono text-[9px] text-secondary bg-secondary/10 px-1.5 py-0.5 border border-secondary/30 rounded-xs uppercase">
                      {state.currentBuildParams.scale === 'campaign' ? 'Expanded' : state.currentBuildParams.scale === 'standard' ? 'Standard' : 'Prototype'}
                    </span>
                  </div>
                  <select 
                    className="w-full bg-terminal-bg border border-primary/40 p-2 text-primary font-mono text-xs cursor-pointer focus:ring-1 focus:ring-primary outline-none"
                    value={state.currentBuildParams.scale || 'prototype'}
                    onChange={(e) => updateBuildParams({ scale: e.target.value as 'prototype' | 'standard' | 'campaign' })}
                  >
                    <option value="prototype">Fast Prototype (1 Level / Small World)</option>
                    <option value="standard">Standard Scale (2-3 Stages / Mid World)</option>
                    <option value="campaign">Expanded Scale (3-5 Stages / Large World)</option>
                  </select>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="block font-mono text-[10px] text-on-surface-variant uppercase">Procedural Visual Density</label>
                    <span className="font-mono text-[10px] text-primary font-bold">{state.currentBuildParams.artDensity}%</span>
                  </div>
                  <input 
                    type="range" min="0" max="100" 
                    value={state.currentBuildParams.artDensity} 
                    onChange={(e) => updateBuildParams({ artDensity: parseInt(e.target.value) })}
                    className="w-full cursor-pointer" 
                  />
                  <div className="flex justify-between mt-1 text-[10px] font-mono text-on-surface-variant/60 uppercase">
                    <span>Minimalist Vector</span>
                    <span>Rich Details</span>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="block font-mono text-[10px] text-on-surface-variant uppercase">Physics Complexity</label>
                    <span className="font-mono text-[10px] text-primary font-bold">{state.currentBuildParams.physics}%</span>
                  </div>
                  <input 
                    type="range" min="0" max="100" 
                    value={state.currentBuildParams.physics} 
                    onChange={(e) => updateBuildParams({ physics: parseInt(e.target.value) })}
                    className="w-full cursor-pointer" 
                  />
                  <div className="flex justify-between mt-1 text-[10px] font-mono text-on-surface-variant/60 uppercase">
                    <span>Arcade / Linear</span>
                    <span>Dynamic Sim</span>
                  </div>
                </div>

                <div className="pt-2 border-t pane-border">
                  <label className="block font-mono text-[10px] text-primary mb-3 uppercase">Logic Modules</label>
                  <div className="space-y-3">
                    {[
                      { name: 'Procedural Generation', desc: 'Distributed coordinate layout & seed' },
                      { name: 'Enhanced NPC Behavior', desc: 'Dynamic chase, patrol & ranged logic' },
                      { name: 'Combat & Dash Mobility', desc: 'Plasma blaster, dash stamina & knockback' },
                      { name: 'Resource & Score Economy', desc: 'Collectible triggers & wave targets' }
                    ].map(mod => {
                      const isChecked = state.currentBuildParams.modules.includes(mod.name);
                      return (
                        <label key={mod.name} className="flex items-center gap-3 cursor-pointer group">
                          <div className="relative flex items-center">
                            <input 
                              type="checkbox" 
                              checked={isChecked} 
                              onChange={() => handleModuleToggle(mod.name)}
                              className="sr-only peer" 
                            />
                            <div className="w-8 h-4 bg-surface-variant rounded-full peer peer-checked:bg-secondary-container after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-full peer-checked:after:border-white"></div>
                          </div>
                          <div className="flex flex-col">
                            <span className="font-mono text-xs text-on-surface-variant group-hover:text-primary transition-colors uppercase">{mod.name}</span>
                            <span className="font-mono text-[9px] text-on-surface-variant/60">{mod.desc}</span>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ═══ Output Console (Left, Row 2) ═══ */}
          <div className={`hidden lg:flex col-start-1 col-end-2 row-start-2 row-end-3 border-t border-r pane-border bg-terminal-bg flex-col h-full relative overflow-hidden ${state.buildStatus === 'COMPILING' ? 'crt-flicker delay-2' : ''}`}>
            {state.buildStatus === 'COMPILING' && <div className="absolute inset-0 scanline-effect opacity-30 pointer-events-none"></div>}
            <div className="flex justify-between items-center px-4 py-1.5 border-b border-primary/20 bg-terminal-header relative z-10">
              <h2 className="font-mono text-[10px] uppercase text-primary flex items-center gap-2">
                <span className="material-symbols-outlined text-[14px]">dvr</span>
                Compiler Output
              </h2>
              <button onClick={clearCompilerLogs} className="text-primary/70 hover:text-primary p-1 hover:bg-primary/10 transition-colors cursor-pointer rounded">
                <span className="material-symbols-outlined text-[14px]">clear_all</span>
              </button>
            </div>
            <div className="flex-1 p-4 font-mono text-xs text-primary/80 overflow-y-auto space-y-1">
              {state.compilerLogs.length === 0 ? (
                <>
                  <div className="text-primary opacity-90">[SYS] Environment ready. Forge Engine v4.2.1 initialized.</div>
                  {state.currentBuildParams.modules.map(mod => (
                    <div key={mod}><span className="text-secondary-soft font-bold">[MOD]</span> Loaded Logic Module: {mod}</div>
                  ))}
                  <div className="opacity-50 text-on-surface-variant">[SYS] Waiting for prompt input...</div>
                </>
              ) : (
                state.compilerLogs.map((log, i) => (
                  <div key={i} className={`animate-[fadeIn_0.15s_ease-out_forwards] ${log.includes('FATAL') ? 'text-error font-bold' : log.includes('[MOD]') ? 'text-secondary-soft' : 'text-primary'}`}>
                    {log}
                  </div>
                ))
              )}
              
              <div className="text-primary opacity-90 animate-pulse mt-2 flex items-center gap-2">
                <span className="w-2 h-4 bg-primary inline-block"></span>
              </div>
              <div ref={logsEndRef} />
            </div>
          </div>

          {/* ═══ Footer (Row 3) ═══ */}
          <div className="col-start-1 lg:col-end-3 row-start-3 row-end-4 border-t pane-border bg-surface-container-low p-2 flex justify-center items-center">
            <p className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest">© 2026 GAMEFORGE AI</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default BuilderPage;
