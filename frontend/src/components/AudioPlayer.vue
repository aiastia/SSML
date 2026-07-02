<template>
  <div class="audio-player">
    <div v-if="!audioUrl" class="no-audio">
      <p>暂无音频，请先合成语音</p>
    </div>
    
    <div v-else class="player-container">
      <audio
        ref="audioPlayer"
        :src="audioUrl"
        @timeupdate="handleTimeUpdate"
        @loadedmetadata="handleLoadedMetadata"
        @play="handlePlay"
        @pause="handlePause"
        @ended="handleEnded"
      ></audio>
      
      <div class="waveform" ref="waveformRef" @click="handleWaveformSeek" @mousedown="startDragSeek">
        <div class="waveform-bars">
          <div
            v-for="(bar, index) in waveformBars"
            :key="index"
            class="waveform-bar"
            :class="{ active: index < progressPercent * 100 }"
            :style="{ height: bar.height }"
          ></div>
        </div>
        <div class="waveform-progress" :style="{ width: progressPercent * 100 + '%' }"></div>
      </div>
      
      <div class="controls">
        <div class="control-row">
          <button class="btn btn-primary" @click="togglePlay" :disabled="loading">
            <span v-if="loading" class="loading"></span>
            <span v-else-if="isPlaying">⏸</span>
            <span v-else>▶</span>
          </button>
          
          <button class="btn btn-secondary" @click="stop" :disabled="loading">
            ⏹
          </button>
          
          <div class="time-display">
            <span>{{ formatTime(currentTime) }}</span>
            <span>/</span>
            <span>{{ formatTime(duration) }}</span>
          </div>
        </div>
        
        <div class="control-row">
          <div class="progress-container">
            <input
              type="range"
              class="progress-bar"
              :value="currentTime"
              :max="duration"
              @input="handleSeek"
              :disabled="loading"
            />
          </div>
          
          <div class="volume-control">
            <span class="volume-icon">🔊</span>
            <input
              type="range"
              class="volume-slider"
              v-model="volume"
              min="0"
              max="1"
              step="0.1"
              @input="handleVolumeChange"
            />
          </div>
          
          <div class="speed-control">
            <select v-model="playbackRate" @change="handleSpeedChange">
              <option value="0.5">0.5x</option>
              <option value="0.75">0.75x</option>
              <option value="1">1x</option>
              <option value="1.25">1.25x</option>
              <option value="1.5">1.5x</option>
              <option value="2">2x</option>
            </select>
          </div>
        </div>
      </div>
      
      <div class="download-section">
        <a :href="audioUrl" download="speech.mp3" class="btn btn-secondary">
          ⬇ 下载音频
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  audioUrl: {
    type: String,
    default: ''
  }
})

const audioPlayer = ref(null)
const waveformRef = ref(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const playbackRate = ref(1)
const loading = ref(false)
const isDragging = ref(false)

// 生成波形数据
const waveformBars = ref([])
const generateWaveform = () => {
  const bars = []
  for (let i = 0; i < 100; i++) {
    bars.push({
      height: `${Math.random() * 80 + 20}%`
    })
  }
  waveformBars.value = bars
}

const progressPercent = computed(() => {
  if (duration.value === 0) return 0
  return currentTime.value / duration.value
})

const togglePlay = () => {
  if (!audioPlayer.value) return
  
  if (isPlaying.value) {
    audioPlayer.value.pause()
  } else {
    audioPlayer.value.play()
  }
}

const stop = () => {
  if (!audioPlayer.value) return
  audioPlayer.value.pause()
  audioPlayer.value.currentTime = 0
}

const handleSeek = (e) => {
  if (!audioPlayer.value) return
  const seekTime = parseFloat(e.target.value)
  audioPlayer.value.currentTime = seekTime
  currentTime.value = seekTime
}

// ── 波形图点击/拖拽跳转 ──
const seekToPosition = (clientX) => {
  if (!waveformRef.value || !audioPlayer.value || !duration.value) return
  const rect = waveformRef.value.getBoundingClientRect()
  const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
  const seekTime = percent * duration.value
  audioPlayer.value.currentTime = seekTime
  currentTime.value = seekTime
}

const handleWaveformSeek = (e) => {
  if (isDragging.value) return // 拖拽中不重复处理点击
  seekToPosition(e.clientX)
}

const startDragSeek = (e) => {
  isDragging.value = true
  seekToPosition(e.clientX)
  const onMove = (ev) => seekToPosition(ev.clientX)
  const onUp = () => {
    isDragging.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

const handleVolumeChange = () => {
  if (!audioPlayer.value) return
  audioPlayer.value.volume = volume.value
}

const handleSpeedChange = () => {
  if (!audioPlayer.value) return
  audioPlayer.value.playbackRate = parseFloat(playbackRate.value)
}

const handleTimeUpdate = () => {
  if (!audioPlayer.value) return
  currentTime.value = audioPlayer.value.currentTime
}

const handleLoadedMetadata = () => {
  if (!audioPlayer.value) return
  duration.value = audioPlayer.value.duration
  loading.value = false
}

const handlePlay = () => {
  isPlaying.value = true
}

const handlePause = () => {
  isPlaying.value = false
}

const handleEnded = () => {
  isPlaying.value = false
  currentTime.value = 0
}

const formatTime = (seconds) => {
  if (isNaN(seconds) || !isFinite(seconds)) return '0:00'
  
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// 监听 audioUrl 变化
watch(() => props.audioUrl, (newUrl) => {
  if (newUrl) {
    loading.value = true
    currentTime.value = 0
    duration.value = 0
    isPlaying.value = false
    generateWaveform()
  }
})

onMounted(() => {
  generateWaveform()
})

onUnmounted(() => {
  if (audioPlayer.value) {
    audioPlayer.value.pause()
  }
})
</script>

<style scoped>
.audio-player {
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
}

.no-audio {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 20px;
}

.player-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.waveform {
  height: 80px;
  background-color: var(--bg-secondary);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
  position: relative;
  user-select: none;
}

.waveform-bars {
  display: flex;
  align-items: center;
  gap: 2px;
  width: 100%;
  height: 60px;
  padding: 0 10px;
}

.waveform-bar {
  flex: 1;
  background-color: var(--border-color);
  border-radius: 2px;
  transition: background-color 0.2s;
}

.waveform-bar.active {
  background-color: var(--accent-color);
}

.waveform-progress {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background-color: var(--accent-color);
  opacity: 0.15;
  pointer-events: none;
  border-radius: 6px 0 0 6px;
}

.controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.time-display {
  display: flex;
  gap: 8px;
  font-size: 14px;
  font-family: monospace;
  color: var(--text-secondary);
  margin-left: auto;
}

.progress-container {
  flex: 1;
}

.progress-bar {
  width: 100%;
  cursor: pointer;
  accent-color: var(--accent-color);
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.volume-icon {
  font-size: 16px;
}

.volume-slider {
  width: 80px;
  cursor: pointer;
  accent-color: var(--accent-color);
}

.speed-control select {
  padding: 6px 10px;
  font-size: 13px;
  min-width: 70px;
  cursor: pointer;
}

.download-section {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

@media (max-width: 768px) {
  .audio-player {
    padding: 16px;
  }
  
  .control-row {
    flex-wrap: wrap;
  }
  
  .volume-control {
    width: 100%;
  }
  
  .volume-slider {
    flex: 1;
  }
  
  .speed-control select {
    width: 100%;
  }
}
</style>