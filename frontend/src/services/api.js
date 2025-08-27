import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// File management API functions
export const fileAPI = {
  // Upload a file
  uploadFile: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // List all files
  listFiles: async () => {
    const response = await api.get('/files/list');
    return response.data;
  },

  // Delete a file
  deleteFile: async (fileId) => {
    const response = await api.delete(`/files/delete/${fileId}`);
    return response.data;
  },

  // Get file info
  getFileInfo: async (fileId) => {
    const response = await api.get(`/files/${fileId}/info`);
    return response.data;
  },

  // Get file URL for viewing
  getFileUrl: (fileId) => {
    return `${API_BASE_URL}/files/${fileId}/download`;
  }
};

// Health check API
export const healthAPI = {
  checkHealth: async () => {
    const response = await api.get('/health/');
    return response.data;
  }
};

// Q&A API functions
export const qaAPI = {
  askQuestion: async (question, fileId = null) => {
    const response = await api.post('/qa/ask', {
      question,
      file_id: fileId
    });
    return response.data;
  }
};

export default api;
