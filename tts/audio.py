import numpy as np
from scipy import signal

def resample_linear(x, orig_sr, target_sr):
    if orig_sr == target_sr:
        return x.astype(np.float32)
    n = len(x)
    m = int(round(n * target_sr / orig_sr))
    if m <= 1 or n <= 1:
        return x.astype(np.float32)
    xp = np.linspace(0.0, 1.0, num=n, endpoint=True)
    fp = x.astype(np.float32)
    x_new = np.linspace(0.0, 1.0, num=m, endpoint=True)
    y = np.interp(x_new, xp, fp).astype(np.float32)
    return y

def concat_with_pause(chunks, pause_ms, sr=24000):
    parts = []
    for idx, c in enumerate(chunks):
        parts.append(np.asarray(c))
        if idx < len(chunks) - 1 and pause_ms > 0:
            parts.append(np.zeros(int(sr * pause_ms / 1000), dtype=np.float32))
    if parts:
        return np.concatenate(parts)
    return np.zeros(1, dtype=np.float32)

def denoise_8k(x, sr=8000):
    x = np.asarray(x, dtype=np.float32)
    if sr != 8000 or x.size == 0:
        return x
    b_hp, a_hp = signal.butter(2, 50, btype='high', fs=sr)
    try:
        y = signal.filtfilt(b_hp, a_hp, x)
    except Exception:
        y = signal.lfilter(b_hp, a_hp, x)
    b_lp, a_lp = signal.butter(6, 3600, btype='low', fs=sr)
    try:
        y = signal.filtfilt(b_lp, a_lp, y)
    except Exception:
        y = signal.lfilter(b_lp, a_lp, y)
    y = np.clip(y, -1.0, 1.0).astype(np.float32)
    return y
