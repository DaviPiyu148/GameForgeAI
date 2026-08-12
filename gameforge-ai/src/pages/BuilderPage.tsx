import { Navbar } from '../components/Shared/Navbar';
import { useAppContext } from '../context/AppContext';
import { useNavigate } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';

const BuilderPage = () => {
  const { state, setPrompt, updateBuildParams, compileProject, clearCompilerLogs } = useAppContext();
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

  return (
    <div className="min-h-screen flex flex-col font-body">
      {/* Scanline */}
      <div className="scanline-effect"></div>
      
      {/* Nav - uses custom builder nav matching reference */}
      <Navbar />

      {/* Main Workspace */}
      <main className="flex-1 bg-background relative overflow-y-auto lg:overflow-hidden">
        {/* Scanline overlay on workspace */}
        <div className="absolute inset-0 pointer-events-none z-20" style={{
          background: 'linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06))',
          backgroundSize: '100% 2px, 3px 100%'
        }}></div>

        <div className="flex flex-col lg:grid lg:grid-cols-[1fr_320px] lg:grid-rows-[1fr_200px_auto] lg:h-[calc(100vh-64px)] relative z-10">
          
          {/* ═══ Main Prompt Editor (Left, Row 1) ═══ */}
          <div className="order-1 lg:col-start-1 lg:col-end-2 lg:row-start-1 lg:row-end-2 flex flex-col p-4 lg:border-r pane-border overflow-hidden min-h-[60vh] lg:min-h-0">
            <header className="mb-4 flex justify-between items-center">
              <h1 className="font-display text-2xl text-primary flex items-center gap-3">
                Scene Composer
                <span className="flex items-center gap-1.5 px-2 py-0.5 border border-primary/30 bg-primary/10 font-mono text-[10px] text-primary">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary ai-pulse"></span>
                  SYS_ONLINE
                </span>
              </h1>
            </header>

            <div className="bg-terminal-bg border border-outline-variant focus-within:border-primary-bright focus-within:shadow-[0_0_20px_rgba(76,224,210,0.5)] transition-all flex flex-col flex-1 overflow-hidden relative">
              {/* Editor Header */}
              <div className="flex justify-between items-center px-4 py-2 border-b border-primary/20 bg-terminal-header relative">
                <h2 className="font-mono text-xs text-primary flex items-center gap-2 uppercase">
                  <span className="material-symbols-outlined text-sm">terminal</span>
                  SYS_PROMPT.md
                </h2>
                <div className="flex gap-2">
                  <button 
                    onClick={() => setShowHistory(!showHistory)}
                    className={`text-primary/70 hover:text-primary p-1 transition-colors icon-interactive cursor-pointer rounded ${showHistory ? 'bg-primary/20' : 'hover:bg-primary/10'}`}
                    title="Prompt History"
                  >
                    <span className="material-symbols-outlined text-sm">history</span>
                  </button>
                  <button 
                    onClick={handleCopy}
                    className="text-primary/70 hover:text-primary p-1 hover:bg-primary/10 transition-colors icon-interactive cursor-pointer rounded flex items-center gap-1"
                    title="Copy to clipboard"
                  >
                    {copyFeedback ? (
                      <span className="font-mono text-[10px] text-primary font-bold">COPIED</span>
                    ) : (
                      <span className="material-symbols-outlined text-sm">content_copy</span>
                    )}
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

              {/* Editor Body with Line Numbers */}
              <div className="flex-1 relative flex">
                {/* Line Numbers */}
                <div className="w-12 bg-terminal-header border-r border-primary/20 flex flex-col text-primary/40 font-mono text-[10px] py-4 px-2 items-end select-none shrink-0">
                  {[1,2,3,4,5,6,7,8].map(n => (
                    <span key={n}>{n}</span>
                  ))}
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
                <div className="text-primary/60 font-mono text-[10px]">TOKENS: {state.currentPrompt.length} / 8192</div>
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

          {/* ═══ Configuration Panel (Right Sidebar, Rows 1-2) ═══ */}
          <div className="order-2 lg:col-start-2 lg:col-end-3 lg:row-start-1 lg:row-end-3 flex flex-col pane-border bg-surface-container-low overflow-y-auto">
            {/* Live Preview */}
            <div className="p-4 border-b pane-border">
              <h3 className="font-mono text-[10px] text-secondary-soft mb-3 flex items-center gap-2 uppercase tracking-wide">
                <span className="material-symbols-outlined text-[14px]">preview</span>
                Live Preview (Wireframe)
              </h3>
              <div className="bg-terminal-bg border border-secondary-soft/30 aspect-video relative overflow-hidden flex items-center justify-center">
                {/* Grid overlay */}
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

            {/* Parameters */}
            <div className="p-4 flex-1">
              <h3 className="font-mono text-[10px] text-primary mb-4 flex items-center gap-2 uppercase tracking-wide">
                <span className="material-symbols-outlined text-[14px]">tune</span>
                Parameters
              </h3>
              <div className="space-y-5">
                {/* Game Engine Preset */}
                <div>
                  <label className="block font-mono text-[10px] text-on-surface-variant mb-1.5 uppercase">Game Engine Preset</label>
                  <select 
                    className="w-full bg-terminal-bg border border-primary/30 p-2 text-primary font-mono text-xs focus:border-primary focus:ring-0 appearance-none cursor-pointer"
                    value={state.currentBuildParams.engine}
                    onChange={(e) => updateBuildParams({ engine: e.target.value })}
                  >
                    <option value="Unreal Engine 5 Core">Unreal Engine 5 Core</option>
                    <option value="Unity HDRP Baseline">Unity HDRP Baseline</option>
                    <option value="Godot 4.0 Setup">Godot 4.0 Setup</option>
                    <option value="Custom Forge Engine">Custom Forge Engine</option>
                  </select>
                </div>

                {/* Art Style Density */}
                <div>
                  <label className="block font-mono text-[10px] text-on-surface-variant mb-1.5 uppercase">Art Style Density</label>
                  <input 
                    type="range" min="0" max="100" 
                    value={state.currentBuildParams.artDensity} 
                    onChange={(e) => updateBuildParams({ artDensity: parseInt(e.target.value) })}
                    className="w-full cursor-pointer" 
                  />
                  <div className="flex justify-between mt-1 text-[10px] font-mono text-on-surface-variant/60 uppercase">
                    <span>Minimalist</span>
                    <span>Photorealistic</span>
                  </div>
                </div>

                {/* Physics Complexity */}
                <div>
                  <label className="block font-mono text-[10px] text-on-surface-variant mb-1.5 uppercase">Physics Complexity</label>
                  <input 
                    type="range" min="0" max="100" 
                    value={state.currentBuildParams.physics} 
                    onChange={(e) => updateBuildParams({ physics: parseInt(e.target.value) })}
                    className="w-full cursor-pointer" 
                  />
                  <div className="flex justify-between mt-1 text-[10px] font-mono text-on-surface-variant/60 uppercase">
                    <span>Arcade</span>
                    <span>Simulation</span>
                  </div>
                </div>

                {/* Logic Modules */}
                <div className="pt-2 border-t pane-border">
                  <label className="block font-mono text-[10px] text-primary mb-3 uppercase">Logic Modules</label>
                  <div className="space-y-3">
                    {[
                      { name: 'Procedural Gen', checked: state.currentBuildParams.modules.includes('Procedural Gen') },
                      { name: 'Dynamic Economy', checked: state.currentBuildParams.modules.includes('Dynamic Economy') },
                      { name: 'Advanced NPC AI', checked: state.currentBuildParams.modules.includes('Advanced NPC AI') }
                    ].map(mod => (
                      <label key={mod.name} className="flex items-center gap-3 cursor-pointer group">
                        <div className="relative flex items-center">
                          <input 
                            type="checkbox" 
                            checked={mod.checked} 
                            onChange={() => handleModuleToggle(mod.name)}
                            className="sr-only peer" 
                          />
                          <div className="w-8 h-4 bg-surface-variant rounded-full peer peer-checked:bg-secondary-container after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-full peer-checked:after:border-white"></div>
                        </div>
                        <span className="font-mono text-xs text-on-surface-variant group-hover:text-primary transition-colors uppercase">{mod.name}</span>
                      </label>
                    ))}
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
