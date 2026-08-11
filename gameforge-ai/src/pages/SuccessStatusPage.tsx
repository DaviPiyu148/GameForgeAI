import { Link } from 'react-router-dom';
import { useState } from 'react';
import { PrototypeModal } from '../components/Shared/PrototypeModal';

const SuccessStatusPage = () => {
  const [showPlayModal, setShowPlayModal] = useState(false);

  return (
    <>
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-16 w-full max-w-[800px] mx-auto relative z-10">
        {/* 1. Success Icon & Title */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-24 h-24 rounded-full border-4 border-primary bg-primary/10 glow-cyan flex items-center justify-center modal-enter mb-6">
            <span
              className="material-symbols-outlined text-6xl text-primary"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              done_all
            </span>
          </div>

          <h1 className="font-display text-2xl md:text-3xl text-on-surface uppercase final-reveal mb-2">
            PROTOTYPE VALIDATED
          </h1>

          <p className="font-mono text-xs text-primary final-reveal">
            &gt; SUCCESS_CODE: 0x00_SYS_READY
          </p>
        </div>

        {/* 2. Validation Terminal */}
        <div className="w-full border border-outline-variant bg-terminal-bg rounded-lg overflow-hidden mb-8 shadow-2xl">
          {/* Terminal Header */}
          <div className="bg-terminal-header px-4 py-3 flex items-center justify-between border-b border-outline-variant">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-secondary-container"></div>
              <div className="w-3 h-3 rounded-full bg-tertiary-container"></div>
              <div className="w-3 h-3 rounded-full bg-primary"></div>
            </div>
            <span className="font-mono text-xs text-on-surface-variant uppercase tracking-wider">
              VALIDATION_SEQUENCE.exe
            </span>
            <div className="w-14"></div>
          </div>

          {/* Terminal Body */}
          <div className="p-6 font-mono text-sm space-y-3.5 text-left">
            <div className="flex items-center gap-3 check-anim delay-1">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Game code generated
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-2">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Syntax validation passed
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-3">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Runtime initialized
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-4">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Core mechanics loaded
              </span>
            </div>

            <div className="flex items-center gap-3 check-anim delay-5">
              <span className="text-primary font-bold">&gt;</span>
              <span
                className="material-symbols-outlined text-primary text-[16px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="text-on-surface uppercase tracking-wide">
                Input controls detected
              </span>
            </div>

            <div className="flex items-center gap-2 pt-2 text-on-surface-variant final-reveal">
              <span className="text-primary font-bold">~ $</span>
              <span>System standing by for user input...</span>
              <span className="inline-block w-2 h-[1em] bg-primary terminal-cursor align-middle ml-0.5"></span>
            </div>
          </div>
        </div>

        {/* 3. Action Buttons */}
        <div className="flex flex-row flex-wrap items-center justify-center gap-4 final-reveal w-full">
          <button 
            onClick={() => setShowPlayModal(true)}
            className="bg-primary text-on-primary glow-cyan btn-interactive energy-sweep font-mono uppercase px-8 py-4 flex items-center justify-center gap-2 font-bold tracking-wider rounded cursor-pointer"
          >
            <span
              className="material-symbols-outlined text-xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              play_arrow
            </span>
            <span>PLAY PROTOTYPE</span>
          </button>

          <Link
            to="/build"
            className="border border-secondary-soft text-secondary-soft hover:bg-secondary/10 font-mono uppercase px-8 py-4 flex items-center justify-center gap-2 font-bold tracking-wider rounded btn-interactive cursor-pointer"
          >
            <span className="material-symbols-outlined text-xl">edit</span>
            <span>MODIFY</span>
          </Link>

          <Link
            to="/dashboard"
            className="border border-outline-variant text-on-surface hover:text-primary hover:border-primary font-mono uppercase px-8 py-4 flex items-center justify-center gap-2 font-bold tracking-wider rounded btn-interactive cursor-pointer"
          >
            <span className="material-symbols-outlined text-xl">dashboard</span>
            <span>DASHBOARD</span>
          </Link>
        </div>
      </div>

      {/* Play Prototype Modal */}
      {showPlayModal && (
        <PrototypeModal onClose={() => setShowPlayModal(false)} />
      )}
    </>
  );
};

export default SuccessStatusPage;

