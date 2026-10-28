// apiClient.js - Cliente HTTP com refresh automático de token

const API_URL = 'http://localhost:8000';
let isRefreshing = false;
let refreshPromise = null;
let failedQueue = [];

// Guarda a referência original do fetch para evitar loop infinito
const originalFetch = window.fetch;

/**
 * Função para renovar o token usando o refresh token
 */
async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('refresh_token');
  
  if (!refreshToken) {
    // Limpa tokens e redireciona
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new Error('Refresh token não encontrado');
  }

  try {
    const response = await originalFetch(`${API_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${refreshToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Falha ao renovar token');
    }

    const data = await response.json();
    
    if (data.access_token && data.refresh_token) {
      localStorage.setItem('access_token', data.access_token);
      // O backend rotaciona o refresh token: o anterior deixa de valer após esta renovação.
      localStorage.setItem('refresh_token', data.refresh_token);
      return data.access_token;
    }
    
    throw new Error('Tokens não retornados');
  } catch (error) {
    // Se falhar, limpa os tokens e redireciona para login
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw error;
  }
}

/**
 * Processa a fila de requisições que falharam
 */
function processQueue(error = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve();
    }
  });
  failedQueue = [];
}

/**
 * Função para fazer requisições HTTP com refresh automático
 */
export async function apiRequest(url, options = {}) {
  const token = localStorage.getItem('access_token');
  
  // Adiciona o token de autorização se existir
  const headers = {
    ...options.headers,
  };
  
  if (token && !options.skipAuth) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Faz a requisição inicial usando originalFetch para evitar loop
  let response = await originalFetch(url, {
    ...options,
    headers,
  });

  // Se receber 401, tenta renovar o token
  if (response.status === 401 && !options.skipAuth) {
    // Se já está renovando, adiciona à fila
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then(() => {
        // Repete a requisição com o novo token
        const newToken = localStorage.getItem('access_token');
        if (newToken) {
          headers['Authorization'] = `Bearer ${newToken}`;
          return originalFetch(url, {
            ...options,
            headers,
          });
        }
        throw new Error('Token não renovado');
      });
    } else {
      // Inicia o processo de renovação
      isRefreshing = true;
      refreshPromise = refreshAccessToken();
      
      try {
        await refreshPromise;
        processQueue(null);
        
        // Repete a requisição com o novo token
        const newToken = localStorage.getItem('access_token');
        if (newToken) {
          headers['Authorization'] = `Bearer ${newToken}`;
          response = await originalFetch(url, {
            ...options,
            headers,
          });
        }
      } catch (error) {
        processQueue(error);
        throw error;
      } finally {
        isRefreshing = false;
        refreshPromise = null;
      }
    }
  }

  return response;
}

