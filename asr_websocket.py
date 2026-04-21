# -*- coding: utf-8 -*-
import argparse
import asyncio
import json
from torch import long
import websockets
from pathlib import Path
import datetime
import pytz

def get_local_model_path(model_name):
    """获取本地模型路径，如果不存在则返回原始模型名用于下载"""
    current_directory = Path.cwd()
    local_model_dir = current_directory / "iic" / model_name.split('/')[-1]
    
    # 检查本地模型目录是否存在且包含必要文件
    if local_model_dir.exists():
        # 检查关键文件是否存在
        config_file = local_model_dir / "configuration.json"
        model_file = local_model_dir / "model.pt"
        
        if config_file.exists() and model_file.exists():
            print(f"使用本地ASR模型: {local_model_dir}")
            return str(local_model_dir)
    
    print(f"本地模型不存在，将从远程下载到iic目录: {model_name}")
    # 如果本地不存在，使用modelscope下载到指定目录
    try:
        from modelscope import snapshot_download
        downloaded_path = snapshot_download(model_name, local_dir=str(current_directory / "iic" / model_name.split('/')[-1]))
        print(f"模型已下载到: {downloaded_path}")
        return downloaded_path
    except ImportError:
        print("modelscope未安装，使用原始模型名")
        return model_name
    except Exception as e:
        print(f"下载模型失败: {e}，使用原始模型名")
        return model_name

parser = argparse.ArgumentParser()
parser.add_argument(
    "--host", type=str, default="0.0.0.0", required=False, help="host ip, localhost, 0.0.0.0"
)
parser.add_argument("--port", type=int, default=10095, required=False, help="grpc server port")
parser.add_argument(
    "--asr_model",
    type=str,
    default="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    help="model from modelscope",
)
parser.add_argument("--asr_model_revision", type=str, default="v2.0.4", help="")
parser.add_argument(
    "--asr_model_online",
    type=str,
    default="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online",
    help="model from modelscope",
)
parser.add_argument("--asr_model_online_revision", type=str, default="v2.0.4", help="")
parser.add_argument(
    "--vad_model",
    type=str,
    default="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
    help="model from modelscope",
)
parser.add_argument("--vad_model_revision", type=str, default="v2.0.4", help="")
parser.add_argument(
    "--punc_model",
    type=str,
    default="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
    help="model from modelscope",
)
parser.add_argument("--punc_model_revision", type=str, default="v2.0.4", help="")
parser.add_argument("--ngpu", type=int, default=1, help="0 for cpu, 1 for gpu")
parser.add_argument("--device", type=str, default="cuda", help="cuda, cpu")
parser.add_argument("--ncpu", type=int, default=4, help="cpu cores")

args = parser.parse_args()

websocket_users = set()
# 全局变量，用于存储每个WebSocket连接的索引计数
websocket_indices = {}
# 全局变量，用于存储每个WebSocket连接的开始时间
start_times = {}
start_times_int = {}

print("model loading")
from funasr import AutoModel

# asr
model_asr = AutoModel(
    model=get_local_model_path(args.asr_model),
    model_revision=args.asr_model_revision,
    ngpu=args.ngpu,
    ncpu=args.ncpu,
    disable_update=True,
    device=args.device,
    disable_pbar=True,
    disable_log=True,
)
# asr streaming
model_asr_streaming = AutoModel(
    model=get_local_model_path(args.asr_model_online),
    model_revision=args.asr_model_online_revision,
    ngpu=args.ngpu,
    ncpu=args.ncpu,
    device=args.device,
    disable_pbar=True,
    disable_log=True,
)
# vad
# max_single_segment_time：单段音频的最大时长，默认60000毫秒（1
# 分钟）。
# max_end_silence_time：检测到结束静音的最大时长，默认800毫秒。
# max_start_silence_time：检测到开始静音的最大时长，默认3000毫秒。
# sil_to_speech_time_thres：从静音到语音的时间阈值，默认150毫秒。
# speech_to_sil_time_thres：从语音到静音的时间阈值，默认150毫秒。

