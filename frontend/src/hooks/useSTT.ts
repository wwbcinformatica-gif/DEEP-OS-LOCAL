import { useState, useCallback, useRef } from 'react';
import { API_BASE } from '../lib/constants';

interface STTResult {
  text: string;
  segments: { start: number; end: number; text: string }[];
  language: string;
  language_probability: number;
  duration: number;
  model: string;
}

interface UseSTTReturn {
  isTranscribing: boolean;
  error: string | null;
  transcribe: (audioBlob: Blob, options?: {
    model?: string;
    language?: string;
    task?: string;
  }) => Promise<STTResult | null>;
  isSupported: boolean;
}

export function useSTT(): UseSTTReturn {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const isSupported = typeof navigator !== 'undefined' && 
    typeof MediaRecorder !== 'undefined';

  const transcribe = useCallback(async (
    audioBlob: Blob,
    options: {
      model?: string;
      language?: string;
      task?: string;
    } = {}
  ): Promise<STTResult | null> => {
    try {
      setError(null);
      setIsTranscribing(true);

      // Cancelar requisição anterior se existir
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      // Criar FormData com o arquivo de áudio
      const formData = new FormData();
      formData.append('file', audioBlob, 'audio.webm');
      
      if (options.model) {
        formData.append('model', options.model);
      }
      if (options.language) {
        formData.append('language', options.language);
      }
      if (options.task) {
        formData.append('task', options.task);
      }

      const response = await fetch(`${API_BASE}/api/stt/transcribe`, {
        method: 'POST',
        body: formData,
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result: STTResult = await response.json();
      return result;
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return null;
      }
      const message = err instanceof Error ? err.message : 'Erro na transcrição';
      setError(message);
      console.error('[STT] Erro:', message);
      return null;
    } finally {
      setIsTranscribing(false);
      abortControllerRef.current = null;
    }
  }, []);

  return {
    isTranscribing,
    error,
    transcribe,
    isSupported,
  };
}

// Hook para gravar áudio do microfone
interface UseAudioRecorderReturn {
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<Blob | null>;
  audioLevel: number;
  error: string | null;
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const updateLevel = useCallback(() => {
    if (!analyserRef.current) return;
    
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);
    
    const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
    setAudioLevel(average / 255);
    
    animFrameRef.current = requestAnimationFrame(updateLevel);
  }, []);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      chunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;

      // Configurar analyser para nível de áudio
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Configurar MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100); // Coletar a cada 100ms
      setIsRecording(true);
      updateLevel();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao acessar microfone';
      setError(message);
      console.error('[AudioRecorder] Erro:', message);
    }
  }, [updateLevel]);

  const stopRecording = useCallback(async (): Promise<Blob | null> => {
    return new Promise((resolve) => {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
        resolve(null);
        return;
      }

      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        resolve(blob.size > 0 ? blob : null);
      };

      mediaRecorderRef.current.stop();
      
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }

      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }

      analyserRef.current = null;
      setIsRecording(false);
      setAudioLevel(0);
    });
  }, []);

  return {
    isRecording,
    startRecording,
    stopRecording,
    audioLevel,
    error,
  };
}
