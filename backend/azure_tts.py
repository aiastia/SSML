import requests
import io
import re
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, List
from pydub import AudioSegment
from models import VoiceInfo


# 注册 SSML 命名空间，防止 ElementTree 在序列化时把 mstts: 改成 ns0: 等自动前缀。
# Azure 只认 mstts: 前缀和默认命名空间，注册一次全局生效。
ET.register_namespace('mstts', 'https://www.w3.org/2001/mstts')
ET.register_namespace('', 'http://www.w3.org/2001/10/synthesis')

# Azure TTS 单次请求建议的文本字符数上限（保守值，避免 400 错误）
MAX_TEXT_CHARS_PER_REQUEST = 3000


class AzureTTSClient:
    def __init__(self, api_key: str, region: str):
        self.api_key = api_key
        self.region = region
        self.base_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    
    def _synthesize_single(self, ssml: str, output_format: str) -> Tuple[bytes, int, Optional[str]]:
        """发送单次 SSML 合成请求"""
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": output_format
        }
        # 打印即将发送的 SSML（repr 形式，便于发现隐藏字符/多余空格）
        print("=" * 100)
        print(f"[Azure TTS] 请求 URL: {self.base_url}")
        print(f"[Azure TTS] OutputFormat: {output_format}")
        print("[Azure TTS] 即将发送的 SSML (repr):")
        print(repr(ssml))
        print("=" * 100)

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                data=ssml.encode('utf-8'),
                timeout=30
            )
            if response.status_code == 200:
                audio_data = response.content
                return audio_data, len(audio_data), None
            else:
                # 打印 Azure 的原始返回，便于定位 InvalidSsml 等具体原因
                print("=" * 100)
                print(f"[Azure TTS] HTTP {response.status_code} {response.reason}")
                print("[Azure TTS] Azure 原始返回 (response.text):")
                print(response.text)
                print("=" * 100)
                # 尝试解析 Azure 返回的错误信息
                error_msg = self._parse_azure_error(response)
                return None, 0, f"API Error: {response.status_code} - {error_msg}"
        except requests.exceptions.Timeout:
            return None, 0, "Request timeout"
        except requests.exceptions.RequestException as e:
            return None, 0, f"Request failed: {str(e)}"

    def _parse_azure_error(self, response) -> str:
        """解析 Azure 返回的错误 XML，提取可读信息"""
        try:
            text = response.text.strip()
            if not text:
                # Azure 对部分非法 SSML（如非法属性值）只返回空 body 的 400，不给任何错误码。
                # 这里补一条提示，避免前端只能看到笼统的 "Bad Request"。
                hint = "Azure 未返回详细错误。常见原因：prosody 属性值非法(如 dB 后缀)、voice 不支持该 style、或 SSML 结构不被接受。"
                return f"{response.reason or 'Unknown error'} ({hint})"
            # Azure 通常返回 XML 格式错误，如 <Error><Code>...</Code><Message>...</Message></Error>
            root = ET.fromstring(text)
            code = root.findtext('.//Code', default='')
            message = root.findtext('.//Message', default='')
            if message:
                return f"{code}: {message}" if code else message
            return text[:500]
        except Exception:
            return response.text[:500] or response.reason or "Unknown error"

    def _validate_prosody_attributes(self, ssml: str) -> Optional[str]:
        """
        预校验 <prosody> 的 volume / rate / pitch 属性值。
        Azure 对非法属性值会返回空 body 的 400（没有任何 InvalidSsml 提示），
        这里提前拦截并返回中文友好提示。

        合法值规则（Azure）：
        - volume: 0-100 纯数字 | 相对百分比如 +30%/-20% | 预设词 silent/x-soft/soft/medium/loud/x-loud/default
        - rate:   相对百分比如 +10%/-5% | 预设词 x-slow/slow/medium/fast/x-fast/default
        - pitch:  相对赫兹如 +5Hz/-10Hz | 预设词 x-low/low/medium/high/x-high/default

        Returns:
            错误提示字符串；None 表示全部合法。
        """
        presets = {
            'volume': {'silent', 'x-soft', 'soft', 'medium', 'loud', 'x-loud', 'default'},
            'rate': {'x-slow', 'slow', 'medium', 'fast', 'x-fast', 'default'},
            'pitch': {'x-low', 'low', 'medium', 'high', 'x-high', 'default'},
        }
        hints = {
            'volume': "volume 不支持 dB 后缀，请用 0-100 / 相对百分比(如 +30%) / 预设词",
            'rate': "rate 请用相对百分比(如 +10%)或预设词(x-slow/slow/medium/fast/x-fast)",
            'pitch': "pitch 请用相对赫兹(如 +5Hz)或预设词(x-low/low/medium/high/x-high)",
        }

        def _is_valid(attr: str, value: str) -> bool:
            value = value.strip()
            if value in presets[attr]:
                return True
            if attr == 'volume' and re.fullmatch(r'\d{1,3}', value) and 0 <= int(value) <= 100:
                return True
            if attr in ('volume', 'rate') and re.fullmatch(r'[+-]\d+%$', value):
                return True
            if attr == 'pitch' and re.fullmatch(r'[+-]\d+Hz$', value):
                return True
            return False

        for match in re.finditer(r'<prosody\b[^>]*>', ssml, re.IGNORECASE):
            tag = match.group(0)
            for attr in ('volume', 'rate', 'pitch'):
                am = re.search(rf'{attr}\s*=\s*"([^"]*)"', tag, re.IGNORECASE)
                if am and not _is_valid(attr, am.group(1)):
                    return f"prosody {attr} 属性值非法: '{am.group(1)}'。{hints[attr]}"
        return None

    def _normalize_namespaces(self, ssml: str) -> str:
        """
        仅在需要时补充 xmlns:mstts 声明：
        - 未使用 mstts: 前缀 → 不动
        - 已声明 xmlns:mstts（无论写在哪个元素上）→ 尊重用户写法，不动
        - 使用了 mstts: 但全文无 xmlns:mstts → 在 <speak> 上补一个
        """
        if 'mstts:' not in ssml:
            return ssml
        if 'xmlns:mstts' in ssml:
            return ssml
        speak_end = ssml.find('>')
        if speak_end == -1:
            return ssml
        return ssml[:speak_end] + ' xmlns:mstts="https://www.w3.org/2001/mstts"' + ssml[speak_end:]

    def synthesize(self, ssml: str, output_format: str = "audio-16khz-32kbitrate-mono-mp3") -> Tuple[bytes, int, Optional[str]]:
        """
        Synthesize speech from SSML.
        若 SSML 文本内容过长，自动拆分为多个请求分段合成，再拼接音频。

        Returns:
            Tuple of (audio_data, file_size, error_message)
        """
        # 发送前预校验 prosody 属性值，提前拦截 dB 等非法后缀，
        # 避免被 Azure 以空 body 的 400 拒绝（那种错误没有任何提示，极难定位）
        validate_error = self._validate_prosody_attributes(ssml)
        if validate_error:
            return None, 0, validate_error

        # 规范化命名空间声明，确保 xmlns:mstts 在 <speak> 根元素上
        ssml = self._normalize_namespaces(ssml)

        # 提取纯文本长度
        try:
            text_length = self._get_text_length(ssml)
        except Exception:
            text_length = len(ssml)

        # 文本未超过阈值，直接单次请求
        if text_length <= MAX_TEXT_CHARS_PER_REQUEST:
            return self._synthesize_single(ssml, output_format)

        # 拆分 SSML 为多个 chunk
        chunks = self._split_ssml(ssml)
        if not chunks:
            chunks = [ssml]

        if len(chunks) == 1:
            return self._synthesize_single(chunks[0], output_format)

        # 分段合成
        audio_segments = []
        for i, chunk_ssml in enumerate(chunks):
            audio_data, file_size, error = self._synthesize_single(chunk_ssml, output_format)
            if error:
                return None, 0, f"分段合成失败 ({i+1}/{len(chunks)}): {error}"
            try:
                segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
                audio_segments.append(segment)
            except Exception as e:
                return None, 0, f"音频解码失败 ({i+1}/{len(chunks)}): {str(e)}"

        # 拼接音频
        try:
            combined = audio_segments[0]
            for seg in audio_segments[1:]:
                combined += seg
            output_buffer = io.BytesIO()
            combined.export(
                output_buffer,
                format="mp3",
                bitrate="32k",
                parameters=["-ar", "16000", "-ac", "1"]
            )
            combined_data = output_buffer.getvalue()
            return combined_data, len(combined_data), None
        except Exception as e:
            return None, 0, f"音频拼接失败: {str(e)}"

    def _get_text_length(self, ssml: str) -> int:
        """提取 SSML 中的纯文本长度"""
        try:
            root = ET.fromstring(ssml)
            return len(''.join(root.itertext()))
        except ET.ParseError:
            return len(re.sub(r'<[^>]+>', '', ssml))

    def _split_ssml(self, ssml: str) -> List[str]:
        """
        将过长的 SSML 拆分为多个 SSML 片段。
        优先在 <p> 或 <s> 标签边界拆分，保留 voice / express-as 等外层包装。
        """
        try:
            root = ET.fromstring(ssml)
        except ET.ParseError:
            return [ssml]

        # 提取 <speak> 属性
        speak_attrs = dict(root.attrib)
        speak_attrib_str = ' '.join(f'{k}="{v}"' for k, v in speak_attrs.items())

        # 找到 <voice> 元素
        voice_elem = None
        for child in root:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'voice':
                voice_elem = child
                break
        if voice_elem is None:
            return [ssml]

        voice_attrib_str = ' '.join(f'{k}="{v}"' for k, v in voice_elem.attrib.items())

        # 检查是否有 <mstts:express-as> 包装
        express_as_elem = None
        express_as_attrib_str = ''
        for child in voice_elem:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'express-as':
                express_as_elem = child
                express_as_attrib_str = ' '.join(f'{k}="{v}"' for k, v in child.attrib.items())
                break

        # 收集可拆分的内容元素（<p> / <s> / <prosody> 等）
        content_parent = express_as_elem or voice_elem
        content_items: List[str] = []
        for child in content_parent:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            # 跳过纯格式标签（如 <break>），它们会跟随前面的文本
            if tag == 'break':
                if content_items:
                    content_items[-1] += ET.tostring(child, encoding='unicode')
                continue
            content_items.append(ET.tostring(child, encoding='unicode'))

        if not content_items:
            return [ssml]

        # 将内容项分组为不超过 MAX_TEXT_CHARS_PER_REQUEST 的 chunk
        chunks_xml = self._group_items(content_items)

        # 为每个 chunk 重建完整 SSML
        result = []
        for chunk_xml in chunks_xml:
            parts = [f'<speak {speak_attrib_str}>']
            if not speak_attrs.get('xmlns:mstts'):
                parts[0] = f'<speak {speak_attrib_str} xmlns:mstts="https://www.w3.org/2001/mstts">'
            parts.append(f'<voice {voice_attrib_str}>')
            if express_as_elem is not None:
                parts.append(f'<mstts:express-as {express_as_attrib_str}>')
            parts.append(chunk_xml)
            if express_as_elem is not None:
                parts.append('</mstts:express-as>')
            parts.append('</voice>')
            parts.append('</speak>')
            result.append(''.join(parts))

        return result if result else [ssml]

    def _group_items(self, items: List[str]) -> List[str]:
        """将 XML 片段分组，使每组纯文本长度不超过上限"""
        chunks: List[str] = []
        current = ''
        current_len = 0

        for item in items:
            text_len = len(re.sub(r'<[^>]+>', '', item))
            # 单个 item 超过上限时，按句号拆分子项
            if text_len > MAX_TEXT_CHARS_PER_REQUEST:
                if current:
                    chunks.append(current)
                    current = ''
                    current_len = 0
                # 按句子拆分
                sentences = re.split(r'(?<=[。！？\n\.\!\?\;])', item)
                sub = ''
                for s in sentences:
                    s_len = len(re.sub(r'<[^>]+>', '', s))
                    if len(re.sub(r'<[^>]+>', '', sub)) + s_len > MAX_TEXT_CHARS_PER_REQUEST and sub.strip():
                        chunks.append(sub.rstrip())
                        sub = s
                    else:
                        sub += s
                if sub.strip():
                    chunks.append(sub.rstrip())
            elif current_len + text_len > MAX_TEXT_CHARS_PER_REQUEST and current:
                chunks.append(current)
                current = item
                current_len = text_len
            else:
                current += item
                current_len += text_len

        if current:
            chunks.append(current)

        return chunks if chunks else [items[0]]
    
    def get_voices(self) -> Tuple[list, Optional[str]]:
        """
        Get available voices from Azure TTS
        
        Returns:
            Tuple of (voices_list, error_message)
        """
        try:
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                voices_data = response.json()
                voices = []
                for voice in voices_data:
                    voice_info = VoiceInfo(
                        name=voice.get("Name", ""),
                        locale=voice.get("Locale", ""),
                        gender=voice.get("Gender", ""),
                        style_list=voice.get("StyleList", [])
                    )
                    voices.append(voice_info)
                return voices, None
            else:
                return [], f"API Error: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return [], f"Request failed: {str(e)}"


