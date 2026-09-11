let ctx: AudioContext | null = null;

const getCtx = (): AudioContext => {
  if (!ctx) ctx = new AudioContext();
  return ctx;
};

const tone = (freq: number, dur: number, type: OscillatorType = 'sine', vol = 0.08) => {
  const c = getCtx();
  const o = c.createOscillator();
  const g = c.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, c.currentTime);
  g.gain.setValueAtTime(vol, c.currentTime);
  g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + dur);
  o.connect(g).connect(c.destination);
  o.start(c.currentTime);
  o.stop(c.currentTime + dur);
};

const burst = (freqs: number[], dur: number, type: OscillatorType = 'sine', vol = 0.06) => {
  const c = getCtx();
  freqs.forEach((f, i) => {
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = type;
    const t = c.currentTime + i * dur;
    o.frequency.setValueAtTime(f, t);
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    o.connect(g).connect(c.destination);
    o.start(t);
    o.stop(t + dur);
  });
};

export type SoundType =
  | 'click_folder_open'
  | 'click_folder_close'
  | 'click_file'
  | 'click_menu'
  | 'toggle_on'
  | 'toggle_off'
  | 'agent_thinking'
  | 'agent_success';

let enabled = false;

export const setSoundEnabled = (v: boolean) => {
  enabled = v;
};

export const playSound = (type: SoundType) => {
  if (!enabled) return;
  try {
    switch (type) {
      case 'click_folder_open':
        tone(300, 0.04, 'sine', 0.06);
        setTimeout(() => tone(500, 0.04, 'sine', 0.06), 40);
        break;
      case 'click_folder_close':
        tone(500, 0.04, 'sine', 0.06);
        setTimeout(() => tone(300, 0.04, 'sine', 0.06), 40);
        break;
      case 'click_file':
        tone(800, 0.03, 'square', 0.04);
        break;
      case 'click_menu':
        burst([660, 880], 0.05, 'sine', 0.05);
        break;
      case 'toggle_on':
        tone(440, 0.05, 'triangle', 0.06);
        setTimeout(() => tone(660, 0.05, 'triangle', 0.06), 50);
        break;
      case 'toggle_off':
        tone(180, 0.08, 'sawtooth', 0.04);
        break;
      case 'agent_thinking':
        tone(1000, 0.06, 'sine', 0.05);
        setTimeout(() => tone(800, 0.06, 'sine', 0.04), 60);
        setTimeout(() => tone(600, 0.08, 'sine', 0.03), 120);
        break;
      case 'agent_success':
        burst([660, 880, 1100], 0.06, 'sine', 0.06);
        break;
    }
  } catch {}
};