model_vad = AutoModel(
    model=get_local_model_path(args.vad_model),
    model_revision=args.vad_model_revision,
    ngpu=args.ngpu,
    ncpu=args.ncpu,
    disable_update=True,
    device=args.device,
    disable_pbar=True,
    disable_log=True,
    energy_threshold=50,  # 能量阈值用于区分静音和有声片段
    #zero_cross_thres=0.5,  # 过零率用于区分清音和浊音
    max_end_silence_time=2500,  # 检测到结束静音的最大时长，默认800毫秒。
    # chunk_size=60,
)

if args.punc_model != "":
    model_punc = AutoModel(
        model=get_local_model_path(args.punc_model),
        model_revision=args.punc_model_revision,
        ngpu=args.ngpu,
        ncpu=args.ncpu,
        disable_update=True,
        device=args.device,
        disable_pbar=True,
        disable_log=True,
    )
else:
    model_punc = None

print("model loaded! only support one client at the same time now!!!!")


async def ws_reset(websocket):
    print("ws reset now, total num is ", len(websocket_users))

    websocket.status_dict_asr_online["cache"] = {}
    websocket.status_dict_asr_online["is_final"] = True
    websocket.status_dict_vad["cache"] = {}
    websocket.status_dict_vad["is_final"] = True
    websocket.status_dict_punc["cache"] = {}

    await websocket.close()


async def clear_websocket():
    for websocket in websocket_users:
        await ws_reset(websocket)
    websocket_users.clear()


