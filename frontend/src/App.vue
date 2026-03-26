<template>
  <div id="app" :data-theme="theme">
    <div class="container">
      <header class="app-header">
        <h1>🎤 SSML 语音合成平台</h1>
        <button class="btn btn-secondary theme-toggle" @click="toggleTheme">
          {{ theme === 'light' ? '🌙' : '☀️' }}
        </button>
      </header>

      <div class="main-content">
        <div class="config-section">
          <div class="card">
            <div class="card-header">
              <h2 class="card-title">API 配置</h2>
            </div>
            <div class="config-form">
              <div class="form-group">
                <label for="apiKey">Azure API 密钥</label>
                <input
                  id="apiKey"
                  v-model="config.apiKey"
                  type="password"
                  placeholder="输入您的 Azure API 密钥"
                />
              </div>
              <div class="form-group">
                <label for="region">区域</label>
                <select id="region" v-model="config.region">
                  <option value="eastus">East US (美国东部)</option>
                  <option value="eastasia">East Asia (东亚)</option>
                  <option value="westus">West US (美国西部)</option>
                  <option value="westeurope">West Europe (西欧)</option>
                  <option value="southeastasia">Southeast Asia (东南亚)</option>
                  <option value="japaneast">Japan East (日本东部)</option>
                  <option value="japanwest">Japan West (日本西部)</option>
                  <option value="eastus2">East US 2 (美国东部 2)</option>
                  <option value="westus2">West US 2 (美国西部 2)</option>
                  <option value="northcentralus">North Central US (美国中北部)</option>
                  <option value="southcentralus">South Central US (美国中南部)</option>
                  <option value="australiaeast">Australia East (澳大利亚东部)</option>
                  <option value="canadacentral">Canada Central (加拿大中部)</option>
                  <option value="centralindia">Central India (印度中部)</option>
                  <option value="francecentral">France Central (法国中部)</option>
                  <option value="germanywestcentral">Germany West Central (德国中西部)</option>
                  <option value="northeurope">North Europe (北欧)</option>
                  <option value="southafricanorth">South Africa North (南非北部)</option>
                  <option value="uksouth">UK South (英国南部)</option>
                  <option value="uaenorth">UAE North (阿联酋北部)</option>
                </select>
              </div>
              <div class="form-group">
                <label for="voice">默认语音</label>
                <select id="voice" v-model="config.voice">
                  <option value="zh-CN-XiaoxiaoNeural">中文 - 晓晓</option>
                  <option value="zh-CN-YunxiNeural">中文 - 云希</option>
                  <option value="zh-CN-YunyangNeural">中文 - 云扬</option>
                  <option value="en-US-JennyNeural">English - Jenny</option>
                  <option value="en-US-GuyNeural">English - Guy</option>
                  <option value="ja-JP-NanamiNeural">日本語 - 七海</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div class="editor-section">
          <div class="card">
            <div class="card-header">
              <h2 class="card-title">SSML 编辑</h2>
            </div>
            <SSMLEditor
              v-model="ssmlContent"
              @validate="handleValidation"
            />
          </div>
        </div>

        <div class="control-section">
          <div class="card">
            <div class="card-header">
              <h2 class="card-title">控制面板</h2>
            </div>
            <div class="control-buttons">
              <button
                class="btn btn-primary btn-lg"
                @click="synthesize"
                :disabled="synthesizing || !isConfigValid"
              >
                <span v-if="synthesizing" class="loading"></span>
                <span v-else>🎵 合成语音</span>
              </button>
            </div>
            
            <div v-if="errorMessage" class="error-message">
              ❌ {{ errorMessage }}
            </div>
            
            <div v-if="successMessage" class="success-message">
              ✅ {{ successMessage }}
            </div>
          </div>

          <div class="card">
            <div class="card-header">
              <h2 class="card-title">音频播放</h2>
            </div>
            <AudioPlayer :audioUrl="audioUrl" />
          </div>
        </div>
      </div>

      <footer class="app-footer">
        <p>SSML 语音合成平台 | 使用 Azure TTS 服务</p>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import SSMLEditor from './components/SSMLEditor.vue'
