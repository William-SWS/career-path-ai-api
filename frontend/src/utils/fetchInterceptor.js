// fetchInterceptor.js - Intercepta requisições fetch para adicionar refresh automático

import { API_URL } from '../config';
import { apiRequest } from './apiClient';

// Guarda a referência original do fetch
const originalFetch = window.fetch;

// Substitui o fetch global
window.fetch = async function(url, options = {}) {
  const urlString = typeof url === 'string' ? url : url.toString();
  
  // Se a URL não é da nossa API, usa fetch normal
  const isApiRequest = urlString.startsWith(API_URL) || urlString.includes('/api/v1/');
  
  if (!isApiRequest) {
    return originalFetch(url, options);
  }
  
  // Verifica se é uma requisição que precisa de autenticação
  // Exclui rotas públicas (login, register, forgot-password, reset-password)
  const publicRoutes = [
    '/api/v1/auth/login',
    '/api/v1/auth/register',
    '/api/v1/auth/forgot-password',
    '/api/v1/auth/reset-password',
    '/api/v1/auth/refresh'
  ];
  
  const isPublicRoute = publicRoutes.some(route => urlString.includes(route));
  
  // Se for rota pública, usa fetch normal
  if (isPublicRoute) {
    return originalFetch(url, options);
  }
  
  // Para requisições autenticadas da nossa API, usa apiRequest
  // O apiRequest adiciona automaticamente o token e faz refresh se necessário
  return apiRequest(url, options);
};

