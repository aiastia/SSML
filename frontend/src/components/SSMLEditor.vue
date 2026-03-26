<template>
  <div class="ssml-editor">
    <div class="editor-header">
      <h3>SSML 编辑器</h3>
      <div class="template-selector">
        <select v-model="selectedTemplate" @change="loadTemplate">
          <option value="">选择模板...</option>
          <option v-for="template in templates" :key="template.name" :value="template.name">
            {{ template.label }}
          </option>
        </select>
      </div>
    </div>
    
    <div class="editor-toolbar">
      <button class="btn btn-secondary btn-sm" @click="insertTag('speak')" title="插入 speak 标签">
        {{ tagLabels.speak }}
      </button>
      <button class="btn btn-secondary btn-sm" @click="insertTag('voice')" title="插入 voice 标签">
        {{ tagLabels.voice }}
      </button>
      <button class="btn btn-secondary btn-sm" @click="insertTag('prosody')" title="插入 prosody 标签">
        {{ tagLabels.prosody }}
      </button>
      <button class="btn btn-secondary btn-sm" @click="insertTag('break')" title="插入 break 标签">
        {{ tagLabels.break }}
      </button>
      <button class="btn btn-secondary btn-sm" @click="insertTag('emphasis')" title="插入 emphasis 标签">
        {{ tagLabels.emphasis }}
      </button>
      <button class="btn btn-secondary btn-sm" @click="formatXML" title="格式化 XML">
        格式化
      </button>
    </div>
    
    <div class="editor-container">
      <textarea
        ref="editor"
        v-model="content"
        class="ssml-textarea"
        spellcheck="false"
        @input="handleInput"
        @keydown.tab.prevent="handleTab"
      ></textarea>
    </div>
    
    <div class="editor-footer">
      <div v-if="validationResult" class="validation-result">
        <div v-if="!validationResult.valid" class="error">
          ❌ {{ validationResult.errors?.[0]?.message || 'SSML 语法错误' }}
        </div>
        <div v-else class="success">✅ SSML 语法正确</div>
        
        <div v-if="validationResult.warnings?.length" class="warnings">
          <div v-for="(warning, index) in validationResult.warnings" :key="index" class="warning">
            ⚠️ {{ warning }}
          </div>
        </div>
      </div>
      <div class="char-count">{{ content.length }} 字符</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  autoValidate: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'validate'])

const content = ref(props.modelValue)
const editor = ref(null)
const selectedTemplate = ref('')
const validationResult = ref(null)
const isLoadingTemplate = ref(false)

// 标签显示文本（使用转义的 HTML 实体）
const tagLabels = {
  speak: '<speak>',
  voice: '<voice>',
  prosody: '<prosody>',
  break: '<break>',
  emphasis: '<emphasis>'
}

// SSML 模板
const templates = [
  {
    name: 'basic',
    label: '基础模板',
    ssml: `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        你好，欢迎使用 SSML 语音合成平台。
    </voice>
</speak>`
  },
  {
    name: 'emotional',
    label: '情感语音',
    ssml: `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        <mstts:express-as style="cheerful" styledegree="2">
            今天天气真好！
        </mstts:express-as>
    </voice>
</speak>`
  },
  {
    name: 'prosody',
    label: '语调控制',
    ssml: `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        <prosody rate="slow" pitch="-10%">
            这句话语速较慢，音调较低。
        </prosody>
        <prosody rate="fast" pitch="+20%">
            这句话语速较快，音调较高。
        </prosody>
    </voice>
</speak>`
  },
  {
    name: 'emphasis',
    label: '强调效果',
    ssml: `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        <emphasis level="strong">这句话会被强调朗读！</emphasis>
    </voice>
</speak>`
  },
  {
    name: 'break',
    label: '停顿控制',
    ssml: `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        这是一句话。<break time="1s" />
        这里有停顿。<break strength="medium" />
        继续朗读。
    </voice>
</speak>`
  },
  {
    name: 'multivoice',
    label: '多角色对话',
    ssml: `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        你好，我是小晓。
    </voice>
    <voice name="zh-CN-YunxiNeural">
        你好，我是云希。
    </voice>
    <voice name="zh-CN-XiaoxiaoNeural">
        很高兴认识你！
    </voice>
</speak>`
  }
]