async def ws_serve(websocket, path):
    frames = []
    frames_asr = []
    frames_asr_online = []
    global websocket_users, speech_start_i, websocket_indices, start_times, start_times_int
    # await clear_websocket()
    websocket_users.add(websocket)
    # 为新连接初始化索引计数为1
    websocket_indices[websocket] = 1
    start_times[websocket] = int(datetime.datetime.now(pytz.timezone('Asia/Shanghai')).timestamp() * 1000)
    websocket.status_dict_asr = {}
    websocket.status_dict_asr_online = {"cache": {}, "is_final": False}
    websocket.status_dict_vad = {"cache": {}, "is_final": False}
    websocket.status_dict_punc = {"cache": {}}
    websocket.chunk_interval = 10
    websocket.chunk_size = [5, 10, 5]
    websocket.is_speaking = True
    websocket.hotwords = "{\"安时达技术服务有限公司\":40,\"占啟\":40}"
    websocket.vad_pre_idx = 0
    speech_start = False
    speech_end_i = -1
    websocket.wav_name = "tel_stem"
    websocket.mode = "2pass"
    print("new user connected", flush=True)

    try:
        async for message in websocket:
            if isinstance(message, str):
                messagejson = json.loads(message)

                if "is_speaking" in messagejson:
                    websocket.is_speaking = messagejson["is_speaking"]
                    websocket.status_dict_asr_online["is_final"] = not websocket.is_speaking
                if "chunk_interval" in messagejson:
                    websocket.chunk_interval = messagejson["chunk_interval"]
                if "wav_name" in messagejson:
                    websocket.wav_name = messagejson.get("wav_name")
                if "chunk_size" in messagejson:
                    chunk_size = messagejson["chunk_size"]
                    if isinstance(chunk_size, str):
                        chunk_size = chunk_size.split(",")
                    websocket.status_dict_asr_online["chunk_size"] = [int(x) for x in chunk_size]
                else:
                    websocket.status_dict_asr_online["chunk_size"] = [5, 10, 5]
                if "encoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["encoder_chunk_look_back"] = messagejson[
                        "encoder_chunk_look_back"
                    ]
                if "decoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["decoder_chunk_look_back"] = messagejson[
                        "decoder_chunk_look_back"
                    ]
                if "hotword" in messagejson:
                    websocket.status_dict_asr["hotword"] = messagejson["hotwords"]
                if "mode" in messagejson:
                    websocket.mode = messagejson["mode"]

            websocket.status_dict_vad["chunk_size"] = int(
                websocket.status_dict_asr_online["chunk_size"][1] * 60 / websocket.chunk_interval
            )
            if len(frames_asr_online) > 0 or len(frames_asr) >= 0 or not isinstance(message, str):
                if not isinstance(message, str):
                    frames.append(message)
                    duration_ms = len(message) // 32
                    websocket.vad_pre_idx += duration_ms

                    # asr online
                    frames_asr_online.append(message)
                    websocket.status_dict_asr_online["is_final"] = speech_end_i != -1
                    if len(frames_asr_online) % websocket.chunk_interval == 0 or websocket.status_dict_asr_online["is_final"]:
                        if websocket.mode == "2pass" or websocket.mode == "online":
                            audio_in = b"".join(frames_asr_online)
                            try:
                                await async_asr_online(websocket, audio_in)
                            except Exception as e:
                                print(f"error in asr streaming: {e}, {websocket.status_dict_asr_online}")
                        frames_asr_online = []
                    if speech_start:
                        frames_asr.append(message)
                    # vad online
                    speech_start_i = -1
                    try:
                        speech_start_i, speech_end_i = await async_vad(websocket, message)
                    except:
                        print("error in vad")
                    if speech_start_i != -1:
                        speech_start = True
                        beg_bias = (websocket.vad_pre_idx - speech_start_i) // duration_ms
                        frames_pre = frames[-beg_bias:]
                        frames_asr = []
                        frames_asr.extend(frames_pre)
                        print("vad start point")
                        
                        # 记录语音开始的东八区时间戳（13位毫秒级）
                        current_time = int(datetime.datetime.now( pytz.timezone('Asia/Shanghai')).timestamp() * 1000)
                        start_times_int[websocket] = current_time-start_times.get(websocket, current_time)
                        
                        message = json.dumps(
                            {
                                "text": "--start--",
                                "type": "start",
                                "start_time": current_time-start_times.get(websocket, current_time),
                                "end_time": 0,
                                "index": int(websocket_indices[websocket]),
                                "wav_name": websocket.wav_name
                            }, ensure_ascii=False
                        )
                       
                        await websocket.send(message)
                # asr punc offline
                if speech_end_i != -1 or not websocket.is_speaking:
                    print("vad end point")
                    if websocket.mode == "2pass" or websocket.mode == "offline":
                        audio_in = b"".join(frames_asr)
                        try:
                            await async_asr(websocket, audio_in)
                        except:
                            print("error in asr offline")
                    frames_asr = []
                    speech_start = False
                    frames_asr_online = []
                    websocket.status_dict_asr_online["cache"] = {}
                    websocket.status_dict_punc["cache"] = {}
                    if not websocket.is_speaking:
                        websocket.vad_pre_idx = 0
                        frames = []
                        websocket.status_dict_vad["cache"] = {}
                    else:
                        frames = frames[-20:]
                    # 获取语音结束的东八区时间戳（13位毫秒级）
                    end_time = int(datetime.datetime.now( pytz.timezone('Asia/Shanghai')).timestamp() * 1000)
                    
                    # 获取开始时间，如果没有记录则使用当前时间
                    start_time = start_times.get(websocket, end_time)
                    
                    # 获取当前索引
                    current_index = websocket_indices[websocket]
                    
                    message = json.dumps(
                        {
                            "text": "--end--",
                            "type": "end",
                            "start_time": start_times_int.get(websocket,0),
                            "end_time": end_time-start_time,
                            "index": current_index,
                            "wav_name": websocket.wav_name
                        }, ensure_ascii=False
                    )
                    await websocket.send(message)
                    
                    # 索引递增，为下一次语音识别做准备
                    websocket_indices[websocket] += 1

    except websockets.ConnectionClosed:
        print("ConnectionClosed...", websocket_users, flush=True)
        await ws_reset(websocket)
        websocket_users.remove(websocket)
        # 清理索引和时间戳记录
        if websocket in websocket_indices:
            del websocket_indices[websocket]
        if websocket in start_times:
            del start_times[websocket]
        if websocket in start_times_int:
            del start_times_int[websocket]
    except websockets.InvalidState:
        print("InvalidState...")
    except Exception as e:
        print("Exception:", e)


