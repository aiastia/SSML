import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

export const ttsAPI = {
  // 语音合成
  async synthesize(data) {
    const response = await api.post('/synthesize', data)
    return response.data
  },

  // 获取语音列表
  async getVoices(params = {}) {
    const response = await api.get('/voices', { params })
    return response.data
  },

  // 验证SSML
  async validate(ssml) {
    const response = await api.post('/validate', { ssml })
    return response.data
  }
}

export default api