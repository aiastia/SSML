import requests
import io
import re
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, List
from pydub import AudioSegment
from models import VoiceInfo


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
                # 尝试解析 Azure 返回的错误信息
                error_msg = self._parse_azure_error(response)
                return None, 0, f"API Error: {response.status_code} - {error_msg}"
        except requests.exceptions.Timeout:
            return None, 0, "Request timeout"
        except requests.exceptions.RequestException as e:
            return None, 0, f"Request failed: {str(e)}"

    def _synthesize_with_retry(self, ssml: str, output_format: str) -> Tuple[bytes, int, Optional[str]]:
        """发送请求，如果因 express-as style 不被支持而 400，去掉 style 后重试"""
        result = self._synthesize_single(ssml, output_format)
        # 失败且 SSML 包含 express-as → 尝试去掉 style 重试
        if result[2] and 'mstts:express-as' in ssml and '400' in result[2]:
            return self._retry_without_express_as_style(ssml, output_format, result[2])
        return result

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
            'rate': "rate 请用相对百分比(如 +10%/-4%/0%)或预设词(x-slow/slow/medium/fast/x-fast)",
            'pitch': "pitch 请用相对百分比(如 +10%/-6%/0%)或相对赫兹(如 +5Hz)或预设词(x-low/low/medium/high/x-high)",
        }

        def _is_valid(attr: str, value: str) -> bool:
            value = value.strip()
            if value in presets[attr]:
                return True
            if attr == 'volume' and re.fullmatch(r'\d{1,3}', value) and 0 <= int(value) <= 100:
                return True
            # volume / rate 支持 ±N% 相对百分比
            if attr in ('volume', 'rate') and re.fullmatch(r'[+-]?\d+%$', value):
                return True
            # pitch 支持 ±N% 相对百分比 和 ±NHz 相对赫兹
            if attr == 'pitch' and (re.fullmatch(r'[+-]?\d+%$', value) or re.fullmatch(r'[+-]?\d+Hz$', value)):
                return True
            return False

        for match in re.finditer(r'<prosody\b[^>]*>', ssml, re.IGNORECASE):
            tag = match.group(0)
            for attr in ('volume', 'rate', 'pitch'):
                am = re.search(rf'{attr}\s*=\s*"([^"]*)"', tag, re.IGNORECASE)
                if am and not _is_valid(attr, am.group(1)):
                    return f"prosody {attr} 属性值非法: '{am.group(1)}'。{hints[attr]}"
        return None

    # Azure 已知的 express-as style 值（仅供参考，不阻塞请求）
    KNOWN_EXPRESS_AS_STYLES = {
        'general', 'narration', 'narration-relaxed', 'cheerful', 'sad', 'angry',
        'calm', 'fearful', 'serious', 'excited', 'customerservice', 'chat',
        'assistant', 'newscast', 'empathetic', 'depressed', 'disgruntled',
        'embarrassed', 'envious', 'grumbling', 'hopeful', 'lyrical', 'poetry',
        'sports_commentary', 'sports_commentary_excited', 'gentle', 'terrified',
        'unfriendly', 'shouting', 'frustrated', 'conversational', 'poetry-reading',
    }

    def _validate_express_as_styles(self, ssml: str) -> Optional[str]:
        """校验 <mstts:express-as> 的 style 属性，返回警告信息（不阻塞）"""
        warnings = []
        for match in re.finditer(r'<mstts:express-as\b[^>]*>', ssml, re.IGNORECASE):
            tag = match.group(0)
            am = re.search(r'style\s*=\s*"([^"]*)"', tag, re.IGNORECASE)
            if am:
                style = am.group(1).strip().lower()
                if style not in self.KNOWN_EXPRESS_AS_STYLES:
                    warnings.append(
                        f"express-as style '{am.group(1)}' 可能不被当前 voice 支持"
                        f"（已知合法值：{', '.join(sorted(self.KNOWN_EXPRESS_AS_STYLES))}）"
                    )
        return '; '.join(warnings) if warnings else None

    def _retry_without_express_as_style(self, ssml: str, output_format: str, original_error: str) -> Tuple[bytes, int, Optional[str]]:
        """
        去掉 <mstts:express-as> 的 style 属性后重试。
        Azure 可能因为 voice 不支持该 style 而返回 400。
        """
        # 去掉 express-as 的 style="xxx" 属性
        retry_ssml = re.sub(r'style\s*=\s*"[^"]*"', '', ssml)
        # 清理多余空格
        retry_ssml = re.sub(r'<mstts:express-as(\s+)>', r'<mstts:express-as>', retry_ssml)
        retry_ssml = re.sub(r'<mstts:express-as(\s+)(/?>)', r'<mstts:express-as\2', retry_ssml)

        return self._synthesize_single(retry_ssml, output_format)

    def _normalize_namespaces(self, ssml: str) -> str:
        """
        规范化 SSML 命名空间声明：
        - 移除子元素上冗余的 xmlns:mstts（如 <mstts:express-as xmlns:mstts="...">）
        - 确保 xmlns:mstts 只出现在 <speak> 根元素上
        Azure 要求 mstts 命名空间在根元素声明，否则可能返回空 body 的 400。
        """
        if 'mstts:' not in ssml:
            return ssml
        # 移除所有 xmlns:mstts 声明（不管它在哪个元素上）
        ssml = re.sub(r'\s+xmlns:mstts\s*=\s*"https://www\.w3\.org/2001/mstts"', '', ssml)
        # 在 <speak> 根元素的 > 之前补回 xmlns:mstts
        speak_end = ssml.find('>')
        if speak_end == -1:
            return ssml
        return ssml[:speak_end] + ' xmlns:mstts="https://www.w3.org/2001/mstts"' + ssml[speak_end:]

    def synthesize(self, ssml: str, output_format: str = "audio-16khz-32kbitrate-mono-mp3") -> Tuple[bytes, int, Optional[str]]:
        """
        Synthesize speech from SSML.
        若 SSML 文本内容过长，自动拆分为多个请求分段合成，再拼接音频。
        若 express-as style 不被 voice 支持，自动去掉 style 后重试。

        Returns:
            Tuple of (audio_data, file_size, error_message)
        """
        # 发送前预校验 prosody 属性值，提前拦截非法值，
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
            return self._synthesize_with_retry(ssml, output_format)

        # 拆分 SSML 为多个 chunk
        chunks = self._split_ssml(ssml)
        if not chunks:
            chunks = [ssml]

        if len(chunks) == 1:
            return self._synthesize_single(chunks[0], output_format)

        # 分段合成
        audio_segments = []
        for i, chunk_ssml in enumerate(chunks):
            audio_data, file_size, error = self._synthesize_with_retry(chunk_ssml, output_format)
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
        使用正则提取，保留原始 XML 格式（避免 ET.tostring 改写命名空间/属性）。
        """
        # 提取 <speak> 开头标签（含属性）
        speak_open_match = re.match(r'(<speak\b[^>]*>)', ssml, re.DOTALL)
        if not speak_open_match:
            return [ssml]
        speak_open = speak_open_match.group(1)

        # 提取 </speak> 结尾标签
        speak_close_match = re.search(r'(</speak>\s*)$', ssml, re.DOTALL)
        speak_close = speak_close_match.group(1) if speak_close_match else '</speak>'

        # 提取中间内容
        inner = ssml[len(speak_open):ssml.rfind('</speak>')]

        # 找到 <voice> 标签
        voice_match = re.search(r'(<voice\b[^>]*>)(.*?)(</voice>)', inner, re.DOTALL)
        if not voice_match:
            return [ssml]

        voice_open = voice_match.group(1)
        voice_content = voice_match.group(2)
        voice_close = voice_match.group(3)

        # 检查是否有 <mstts:express-as>
        express_match = re.search(r'(<mstts:express-as\b[^>]*>)(.*?)(</mstts:express-as>)', voice_content, re.DOTALL)
        if express_match:
            express_open = express_match.group(1)
            express_content = express_match.group(2)
            express_close = express_match.group(3)
        else:
            express_open = ''
            express_content = voice_content
            express_close = ''

        # 提取 content_parent 内的子元素（保留原始 XML 格式）
        # 用栈匹配方式逐个提取顶层子元素，正确处理嵌套标签
        content_items = self._extract_top_level_elements(express_content)

        if not content_items:
            return [ssml]

        # 将内容项分组
        chunks_xml = self._group_items(content_items)

        # 为每个 chunk 重建完整 SSML
        result = []
        for chunk_xml in chunks_xml:
            parts = [speak_open]
            parts.append(voice_open)
            if express_open:
                parts.append(express_open)
            parts.append(chunk_xml)
            if express_close:
                parts.append(express_close)
            parts.append(voice_close)
            parts.append(speak_close)
            result.append(''.join(parts))

        return result if result else [ssml]

    def _extract_top_level_elements(self, content: str) -> List[str]:
        """
        从 XML 内容中提取顶层子元素（保留原始格式）。
        用栈匹配方式处理嵌套标签，正确提取每个完整的顶层元素及其前后文本。
        <break/> 等自闭合标签会合并到前一个元素。
        """
        items: List[str] = []
        pos = 0
        n = len(content)

        while pos < n:
            # 找到下一个标签开始
            lt = content.find('<', pos)
            if lt == -1:
                # 剩余都是纯文本
                tail = content[pos:]
                if tail.strip() and items:
                    items[-1] = items[-1].rstrip() + tail.rstrip()
                break

            # 标签前的文本
            text_before = content[pos:lt]
            if text_before.strip() and items:
                items[-1] = items[-1].rstrip() + text_before
            elif text_before.strip():
                items.append(text_before)

            # 解析标签名
            gt = content.find('>', lt)
            if gt == -1:
                break
            tag_text = content[lt:gt + 1]

            # 判断是否是自闭合标签 <xxx .../>
            if tag_text.endswith('/>'):
                tag_name = re.match(r'<([a-zA-Z:][\w:.-]*)', tag_text)
                name = tag_name.group(1).lower() if tag_name else ''
                if name == 'break':
                    if items:
                        items[-1] = items[-1].rstrip() + '\n' + tag_text
                    else:
                        items.append(tag_text)
                else:
                    items.append(tag_text)
                pos = gt + 1
                continue

            # 普通开标签 <xxx ...>
            tag_name_m = re.match(r'<([a-zA-Z:][\w:.-]*)', tag_text)
            if not tag_name_m:
                pos = gt + 1
                continue
            tag_name = tag_name_m.group(1)
            close_tag = f'</{tag_name}>'

            # 用栈找到匹配的结束标签（处理同名嵌套）
            depth = 1
            search_pos = gt + 1
            element_start = lt
            while search_pos < n and depth > 0:
                next_open = content.find(f'<{tag_name}', search_pos)
                next_close = content.find(close_tag, search_pos)
                if next_close == -1:
                    # 没有结束标签，当作自闭合处理
                    break
                if next_open != -1 and next_open < next_close:
                    # 检查 next_open 是开标签还是自闭合
                    open_end = content.find('>', next_open)
                    if open_end != -1 and not content[next_open:open_end + 1].endswith('/>'):
                        depth += 1
                    search_pos = open_end + 1
                else:
                    depth -= 1
                    search_pos = next_close + len(close_tag)

            element_end = search_pos
            full_element = content[element_start:element_end]
            items.append(full_element)
            pos = element_end

        return items

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