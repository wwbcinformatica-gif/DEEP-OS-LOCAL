import React, { useState, useRef, useEffect, useImperativeHandle, forwardRef } from 'react';

interface Track {
  name: string;
  url: string;
  isVideo: boolean;
  path?: string;
}

export interface MusicPlayerHandle {
  playFile: (name: string) => boolean;
  playPause: () => void;
  next: () => void;
  prev: () => void;
  stop: () => void;
  getTracks: () => { name: string; isVideo: boolean }[];
  addByUrl: (name: string, url: string, isVideo: boolean) => void;
  setVolume: (v: number) => void;
}

const MusicPlayer = forwardRef<MusicPlayerHandle>((_props, ref) => {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [currentIdx, setCurrentIdx] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(0.7);
  const [showList, setShowList] = useState(false);
  const [videoSize, setVideoSize] = useState<'xs' | 'sm' | 'md' | 'lg'>('sm');
  const mediaRef = useRef<HTMLAudioElement | HTMLVideoElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const currentTrack = currentIdx >= 0 ? tracks[currentIdx] : null;
  const isVideo = currentTrack?.isVideo || false;

  const VIDEO_SIZES: Record<string, { w: number; h: number; label: string }> = {
    xs: { w: 50, h: 28, label: 'XS' },
    sm: { w: 80, h: 45, label: 'SM' },
    md: { w: 120, h: 68, label: 'MD' },
    lg: { w: 160, h: 90, label: 'LG' },
  };
  const vs = VIDEO_SIZES[videoSize];

  useEffect(() => {
    return () => { tracks.forEach((t) => URL.revokeObjectURL(t.url)); };
  }, []);

  const addFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const newTracks: Track[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const isVid = f.type.startsWith('video/') || /\.(mp4|wmv|avi|mkv|webm|mov)$/i.test(f.name);
      const isAud = f.type.startsWith('audio/') || /\.(mp3|wav|ogg|flac|m4a|aac)$/i.test(f.name);
      if (isVid || isAud) {
        newTracks.push({ name: f.name, url: URL.createObjectURL(f), isVideo: isVid });
      }
    }
    if (newTracks.length) {
      setTracks((prev) => {
        const next = [...prev, ...newTracks];
        if (currentIdx < 0 && next.length > 0) setCurrentIdx(0);
        return next;
      });
    }
    // Reseta o input para permitir selecionar os mesmos arquivos novamente
    if (fileRef.current) fileRef.current.value = '';
  };

  useEffect(() => {
    const el = isVideo ? videoRef.current : mediaRef.current;
    if (!el) return;
    const onTime = () => {
      if (el.duration) {
        setProgress(el.currentTime / el.duration);
        setDuration(el.duration);
      }
    };
    const onEnd = () => setCurrentIdx((p) => (p + 1 < tracks.length ? p + 1 : 0));
    el.addEventListener('timeupdate', onTime);
    el.addEventListener('ended', onEnd);
    return () => {
      el.removeEventListener('timeupdate', onTime);
      el.removeEventListener('ended', onEnd);
    };
  }, [tracks.length, isVideo, currentIdx]);

  useEffect(() => {
    if (currentIdx < 0 || !tracks[currentIdx]) return;
    const t = tracks[currentIdx];
    mediaRef.current?.pause();
    videoRef.current?.pause();
    if (t.isVideo && videoRef.current) {
      videoRef.current.src = t.url;
      videoRef.current.volume = volume;
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    } else if (!t.isVideo && mediaRef.current) {
      (mediaRef.current as HTMLAudioElement).src = t.url;
      mediaRef.current.volume = volume;
      mediaRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  }, [currentIdx]);

  useEffect(() => {
    if (mediaRef.current) mediaRef.current.volume = volume;
    if (videoRef.current) videoRef.current.volume = volume;
  }, [volume]);

  const togglePlay = () => {
    const el = isVideo ? videoRef.current : mediaRef.current;
    if (!el || currentIdx < 0) return;
    if (isPlaying) { el.pause(); setIsPlaying(false); }
    else { el.play().then(() => setIsPlaying(true)).catch(() => {}); }
  };

  const stopPlayback = () => {
    mediaRef.current?.pause();
    videoRef.current?.pause();
    setIsPlaying(false);
    setProgress(0);
  };

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = isVideo ? videoRef.current : mediaRef.current;
    if (!el || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    el.currentTime = pct * duration;
    setProgress(pct);
  };

  const prevTrack = () => setCurrentIdx((p) => (p > 0 ? p - 1 : tracks.length - 1));
  const nextTrack = () => setCurrentIdx((p) => (p + 1 < tracks.length ? p + 1 : 0));

  const removeTrack = (idx: number) => {
    URL.revokeObjectURL(tracks[idx].url);
    setTracks((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      if (currentIdx >= next.length) setCurrentIdx(next.length - 1);
      else if (idx < currentIdx) setCurrentIdx((p) => p - 1);
      return next;
    });
  };

  // Expose methods for AI control
  useImperativeHandle(ref, () => ({
    playFile: (name: string) => {
      const idx = tracks.findIndex((t) => t.name.toLowerCase().includes(name.toLowerCase()));
      if (idx >= 0) { setCurrentIdx(idx); return true; }
      return false;
    },
    playPause: togglePlay,
    next: nextTrack,
    prev: prevTrack,
    stop: stopPlayback,
    getTracks: () => tracks.map((t) => ({ name: t.name, isVideo: t.isVideo })),
    addByUrl: (name: string, url: string, isVideo: boolean) => {
      setTracks((prev) => {
        const next = [...prev, { name, url, isVideo }];
        if (currentIdx < 0) setCurrentIdx(0);
        return next;
      });
    },
    setVolume: (v: number) => setVolumeState(Math.max(0, Math.min(1, v))),
  }));

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', position: 'relative' }}>
      <audio ref={mediaRef} preload="auto" />

      <span style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
        Media
      </span>

      <button
        onClick={() => fileRef.current?.click()}
        style={{ background: 'none', border: '1px solid var(--line)', borderRadius: '4px', color: 'var(--muted)', cursor: 'pointer', padding: '3px 6px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: 700, lineHeight: 1, width: 22, height: 22 }}
        title="Adicionar musica ou video"
      >
        +
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="audio/*,video/*,.mp3,.wav,.ogg,.flac,.m4a,.aac,.mp4,.wmv,.avi,.mkv,.webm,.mov"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => addFiles(e.target.files)}
      />

      {/* Mini video preview */}
      {isVideo && (
        <>
          <div
            style={{ width: vs.w, height: vs.h, borderRadius: 3, overflow: 'hidden', border: '1px solid var(--line)', background: '#000', flexShrink: 0, position: 'relative', cursor: 'pointer', transition: 'width 0.2s, height 0.2s' }}
            onClick={togglePlay}
            title="Clique para pausar/reproduzir"
          >
            <video ref={videoRef} preload="auto" style={{ width: '100%', height: '100%', objectFit: 'cover' }} playsInline muted={false} />
            {!isPlaying && (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000' }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="#fff"><path d="M4 2l10 6-10 6z" /></svg>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '1px' }}>
            {(['xs', 'sm', 'md', 'lg'] as const).map((s) => (
              <button key={s} onClick={() => setVideoSize(s)} style={{ background: videoSize === s ? 'var(--accent)' : 'transparent', color: videoSize === s ? 'var(--selection-fg)' : 'var(--muted)', border: 'none', borderRadius: 2, fontSize: '7px', fontWeight: 700, padding: '1px 3px', cursor: 'pointer', lineHeight: 1, fontFamily: 'inherit' }} title={`${VIDEO_SIZES[s].w}x${VIDEO_SIZES[s].h}`}>
                {VIDEO_SIZES[s].label}
              </button>
            ))}
          </div>
        </>
      )}

      {tracks.length > 0 && (
        <>
          <button onClick={prevTrack} style={ctrlBtn} title="Anterior">
            <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor"><path d="M3 3h2v10H3zM7 8l6-5v10z" /></svg>
          </button>
          <button onClick={togglePlay} style={ctrlBtn} title={isPlaying ? 'Pausar' : 'Tocar'}>
            {isPlaying ? (
              <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="2" width="4" height="12" rx="1" /><rect x="9" y="2" width="4" height="12" rx="1" /></svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2l10 6-10 6z" /></svg>
            )}
          </button>
          <button onClick={nextTrack} style={ctrlBtn} title="Proxima">
            <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor"><path d="M11 3h2v10h-2zM3 3l6 5-6 5z" /></svg>
          </button>

          <div onClick={seek} style={{ width: 80, height: 4, borderRadius: 2, background: 'var(--line)', cursor: 'pointer', flexShrink: 0 }}>
            <div style={{ height: '100%', width: `${progress * 100}%`, background: 'var(--accent)', borderRadius: 2, transition: 'width 0.1s linear' }} />
          </div>

          <span style={{ fontSize: '9px', color: 'var(--muted)', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'pointer' }} onClick={() => setShowList(!showList)} title={currentTrack?.name}>
            {isVideo && '🎬 '}{currentTrack?.name || ''}
          </span>

          <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
            <svg width="10" height="10" viewBox="0 0 16 16" fill="var(--muted)">
              <path d="M2 5h3l4-3v12L5 11H2a1 1 0 01-1-1V6a1 1 0 011-1z" />
              {volume > 0.3 && <path d="M10 4.5c1.5 1 1.5 5 0 6" fill="none" stroke="var(--muted)" strokeWidth="1.2" />}
              {volume > 0.6 && <path d="M12 3c2.5 2 2.5 7 0 9" fill="none" stroke="var(--muted)" strokeWidth="1.2" />}
            </svg>
            <input type="range" min="0" max="1" step="0.05" value={volume} onChange={(e) => setVolumeState(parseFloat(e.target.value))} style={{ width: 40, accentColor: 'var(--accent)', height: 3 }} />
          </div>
        </>
      )}

      {showList && tracks.length > 0 && (
        <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 6, padding: '4px 0', minWidth: 260, maxHeight: 250, overflowY: 'auto', zIndex: 1000, boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}>
          {tracks.map((t, i) => (
            <div key={i} onClick={() => { setCurrentIdx(i); setShowList(false); }} style={{ display: 'flex', alignItems: 'center', padding: '5px 10px', cursor: 'pointer', fontSize: '10px', color: i === currentIdx ? 'var(--accent)' : 'var(--ink)', fontWeight: i === currentIdx ? 700 : 400, gap: 6 }} onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-3)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
              <span style={{ fontSize: '10px', width: 14, textAlign: 'center' }}>{t.isVideo ? '🎬' : '🎵'}</span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{i === currentIdx && isPlaying ? '> ' : '  '}{t.name}</span>
              <span onClick={(e) => { e.stopPropagation(); removeTrack(i); }} style={{ color: 'var(--muted)', cursor: 'pointer', padding: '0 2px', fontSize: '10px' }}>x</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

MusicPlayer.displayName = 'MusicPlayer';
export default MusicPlayer;

const ctrlBtn: React.CSSProperties = {
  background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer',
  padding: '3px', display: 'flex', alignItems: 'center', justifyContent: 'center',
  borderRadius: '3px', width: 20, height: 20,
};
