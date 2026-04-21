import os
from aiohttp import web
from tts.service import synthesize

async def websocket_speech(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = msg.json()
                text = data.get('text')
                language = data.get('language', 'ZH')
                speed_req = data.get('speed', 1.0)
                max_chunk = int(os.getenv('MAX_CHUNK_LEN', '150'))
                pause_ms = int(os.getenv('CHUNK_PAUSE_MS', '100'))
                target_sr = data.get('target', 8000)
                audio_bytes = synthesize(text, language, speed_req, max_chunk, pause_ms, target_sr)
                await ws.send_bytes(audio_bytes)
            elif msg.type == web.WSMsgType.ERROR:
                await ws.send_json({'error': 'ws error'})
    except Exception as e:
        await ws.send_json({'error': str(e)})
    finally:
        pass
    return ws

app = web.Application()
app.router.add_route('GET', '/', websocket_speech)

if __name__ == '__main__':
    synthesize('占啟您好')
    web.run_app(app, port=8000)
