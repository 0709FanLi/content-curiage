"""TTS 语音合成服务。

- Sambert：通过 DashScope SDK（`dashscope.audio.tts.SpeechSynthesizer`）
- CosyVoice v3：按用户提供的 `api-voice.txt`，通过 DashScope SDK 调用（优先 tts_v2，其次 Generation.call）
"""

import os
import asyncio
import uuid
import tempfile
from typing import Optional, List, Dict, Any, Tuple
import structlog

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.utils.exceptions import ExternalServiceError
from src.services.oss_service import OSSService

logger = structlog.get_logger(__name__)


# Sambert 预定义音色列表
# 参考：https://help.aliyun.com/zh/model-studio/sambert-python-sdk
VOICE_LIST = [
    # 中文女声
    {"id": "sambert-zhichu-v1", "name": "知楚", "language": "zh", "gender": "female", "description": "温柔知性女声"},
    {"id": "sambert-zhiqi-v1", "name": "知琪", "language": "zh", "gender": "female", "description": "甜美活泼女声"},
    {"id": "sambert-zhiru-v1", "name": "知茹", "language": "zh", "gender": "female", "description": "亲切自然女声"},
    {"id": "sambert-zhixiao-v1", "name": "知晓", "language": "zh", "gender": "female", "description": "清新甜美女声"},
    {"id": "sambert-zhiya-v1", "name": "知雅", "language": "zh", "gender": "female", "description": "优雅知性女声"},
    {"id": "sambert-zhiying-v1", "name": "知莹", "language": "zh", "gender": "female", "description": "活力年轻女声"},
    {"id": "sambert-zhina-v1", "name": "知娜", "language": "zh", "gender": "female", "description": "可爱萌系女声"},
    {"id": "sambert-zhijing-v1", "name": "知静", "language": "zh", "gender": "female", "description": "沉稳大气女声"},
    {"id": "sambert-zhistella-v1", "name": "Stella", "language": "zh", "gender": "female", "description": "英文女声"},
    {"id": "sambert-zhimiao-emo-v1", "name": "知妙", "language": "zh", "gender": "female", "description": "情感丰富女声"},
    # 中文男声
    {"id": "sambert-zhinan-v1", "name": "知南", "language": "zh", "gender": "male", "description": "成熟稳重男声"},
    {"id": "sambert-zhide-v1", "name": "知德", "language": "zh", "gender": "male", "description": "儒雅温和男声"},
    {"id": "sambert-zhijia-v1", "name": "知佳", "language": "zh", "gender": "male", "description": "阳光活力男声"},
    {"id": "sambert-zhixiang-v1", "name": "知祥", "language": "zh", "gender": "male", "description": "沉稳大气男声"},
    {"id": "sambert-zhihao-v1", "name": "知浩", "language": "zh", "gender": "male", "description": "磁性魅力男声"},
    {"id": "sambert-zhiming-v1", "name": "知明", "language": "zh", "gender": "male", "description": "专业播音男声"},
    {"id": "sambert-zhiyuan-v1", "name": "知远", "language": "zh", "gender": "male", "description": "厚重有力男声"},
    {"id": "sambert-zhilun-v1", "name": "知伦", "language": "zh", "gender": "male", "description": "年轻活力男声"},
    {"id": "sambert-zhifei-v1", "name": "知飞", "language": "zh", "gender": "male", "description": "青春阳光男声"},
    {"id": "sambert-zhida-v1", "name": "知达", "language": "zh", "gender": "male", "description": "沉稳大方男声"},
    # 儿童声
    {"id": "sambert-zhimao-v1", "name": "知猫", "language": "zh", "gender": "child", "description": "可爱童声"},
    {"id": "sambert-zhimo-v1", "name": "知墨", "language": "zh", "gender": "child", "description": "活泼童声"},
    {"id": "sambert-zhishu-v1", "name": "知舒", "language": "zh", "gender": "child", "description": "清脆童声"},
    # 英文音色
    {"id": "sambert-beth-v1", "name": "Beth", "language": "en", "gender": "female", "description": "英文女声"},
    {"id": "sambert-betty-v1", "name": "Betty", "language": "en", "gender": "female", "description": "英文甜美女声"},
    {"id": "sambert-cally-v1", "name": "Cally", "language": "en", "gender": "female", "description": "英文清新女声"},
    {"id": "sambert-cindy-v1", "name": "Cindy", "language": "en", "gender": "female", "description": "英文活泼女声"},
    {"id": "sambert-eva-v1", "name": "Eva", "language": "en", "gender": "female", "description": "英文优雅女声"},
    {"id": "sambert-donna-v1", "name": "Donna", "language": "en", "gender": "female", "description": "英文知性女声"},
    {"id": "sambert-brian-v1", "name": "Brian", "language": "en", "gender": "male", "description": "英文男声"},
]