import AudioPlayer from './components/AudioPlayer.vue'
import { ttsAPI } from './api.js'

// 主题
const theme = ref('light')

// 配置
const config = ref({
  apiKey: '',
  region: 'eastus',
  voice: 'zh-CN-XiaoxiaoNeural'
})

// SSML 内容
const ssmlContent = ref(`<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        你好，欢迎使用 SSML 语音合成平台。
    </voice>
</speak>`)

// 状态
const synthesizing = ref(false)
const audioUrl = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const validationResult = ref(null)

// 计算属性
const isConfigValid = computed(() => {
  return config.value.apiKey.trim() !== '' && ssmlContent.value.trim() !== ''
})

// 方法
const toggleTheme = () => {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  localStorage.setItem('theme', theme.value)
}

const handleValidation = (result) => {
  validationResult.value = result
}

const synthesize = async () => {
  if (!isConfigValid.value) {
    errorMessage.value = '请填写完整的 API 配置和 SSML 内容'
    return
  }

  errorMessage.value = ''
  successMessage.value = ''
  synthesizing.value = true

  try {
    const response = await ttsAPI.synthesize({
      ssml: ssmlContent.value,
      api_key: config.value.apiKey,
      region: config.value.region,
      voice: config.value.voice,
      output_format: 'audio-16khz-32kbitrate-mono-mp3'
    })

    if (response.success) {
      audioUrl.value = response.audio_url
      successMessage.value = `合成成功！文件大小: ${(response.file_size / 1024).toFixed(2)} KB`
    } else {
      errorMessage.value = response.error || '合成失败'
    }
  } catch (error) {
    console.error('合成错误:', error)
    errorMessage.value = '网络错误，请检查后端服务是否正常运行'
  } finally {
    synthesizing.value = false
  }
}

// 生命周期
onMounted(() => {
  // 从 localStorage 加载主题
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme) {
    theme.value = savedTheme
  }
  
  // 从 localStorage 加载配置
  const savedConfig = localStorage.getItem('config')
  if (savedConfig) {
    try {
      const parsed = JSON.parse(savedConfig)
      config.value = { ...config.value, ...parsed }
    } catch (e) {
      console.error('加载配置失败:', e)
    }
  }
})

// 监听配置变化并保存
import { watch } from 'vue'
watch(config, (newConfig) => {
  localStorage.setItem('config', JSON.stringify(newConfig))
}, { deep: true })
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.app-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.theme-toggle {
  padding: 8px 16px;
  font-size: 20px;
}

.main-content {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.config-section {
  grid-column: 1;
}

.editor-section {
  grid-column: 2;
}

.control-section {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-group input,
.form-group select {
  width: 100%;
}

.control-buttons {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.btn-lg {
  padding: 14px 28px;
  font-size: 16px;
  font-weight: 600;
}

.error-message {
  padding: 12px 16px;
  background-color: #fee2e2;
  color: #dc2626;
  border-radius: 6px;
  margin-top: 12px;
  font-size: 14px;
}

.success-message {
  padding: 12px 16px;
  background-color: #dcfce7;
  color: #16a34a;
  border-radius: 6px;
  margin-top: 12px;
  font-size: 14px;
}

.app-footer {
  text-align: center;
  padding: 20px 0;
  border-top: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 14px;
}

/* 暗色模式下的消息样式 */
[data-theme="dark"] .error-message {
  background-color: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

[data-theme="dark"] .success-message {
  background-color: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

/* 响应式 */
@media (max-width: 1024px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  
  .config-section {
    grid-column: 1;
  }
  
  .editor-section {
    grid-column: 1;
  }
  
  .control-section {
    grid-column: 1;
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .app-header {
    flex-direction: column;
    gap: 12px;
    text-align: center;
  }
  
  .app-header h1 {
    font-size: 24px;
  }
  
  .control-section {
    grid-template-columns: 1fr;
  }
  
  .btn-lg {
    width: 100%;
    padding: 12px 24px;
  }
}
</style>