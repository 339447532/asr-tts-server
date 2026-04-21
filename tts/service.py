import io
import os
import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline, KModel

from .preprocess import (
    get_lang_descriptor,
    convert_units,
    remove_linebreaks,
    convert_english_punct_to_chinese,
    convert_special_characters,
    process_character_by_character,
    split_long_text,
)
from .audio import resample_linear, concat_with_pause, denoise_8k

voice_zf = "zf_001"
voice_af = 'af_maple'
voice_zf_tensor = torch.load(f'ckpts/kokoro-v1.1/voices/{voice_zf}.pt', weights_only=True)
voice_af_tensor = torch.load(f'ckpts/kokoro-v1.1/voices/{voice_af}.pt', weights_only=True)

repo_id = 'hexgrad/Kokoro-82M-v1.1-zh'
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model_path = 'ckpts/kokoro-v1.1/kokoro-v1_1-zh.pth'
config_path = 'ckpts/kokoro-v1.1/config.json'
model = KModel(model=model_path, config=config_path, repo_id=repo_id).to(device).eval()

en_pipeline = KPipeline(lang_code='a', repo_id=repo_id, model=False)
def en_callable(text):
    if text == 'Kokoro':
        return 'kˈOkəɹO'
    elif text == 'Sol':
        return 'sˈOl'
    return next(en_pipeline(text)).phonemes

zh_pipeline = KPipeline(lang_code='z', repo_id=repo_id, model=model, en_callable=en_callable)

def synthesize(text, language='ZH', speed=1.1, max_chunk_len=150, chunk_pause_ms=100, target_sr=8000):
    lang_code = get_lang_descriptor(language)
    voice_tensor = voice_af_tensor if lang_code in ('a','b') else voice_zf_tensor
    def speed_callable(len_ps):
        base = 0.8
        if len_ps <= 83:
            base = 1
        elif len_ps < 183:
            base = 1 - (len_ps - 83) / 500
        return base * 1.1 * speed
    s = convert_units(text)
    s = remove_linebreaks(s)
    s = convert_english_punct_to_chinese(s)
    s = convert_special_characters(s)
    s = process_character_by_character(s)
    pieces = split_long_text(s, max_len=max_chunk_len)
    wavs = []
    for piece in pieces:
        for result in zh_pipeline(piece, voice=voice_tensor, speed=speed_callable):
            wavs.append(np.asarray(result.audio))
    full_wav = concat_with_pause(wavs, chunk_pause_ms, sr=24000)
    wav_target = resample_linear(full_wav, 24000, target_sr)
    if target_sr == 8000:
        wav_target = denoise_8k(wav_target, sr=target_sr)
    buf = io.BytesIO()
    sf.write(buf, wav_target.astype(np.float32), target_sr, format='WAV')
    buf.seek(0)
    return buf.getvalue()