class TTSService:
    """TTS 语音合成服务类（阿里云百炼 Sambert 模型）
    
    使用 DashScope SDK 的 SpeechSynthesizer.call() 方法进行语音合成
    这是一个简单的同步 HTTP API，无需建立 WebSocket 连接
    """

    def __init__(self) -> None:
        """初始化 TTS 服务"""
        self.api_key = settings.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY") or ""
        self.default_model = "sambert-zhichu-v1"  # 默认音色
        self.timeout = 60  # 超时时间（秒）
        self.oss_service = OSSService()
        # CosyVoice（DashScope）TTS：按用户提供的接口文档，使用 DashScope Python SDK
        self.cosyvoice_model = os.getenv("COSYVOICE_MODEL", "cosyvoice-v3-plus")
        self.cosyvoice_voice = os.getenv("COSYVOICE_VOICE", "longanhuan")
        self.cosyvoice_format = os.getenv("COSYVOICE_FORMAT", "wav").lower()
        self.cosyvoice_sample_rate = int(os.getenv("COSYVOICE_SAMPLE_RATE", "48000"))
        self.cosyvoice_emotion = os.getenv("COSYVOICE_EMOTION", "neutral").strip() or None
        # 文档：volume 0~100，默认 50
        self.cosyvoice_volume = int(os.getenv("COSYVOICE_VOLUME", "50"))

        # 兼容：保留旧的调用配置（外部仍用 synthesize_qwen3_tts_flash），但内部实现已切到 CosyVoice
        self.qwen_tts_model = os.getenv("QWEN_TTS_MODEL", "qwen3-tts-flash")
        self.qwen_tts_voice = os.getenv("QWEN_TTS_VOICE", "Elias")
        self._qwen_tts_semaphore = asyncio.Semaphore(
            int(os.getenv("TTS_CONCURRENCY", "2"))
        )
        self.qwen_tts_generation_url = os.getenv("QWEN_TTS_GENERATION_URL", "").rstrip("/")

    def get_voices(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取可用音色列表
        
        Args:
            language: 语言过滤（可选），如 "zh", "en"
            
        Returns:
            音色列表
        """
        if language:
            return [v for v in VOICE_LIST if v["language"] == language]
        return VOICE_LIST

    def get_voice_by_id(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取音色信息
        
        Args:
            voice_id: 音色 ID
            
        Returns:
            音色信息，不存在返回 None
        """
        for voice in VOICE_LIST:
            if voice["id"] == voice_id:
                return voice
        return None

    async def synthesize(
        self,
        text: str,
        voice: str = "sambert-zhichu-v1",
        format: str = "mp3",
        sample_rate: int = 16000,
        volume: int = 50,
        speech_rate: int = 0,
        pitch_rate: int = 0,
    ) -> Dict[str, Any]:
        """
        文本转语音（使用 Sambert 模型，简单 HTTP API）
        
        Args:
            text: 要合成的文本
            voice: 音色 ID（如 sambert-zhichu-v1）
            format: 输出格式（pcm, wav, mp3）
            sample_rate: 采样率（16000, 48000）
            volume: 音量（0-100）
            speech_rate: 语速（-500 到 500，0为正常）
            pitch_rate: 音调（-500 到 500，0为正常）
            
        Returns:
            包含音频 URL、时长等信息的字典
        """
        if not self.api_key:
            raise ExternalServiceError("TTS", "API Key 未配置")

        try:
            # 动态导入 dashscope SDK
            import dashscope
            from dashscope.audio.tts import SpeechSynthesizer
            
            dashscope.api_key = self.api_key
            
            # 如果传入的是简化的音色名，尝试匹配完整模型名
            if not voice.startswith("sambert-"):
                # 尝试在 VOICE_LIST 中查找
                for v in VOICE_LIST:
                    if v["name"].lower() == voice.lower() or v["id"].endswith(f"-{voice.lower()}-v1"):
                        voice = v["id"]
                        break
                else:
                    voice = self.default_model
            
            # 在线程池中运行同步调用
            def do_synthesis():
                return SpeechSynthesizer.call(
                    model=voice,
                    text=text,
                    sample_rate=sample_rate,
                    format=format,
                    volume=volume,
                    rate=speech_rate,
                    pitch=pitch_rate,
                )
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, do_synthesis)
            
            # 检查结果
            audio_data = result.get_audio_data()
            if audio_data is None:
                response = result.get_response()
                error_msg = response.get("message", "未知错误") if response else "合成失败"
                raise ExternalServiceError("TTS", error_msg)
            
            # 上传到 OSS
            file_ext = format.lower()
            file_name = f"{uuid.uuid4()}.{file_ext}"
            
            # 使用 BytesIO 作为文件对象
            from io import BytesIO
            audio_stream = BytesIO(audio_data)
            
            # 获取 MIME 类型
            mime_types = {
                "mp3": "audio/mpeg",
                "wav": "audio/wav",
                "pcm": "audio/pcm",
            }
            content_type = mime_types.get(file_ext, "audio/mpeg")
            
            # 上传文件（同步方法）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.oss_service.upload_file(
                    file_data=audio_stream,
                    filename=file_name,
                    category='tts',
                    content_type=content_type
                )
            )
            
            # 获取 URL
            if isinstance(result, dict):
                audio_url = result.get('url', '')
            else:
                audio_url = str(result)
            
            # 估算时长
            duration_ms = self._estimate_duration(text, speech_rate)
            
            logger.info(
                "TTS 合成成功",
                voice=voice,
                text_length=len(text),
                audio_size=len(audio_data),
                duration_ms=duration_ms
            )
            
            return {
                "url": audio_url,
                "duration_ms": duration_ms,
                "text": text,
                "voice": voice,
                "format": format,
            }
            
        except ImportError:
            logger.error("DashScope SDK not installed")
            raise ExternalServiceError("TTS", "DashScope SDK 未安装，请运行: pip install dashscope")
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"TTS service error: {e}", exc_info=True)
            raise ExternalServiceError("TTS", f"服务异常: {str(e)}")

    @staticmethod
    def _estimate_text_duration_sec(text: str) -> float:
        """粗略估算中文口播时长（秒）.

        说明：用于计算语速/目标时长控制的初始值；最终仍以音频后处理对齐。

        Args:
            text: 口播文本

        Returns:
            估算时长（秒）
        """
        # 经验值：中文约每秒 4 字左右
        chars_per_second = 4.0
        safe_len = max(1, len(text.strip()))
        return float(safe_len / chars_per_second)

    @staticmethod
    def _compute_speed_for_target(
        estimated_sec: float,
        target_sec: float,
    ) -> float:
        """根据目标时长计算 TTS speed 参数.

        Args:
            estimated_sec: 估算时长（秒）
            target_sec: 目标时长（秒）

        Returns:
            speed（OpenAI 兼容：0.25~4.0，保守限制到 0.5~2.0）
        """
        if target_sec <= 0:
            return 1.0
        ratio = estimated_sec / target_sec
        # ratio>1 表示文本偏长，需要加速（speed>1）
        speed = max(0.5, min(2.0, float(ratio)))
        return speed

    @staticmethod
    def _build_qwen_audio_speech_payload(
        *,
        model: str,
        text: str,
        voice: str,
        speed: float,
        sample_rate: int,
        audio_format: str,
    ) -> Dict[str, Any]:
        """构建 OpenAI 兼容模式的 audio/speech payload."""
        return {
            "model": model,
            "input": text,
            "voice": voice,
            "speed": speed,
            # OpenAI 兼容字段名：response_format（DashScope 兼容通常支持）
            "response_format": audio_format,
            # 采样率并非 OpenAI 标准字段，但部分兼容实现支持；不支持时会被忽略
            "sample_rate": sample_rate,
        }

    @staticmethod
    def _probe_wav_duration_sec(wav_path: str) -> float:
        """读取 wav 文件时长（秒）."""
        import json
        import subprocess

        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            wav_path,
        ]
        result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        try:
            return float((data.get("format") or {}).get("duration") or 0.0)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _ffmpeg_fit_audio_to_duration(
        *,
        input_wav: str,
        output_wav: str,
        target_sec: float,
        sample_rate: int = 44100,
    ) -> None:
        """用 ffmpeg 将音频严格对齐到目标时长（裁剪/补静音）."""
        import subprocess

        target_sec = max(0.1, float(target_sec))
        # 先裁剪，再补齐到目标时长
        afilter = (
            f"atrim=0:{target_sec:.6f},asetpts=PTS-STARTPTS,"
            f"apad=pad_dur={target_sec:.6f}"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_wav,
            "-af",
            afilter,
            "-t",
            f"{target_sec:.6f}",
            "-ac",
            "1",
            "-ar",
            str(int(sample_rate)),
            output_wav,
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _call_cosyvoice_tts(
        self,
        *,
        text: str,
        voice: str,
        sample_rate: int,
        audio_format: str,
        emotion: Optional[str],
        speed: float,
        volume: int,
    ) -> bytes:
        """调用 CosyVoice（DashScope Python SDK）生成音频 bytes。

        依据用户提供的 `api-voice.txt`：
        - 优先使用 `dashscope.audio.tts_v2.SpeechSynthesizer`
        - 回退到 `dashscope.Generation.call`
        """
        if not self.api_key:
            raise ExternalServiceError("TTS", "DASHSCOPE_API_KEY 未配置")

        try:
            import dashscope  # type: ignore
        except ImportError as e:
            raise ExternalServiceError("TTS", f"DashScope SDK 未安装: {str(e)}")

        dashscope.api_key = self.api_key
        loop = asyncio.get_event_loop()

        def _call_sdk() -> bytes:
            # 优先使用 tts_v2：按 api-voice.txt 的 Python 示例思路
            from dashscope.audio.tts_v2 import SpeechSynthesizer  # type: ignore
            from dashscope.audio.tts_v2.speech_synthesizer import AudioFormat  # type: ignore

            def pick_audio_format(fmt: str, sr: int) -> AudioFormat:
                fmt = (fmt or "wav").lower()
                sr = int(sr or 48000)
                if fmt == "wav":
                    return getattr(AudioFormat, f"WAV_{sr}HZ_MONO_16BIT")
                if fmt == "mp3":
                    # SDK 的 MP3 默认 128/256kbps，选与采样率匹配的常用档
                    kbps = 128 if sr in (8000, 16000) else 256
                    return getattr(AudioFormat, f"MP3_{sr}HZ_MONO_{kbps}KBPS")
                if fmt == "pcm":
                    return getattr(AudioFormat, f"PCM_{sr}HZ_MONO_16BIT")
                # 兜底
                return AudioFormat.DEFAULT

            instruction = None
            if emotion:
                # 文档提示可用 instruct / instruction 控制情感（不同模型支持度不同）
                instruction = f"你说话的情感是{emotion}。"

            synthesizer = SpeechSynthesizer(
                model=self.cosyvoice_model,
                voice=voice,
                format=pick_audio_format(audio_format, sample_rate),
                volume=int(volume),
                speech_rate=float(speed),
                instruction=instruction,
            )
            resp = synthesizer.call(text=text, timeout_millis=int(self.timeout * 1000))

            # SDK 可能直接返回 bytes
            if isinstance(resp, (bytes, bytearray)):
                return bytes(resp)

            audio_data = resp.get_audio_data() if hasattr(resp, "get_audio_data") else None
            if isinstance(audio_data, (bytes, bytearray)):
                return bytes(audio_data)

            response = resp.get_response() if hasattr(resp, "get_response") else None
            msg = ""
            if isinstance(response, dict):
                msg = str(response.get("message") or response.get("Message") or response)
            status_code = getattr(resp, "status_code", None)
            message = getattr(resp, "message", None)
            raise ExternalServiceError(
                "TTS",
                f"CosyVoice 合成失败（status_code={status_code}, message={message}, response={msg}）",
            )

        try:
            return await loop.run_in_executor(None, _call_sdk)
        except ExternalServiceError:
            raise
        except Exception as e:
            raise ExternalServiceError("TTS", f"CosyVoice SDK 调用失败: {str(e)}")

    async def synthesize_cosyvoice_to_bytes(
        self,
        *,
        text: str,
        target_duration_sec: float,
        voice: Optional[str] = None,
        sample_rate: Optional[int] = None,
        audio_format: Optional[str] = None,
        emotion: Optional[str] = None,
        volume: Optional[int] = None,
    ) -> Dict[str, Any]:
        """使用 CosyVoice 生成音频 bytes（不依赖 OSS，便于本地测试）.

        Args:
            text: 口播文本
            target_duration_sec: 目标时长（秒）
            voice: 音色（默认取 COSYVOICE_VOICE）
            sample_rate: 采样率（默认取 COSYVOICE_SAMPLE_RATE）
            audio_format: 音频格式（默认取 COSYVOICE_FORMAT）
            emotion: 情感（可选，默认取 COSYVOICE_EMOTION）
            volume: 音量 0~100（默认取 COSYVOICE_VOLUME）

        Returns:
            dict: {audio_bytes, duration_sec, model, voice, sample_rate, format}
        """
        if not text.strip():
            raise ExternalServiceError("TTS", "口播文本为空")

        final_voice = voice or self.cosyvoice_voice
        final_sample_rate = int(sample_rate or self.cosyvoice_sample_rate)
        final_format = str(audio_format or self.cosyvoice_format).lower()
        final_emotion = emotion if emotion is not None else self.cosyvoice_emotion
        final_volume = int(volume if volume is not None else self.cosyvoice_volume)

        target_sec = max(0.1, float(target_duration_sec))
        estimated_sec = self._estimate_text_duration_sec(text)
        speed = self._compute_speed_for_target(estimated_sec, target_sec)
        # 默认限制语速，避免过快导致“听不清”
        min_rate = float(os.getenv("COSYVOICE_SPEECH_RATE_MIN", "0.9"))
        max_rate = float(os.getenv("COSYVOICE_SPEECH_RATE_MAX", "1.25"))
        speed = max(min_rate, min(max_rate, float(speed)))

        # neutral/空情感时，不传 instruction，避免模型误解
        if final_emotion and str(final_emotion).strip().lower() in {"neutral", "none", "null"}:
            final_emotion = None

        logger.info(
            "CosyVoice TTS request",
            model=self.cosyvoice_model,
            voice=final_voice,
            target_sec=target_sec,
            estimated_sec=float(estimated_sec),
            speech_rate=float(speed),
            sample_rate=int(final_sample_rate),
            text_len=len(text),
        )

        async with self._qwen_tts_semaphore:
            audio_bytes = await self._call_cosyvoice_tts(
                text=text,
                voice=final_voice,
                sample_rate=final_sample_rate,
                audio_format=final_format,
                emotion=final_emotion,
                speed=speed,
                volume=final_volume,
            )

        # 写入临时文件并严格对齐到目标时长（解决返回时长误差）
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_path = os.path.join(tmp_dir, f"raw.{final_format}")
            fixed_path = os.path.join(tmp_dir, "fixed.wav")
            with open(raw_path, "wb") as f:
                f.write(audio_bytes)

            # 为了拼接/替换音轨，统一产出 wav
            self._ffmpeg_fit_audio_to_duration(
                input_wav=raw_path,
                output_wav=fixed_path,
                target_sec=target_sec,
                sample_rate=final_sample_rate,
            )

            duration_sec = self._probe_wav_duration_sec(fixed_path)
            with open(fixed_path, "rb") as f:
                final_audio = f.read()

        return {
            "audio_bytes": final_audio,
            "duration_sec": float(duration_sec or target_sec),
            "model": self.cosyvoice_model,
            "voice": final_voice,
            "sample_rate": int(final_sample_rate),
            "format": "wav",
        }

    async def synthesize_qwen3_tts_flash(
        self,
        *,
        text: str,
        target_duration_sec: float,
        voice: Optional[str] = None,
        sample_rate: int = 48000,
    ) -> Dict[str, Any]:
        """生成 WAV 并上传 OSS（用于视频配音流水线）。

        兼容说明：
        - 方法名保留为 synthesize_qwen3_tts_flash，避免影响现有调用链
        - 内部实现已切换为 CosyVoice-v3-plus（见 _call_cosyvoice_tts）

        Args:
            text: 口播文本
            target_duration_sec: 目标时长（秒），由视频 ffprobe 真实时长决定
            voice: 音色，默认取环境变量 COSYVOICE_VOICE（回退 QWEN_TTS_VOICE）
            sample_rate: 采样率（默认 48000）

        Returns:
            dict: {url, duration_sec, model, voice, sample_rate}
        """
        if not text.strip():
            raise ExternalServiceError("TTS", "口播文本为空")

        final_voice = voice or self.cosyvoice_voice or self.qwen_tts_voice
        target_sec = max(0.1, float(target_duration_sec))

        cosy_result = await self.synthesize_cosyvoice_to_bytes(
            text=text,
            target_duration_sec=target_sec,
            voice=final_voice,
            sample_rate=sample_rate,
            audio_format="wav",
        )
        final_audio = bytes(cosy_result["audio_bytes"])
        duration_sec = float(cosy_result["duration_sec"])

        # 上传 OSS（同步 upload_file 放线程池）
        file_name = f"{uuid.uuid4()}.wav"
        from io import BytesIO

        audio_stream = BytesIO(final_audio)
        loop = asyncio.get_event_loop()
        upload_result = await loop.run_in_executor(
            None,
            lambda: self.oss_service.upload_file(
                file_data=audio_stream,
                filename=file_name,
                category="tts",
                content_type="audio/wav",
            ),
        )
        audio_url = (
            upload_result.get("url", "")
            if isinstance(upload_result, dict)
            else str(upload_result)
        )

        logger.info(
            "CosyVoice TTS generated",
            model=self.cosyvoice_model,
            voice=final_voice,
            target_duration_sec=target_sec,
            duration_sec=duration_sec,
            audio_size=len(final_audio),
        )

        return {
            "url": audio_url,
            "duration_sec": float(duration_sec),
            "model": self.cosyvoice_model,
            "voice": final_voice,
            "sample_rate": int(sample_rate),
        }

    def _estimate_duration(self, text: str, speech_rate: int = 0) -> int:
        """
        估算音频时长（毫秒）
        
        Args:
            text: 文本内容
            speech_rate: 语速调整（-500 到 500）
            
        Returns:
            估算的时长（毫秒）
        """
        # 中文约每秒 4-5 个字，英文约每秒 2-3 个词
        # speech_rate 影响语速，-500 最慢，500 最快
        base_chars_per_second = 4.0
        # 调整语速因子
        rate_factor = 1.0 + (speech_rate / 1000.0)  # -500->0.5, 0->1.0, 500->1.5
        rate_factor = max(0.5, min(1.5, rate_factor))
        
        chars_per_second = base_chars_per_second * rate_factor
        duration_seconds = len(text) / chars_per_second
        return int(duration_seconds * 1000)

    async def synthesize_batch(
        self,
        items: List[Dict[str, Any]],
        voice: str = "sambert-zhichu-v1",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        批量文本转语音
        
        Args:
            items: 文本列表，每项包含 {"text": "...", "id": "..."}
            voice: 音色 ID
            **kwargs: 其他合成参数
            
        Returns:
            结果列表
        """
        results = []
        
        for item in items:
            try:
                text = item.get("text", "")
                item_id = item.get("id", str(uuid.uuid4()))
                
                if not text:
                    results.append({
                        "id": item_id,
                        "success": False,
                        "error": "文本为空"
                    })
                    continue
                
                result = await self.synthesize(text=text, voice=voice, **kwargs)
                results.append({
                    "id": item_id,
                    "success": True,
                    **result
                })
                
            except Exception as e:
                results.append({
                    "id": item.get("id", "unknown"),
                    "success": False,
                    "error": str(e)
                })
        
        return results


# 单例实例
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """获取 TTS 服务单例"""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