// 加载模板
const loadTemplate = () => {
  const template = templates.find(t => t.name === selectedTemplate.value)
  if (template) {
    isLoadingTemplate.value = true
    content.value = template.ssml
    selectedTemplate.value = '' // 重置选择器
    emit('update:modelValue', template.ssml)
    validateSSML()
    nextTick(() => {
      isLoadingTemplate.value = false
    })
  }
}

// 插入标签
const insertTag = (tagName) => {
  const textarea = editor.value
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const text = content.value
  const selectedText = text.substring(start, end)
  
  let tagPair = ''
  switch (tagName) {
    case 'speak':
      tagPair = `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">\n    ${selectedText}\n</speak>`
      break
    case 'voice':
      tagPair = `<voice name="zh-CN-XiaoxiaoNeural">${selectedText}</voice>`
      break
    case 'prosody':
      tagPair = `<prosody rate="medium" pitch="0%">${selectedText}</prosody>`
      break
    case 'break':
      tagPair = selectedText ? `<break time="${selectedText}" />` : `<break time="1s" />`
      break
    case 'emphasis':
      tagPair = `<emphasis level="strong">${selectedText}</emphasis>`
      break
  }
  
  content.value = text.substring(0, start) + tagPair + text.substring(end)
  
  // 重新聚焦并设置光标位置
  setTimeout(() => {
    textarea.focus()
  }, 0)
}

// 格式化 XML
const formatXML = () => {
  try {
    const parser = new DOMParser()
    const xmlDoc = parser.parseFromString(content.value, 'text/xml')
    const serializer = new XMLSerializer()
    let formatted = serializer.serializeToString(xmlDoc)
    
    // 添加缩进
    formatted = formatted.replace(/>\s*</g, '>\n<')
    const lines = formatted.split('\n')
    let indent = 0
    const formattedLines = lines.map(line => {
      if (line.match(/^<\//)) {
        indent = Math.max(0, indent - 1)
      }
      const indentedLine = '    '.repeat(indent) + line
      if (line.match(/^<[^/][^>]*>[^<]*$/)) {
        // 自闭合标签或内容行
      } else if (line.match(/^<[^/][^>]*>$/) && !line.match(/\/>$/)) {
        indent++
      }
      return indentedLine
    })
    
    content.value = formattedLines.join('\n')
  } catch (e) {
    alert('格式化失败，请检查 SSML 语法')
  }
}

// 处理输入
const handleInput = () => {
  if (!isLoadingTemplate.value) {
    emit('update:modelValue', content.value)
    if (props.autoValidate) {
      validateSSML()
    }
  }
}

// 处理 Tab 键
const handleTab = () => {
  const textarea = editor.value
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  content.value = content.value.substring(0, start) + '    ' + content.value.substring(end)
  setTimeout(() => {
    textarea.selectionStart = textarea.selectionEnd = start + 4
  }, 0)
}

// 验证 SSML
const validateSSML = async () => {
  try {
    const response = await fetch('/api/validate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ ssml: content.value })
    })
    const result = await response.json()
    validationResult.value = result
    emit('validate', result)
  } catch (error) {
    console.error('验证失败:', error)
  }
}

// 监听 modelValue 变化
watch(() => props.modelValue, (newVal) => {
  if (newVal !== content.value && !isLoadingTemplate.value) {
    content.value = newVal
  }
})

onMounted(() => {
  if (props.autoValidate && content.value) {
    validateSSML()
  }
})
</script>

<style scoped>
.ssml-editor {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--bg-secondary);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.editor-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.template-selector select {
  padding: 6px 10px;
  font-size: 13px;
  min-width: 150px;
}

.editor-toolbar {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}

.editor-container {
  position: relative;
}

.ssml-textarea {
  width: 100%;
  height: 400px;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  border: none;
  resize: vertical;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  tab-size: 4;
}

.ssml-textarea:focus {
  outline: none;
}

.editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background-color: var(--bg-tertiary);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
}

.validation-result {
  flex: 1;
}

.error {
  color: var(--error-color);
  font-weight: 500;
}

.success {
  color: var(--success-color);
  font-weight: 500;
}

.warnings {
  margin-top: 4px;
}

.warning {
  color: var(--warning-color);
  font-size: 11px;
}

.char-count {
  color: var(--text-secondary);
  margin-left: 16px;
}

@media (max-width: 768px) {
  .editor-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .template-selector select {
    width: 100%;
  }
  
  .ssml-textarea {
    height: 300px;
    font-size: 12px;
  }
  
  .editor-footer {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
  
  .char-count {
    margin-left: 0;
  }
}
</style>