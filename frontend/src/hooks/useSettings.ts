import { useState, useEffect } from 'react';
import type { Provider, Mood } from '../lib/constants';
import {
  DEFAULT_PROVIDER,
  DEFAULT_MODEL,
  DEFAULT_MOOD,
  DEFAULT_TEMP,
  DEFAULT_BRIGHT,
  DEFAULT_FSIZE,
  SETTINGS_KEY,
} from '../lib/constants';

export interface Settings {
  prov: Provider;
  model: string;
  mood: Mood;
  temp: number;
  sysPr: string;
  snd: boolean;
  bright: number;
  fsize: number;
  apiKey: string;
  orApiKey: string;
}

const DEFAULTS: Settings = {
  prov: DEFAULT_PROVIDER,
  model: DEFAULT_MODEL,
  mood: DEFAULT_MOOD,
  temp: DEFAULT_TEMP,
  sysPr: '',
  snd: false,
  bright: DEFAULT_BRIGHT,
  fsize: DEFAULT_FSIZE,
  apiKey: '',
  orApiKey: '',
};

function load(): Settings {
  try {
    const s = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
    return { ...DEFAULTS, ...s };
  } catch {
    return { ...DEFAULTS };
  }
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(load);
  const [initDone, setInitDone] = useState(false);

  useEffect(() => {
    setSettings(load());
    setInitDone(true);
  }, []);

  useEffect(() => {
    if (!initDone) return;
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }, [initDone, settings]);

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  return { settings, update, initDone };
}