class SSMLValidator:
    """SSML syntax validator"""
    
    # Allowed SSML tags
    ALLOWED_TAGS = {
        'speak', 'voice', 'prosody', 'break', 'emphasis', 
        'say-as', 'lexicon', 'p', 's', 'phoneme', 'sub', 'mstts:express-as'
    }
    
    # Dangerous attributes to check
    DANGEROUS_PATTERNS = [
        r'<!ENTITY',
        r'<!DOCTYPE',
        r'<script',
        r'javascript:',
        r'on\w+\s*='
    ]
    
    @classmethod
    def validate(cls, ssml: str) -> tuple:
        """
        Validate SSML content
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check 1: Basic dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, ssml, re.IGNORECASE):
                errors.append({
                    "line": 1,
                    "column": 1,
                    "message": f"Potentially dangerous pattern detected: {pattern}"
                })
        
        # Check 2: XML syntax
        try:
            ET.fromstring(ssml)
        except ET.ParseError as e:
            errors.append({
                "line": e.position[0] if hasattr(e, 'position') else 1,
                "column": e.position[1] if hasattr(e, 'position') else 1,
                "message": f"XML syntax error: {str(e)}"
            })
        
        # Check 3: Check for speak root element
        if not ssml.strip().lower().startswith('<speak'):
            warnings.append("SSML should start with <speak> element")
        
        # Check 4: Check for language attribute
        if 'xml:lang' not in ssml and 'lang=' not in ssml:
            warnings.append("Consider adding language attribute for better pronunciation")
        
        # Check 5: Check for voice element
        if '<voice' not in ssml:
            warnings.append("Consider adding <voice> element to specify voice")
        
        return len(errors) == 0, errors, warnings