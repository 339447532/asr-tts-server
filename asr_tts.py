# -*- coding: utf-8 -*-
import os
import uuid
import io
from tts.service import synthesize
import torch
from flask import request, Flask, jsonify, send_file, send_from_directory, Response
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from modelscope import snapshot_download


app = Flask(__name__)

app.config['SECRET_KEY'] = 'asd.sec'
UPLOAD_FOLDER = 'upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
model_dir = snapshot_download('iic/SenseVoiceSmall', local_dir="iic/SenseVoiceSmall")

asr_model = AutoModel(
    model=model_dir,
    disable_update=True,
    trust_remote_code=True,
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 30000},
    device="cuda" if torch.cuda.is_available() else "cpu",
)
# 确保wav_dir目录存在
os.makedirs('wav_dir', exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        
        temp_file_path = f'wav_dir/{uuid.uuid4()}_temp_audio.wav'
        file.save(temp_file_path)

        res = asr_model.generate(
            input=temp_file_path,
            cache={},
            language="zh",  # "zh","zn", "en", "yue", "ja", "ko", "nospeech"
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,  #
            merge_length_s=15,
        )
        text = rich_transcription_postprocess(res[0]["text"])
        print("say:  " + text)
        os.remove(temp_file_path)
        response = jsonify({"text": text})
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response


@app.route("/speech", methods=['GET'])
def speech():
    text = request.args.get('text')
    language = request.args.get('language', 'ZH')
    target_sr = request.args.get('target', 8000)
    speed_req = float(request.args.get('speed', 1.0))
    max_chunk = int(os.getenv('MAX_CHUNK_LEN', '150'))
    pause_ms = int(os.getenv('CHUNK_PAUSE_MS', '100'))
    audio_bytes = synthesize(text, language, speed_req, max_chunk, pause_ms, target_sr)
   
    # 将音频字节流转换为WAV格式的字节流
    wav_buffer = io.BytesIO(audio_bytes)
    wav_buffer.seek(0)
    
    # 返回音频流
    return Response(
        wav_buffer.getvalue(),
        mimetype='audio/wav',
        headers={
            'Content-Disposition': 'inline; filename="speech.wav"',
            'Content-Length': str(len(wav_buffer.getvalue()))
        }
    )


@app.route("/speech_url", methods=['GET'])
def speech_url():
    text = request.args.get('text')
    language = request.args.get('language', 'ZH')
    target_sr = request.args.get('target', 8000)
    speed_req = float(request.args.get('speed', 1.0))
    max_chunk = int(os.getenv('MAX_CHUNK_LEN', '150'))
    pause_ms = int(os.getenv('CHUNK_PAUSE_MS', '100'))

    # 确保wav_dir存在
    os.makedirs('wav_dir', exist_ok=True)

    # 生成唯一的文件名
    file_name = f'{uuid.uuid4()}.wav'
    output_path = f'wav_dir/{file_name}'
    audio_bytes = synthesize(text, language, speed_req, max_chunk, pause_ms, target_sr)
    
    # 保存音频字节流到文件
    with open(output_path, 'wb') as f:
        f.write(audio_bytes)

    # 构建文件的URL。这需要根据你的实际部署环境进行调整
    file_url = f"{request.url_root}speeches/{file_name}"

    # 返回包含文件URL的JSON响应
    return jsonify({"file_url": file_url})


# 添加一个新的路由来提供生成的语音文件
@app.route('/speeches/<filename>')
def serve_speech_files(filename):
    return send_from_directory('wav_dir', filename, mimetype='audio/wav')

if __name__ == '__main__':
    app.run(
        debug=False,
        threaded=True,
        host="0.0.0.0",
        port=1377
    )