async def async_vad(websocket, audio_in):
    segments_result = model_vad.generate(input=audio_in, **websocket.status_dict_vad)[0]["value"]

    speech_start = -1
    speech_end = -1

    if len(segments_result) == 0 or len(segments_result) > 1:
        return speech_start, speech_end
    if segments_result[0][0] != -1:
        speech_start = segments_result[0][0]
    if segments_result[0][1] != -1:
        speech_end = segments_result[0][1]
    return speech_start, speech_end


async def async_asr(websocket, audio_in):
    if len(audio_in) > 0:
        rec_result = model_asr.generate(input=audio_in, **websocket.status_dict_asr)[0]
        if model_punc is not None and len(rec_result["text"]) > 0:
            try:
                rec_result = model_punc.generate(
                    input=rec_result["text"], **websocket.status_dict_punc
                )[0]
            except Exception as e:
                print(f"error in punc: {e}")
        if len(rec_result["text"]) > 0:
            end_time = int(datetime.datetime.now( pytz.timezone('Asia/Shanghai')).timestamp() * 1000)
                    
            # 获取开始时间，如果没有记录则使用当前时间
            start_time = start_times.get(websocket, end_time)
            
            # 获取当前索引
            current_index = websocket_indices.get(websocket, 1)
            
            # print("offline", rec_result)
            # mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
            message = json.dumps(
                {
                    "text": rec_result["text"],
                    "type": "speech",
                    "start_time": start_times_int.get(websocket,0),
                    "end_time": end_time-start_time,
                    "index": current_index,
                    "wav_name": websocket.wav_name
                }, ensure_ascii=False
            )
            await websocket.send(message)

    # else:
    #     mode = "2pass-offline" if "2pass" in websocket.mode else websocket.mode
    #     message = json.dumps(
    #         {
    #             "text": "",
    #             "wav_name": websocket.wav_name
    #         }, ensure_ascii=False
    #     )
    #     await websocket.send(message)


async def async_asr_online(websocket, audio_in):
    if len(audio_in) > 0:
        # 获取实时推理结果
        rec_result = model_asr_streaming.generate(
            input=audio_in, **websocket.status_dict_asr_online
        )[0]
        
        # 如果是2pass模式且已经是最终结果，则不发送实时推理结果
        if websocket.mode == "2pass" and websocket.status_dict_asr_online.get("is_final", False):
            return
        
        # 如果有文本结果，发送实时推理状态
        if len(rec_result["text"]):
            # 获取当前东八区时间戳作为结束时间（13位毫秒级）
            end_time = int(datetime.datetime.now( pytz.timezone('Asia/Shanghai')).timestamp() * 1000)
                    
            # 获取开始时间，如果没有记录则使用当前时间
            start_time = start_times.get(websocket, end_time)
            
            # 获取当前索引
            current_index = websocket_indices.get(websocket, 1)
            
            message = json.dumps(
                {
                    "text": rec_result["text"],
                    "type": "reasoning",  # 使用reasoning类型表示实时推理过程
                    "start_time": start_times_int.get(websocket,0),
                    "end_time": end_time-start_time,
                    "index": current_index,
                    "wav_name": websocket.wav_name
                }, ensure_ascii=False
            )
            await websocket.send(message)


start_server = websockets.serve(
    ws_serve, args.host, args.port, subprotocols=["binary"], ping_interval=None
)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
print(f"======== Running on http://{args.host}:{args.port} ========")
