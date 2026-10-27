import { apiRequest } from '../utils/apiClient';
import { readErrorMessage } from '../utils/errorMessage';

const API_URL = 'http://localhost:8000';

export async function registerUser(email, name, password) {
  const response = await fetch(`${API_URL}/api/v1/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, name, password }),
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao cadastrar. Verifique os dados e tente novamente.');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json();
}

export async function loginUser(email, password) {
  const response = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Credenciais inválidas');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json();
}

export async function emailResetPassword(email) {
  const response = await fetch(`${API_URL}/api/v1/auth/forgot-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    throw new Error('email inválido');
  }

  return await response.json();
}

export async function resetPassword(token, password) {
  const response = await fetch(`${API_URL}/api/v1/auth/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      reset_token: token,
      new_password: password
    }),
  });

  if (!response.ok) {
    throw new Error('senha inválida');
  }

  return await response.json();
}

export async function uploadResume(file) {
  const token = localStorage.getItem('access_token');
  
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/api/v1/resume-analysis/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Erro ao fazer upload do currículo');
  }

  return await response.json();
}

export async function excludeUser(password) {
  const accessToken = localStorage.getItem('access_token');

  if (!accessToken) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/users/me/delete`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`,   
    },
    body: JSON.stringify({ password }),
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao excluir conta');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json(); 
}

export async function EditUserName(name) {
  const accessToken = localStorage.getItem('access_token');

  if (!accessToken) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/users/me`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`,   
    },
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao atualizar nome');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json(); 
}

export async function getDevelopmentTrails(skip = 0, limit = 100) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }
  
  const response = await fetch(`${API_URL}/api/v1/development-trail/?skip=${skip}&limit=${limit}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    // Se for 404, retorna lista vazia em vez de erro
    if (response.status === 404) {
      return { development_trails: [], total_count: 0 };
    }
    const errorMessage = await readErrorMessage(response, 'Erro ao buscar trilhas de desenvolvimento');

    throw new Error(errorMessage);
  }

  return await response.json();
}

export async function getDevelopmentTrailById(trailId) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/development-trail/${trailId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao buscar trilha de desenvolvimento');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json();
}

export async function getTotalDevelopmentTrail() {
  const token = localStorage.getItem('access_token');

  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/development-trail/?skip=0&limit=1`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    // Se for 404, retorna 0 (não há trilhas)
    if (response.status === 404) {
      return 0;
    }
    const errorMessage = await readErrorMessage(response, 'Erro ao buscar total de trilhas');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  const data = await response.json();

  return data.total_count || 0;
}

export async function getTotalAnalyzeResume() {
  const token = localStorage.getItem('access_token');

  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/resume-analysis/?skip=0&limit=1`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    // Se for 404, retorna 0 (não há análises)
    if (response.status === 404) {
      return 0;
    }
    const errorMessage = await readErrorMessage(response, 'Erro ao buscar total de currículos');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  const data = await response.json();

  return data.total_count || 0;
}

export async function getTotalInterviewGuide() {
  const token = localStorage.getItem('access_token');

  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/interview-guide/?skip=0&limit=1`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao buscar total de conversas');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  const data = await response.json();

  return data.total_count; // <<< retorna APENAS isso
}

export async function analyzeResume(file) {
  const token = localStorage.getItem('access_token');

  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  if (!file) {
    throw new Error('Nenhum arquivo enviado');
  }

  const formData = new FormData();
  formData.append('file', file);  // nome esperado pelo backend (alterar se necessário)

  const response = await fetch(`${API_URL}/api/v1/resume-analysis/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      // NÃO adicionar Content-Type aqui, o FormData define sozinho
    },
    body: formData,
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao enviar currículo para análise');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json(); // Deve retornar o ID da análise ou dados da análise
}

export async function analyzeInterviewGuide(job_description, file) {
  const token = localStorage.getItem('access_token');

  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  if (!file) {
    throw new Error('Nenhum arquivo enviado');
  }

  const formData = new FormData();
  formData.append('job_description', job_description);
  formData.append('file', file);

  const response = await fetch(`${API_URL}/api/v1/interview-guide/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      // NÃO adicionar Content-Type aqui, o FormData define sozinho
    },
    body: formData,
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao gerar guia de entrevista');

    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json();
}

// Funções para análise de currículo
export async function getResumeAnalysisById(analysisId) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/resume-analysis/${analysisId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Erro ao buscar análise de currículo');
  }

  return await response.json();
}

export async function getResumeAnalyses(skip = 0, limit = 100) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/resume-analysis/?skip=${skip}&limit=${limit}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    // Se for 404, retorna lista vazia em vez de erro
    if (response.status === 404) {
      return { analyses: [], total_count: 0 };
    }
    const errorMessage = await readErrorMessage(response, 'Erro ao buscar análises de currículo');

    throw new Error(errorMessage);
  }

  return await response.json();
}

export async function deleteResumeAnalysis(analysisId) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/resume-analysis/${analysisId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Erro ao deletar análise de currículo');
  }

  return await response.json();
}

// Funções para guia de entrevista
export async function getInterviewGuideById(guideId) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/interview-guide/${guideId}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Erro ao buscar guia de entrevista');
  }

  return await response.json();
}

export async function getInterviewGuides(skip = 0, limit = 100) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/interview-guide/?skip=${skip}&limit=${limit}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    // Se for 404, retorna lista vazia em vez de erro
    if (response.status === 404) {
      return { interview_guides: [], total_count: 0 };
    }
    const errorMessage = await readErrorMessage(response, 'Erro ao buscar guias de entrevista');

    throw new Error(errorMessage);
  }

  return await response.json();
}

export async function deleteInterviewGuide(guideId) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/interview-guide/${guideId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Erro ao deletar guia de entrevista');
  }

  return await response.json();
}

// Funções para trilha de desenvolvimento
export async function createDevelopmentTrail(trailData) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/development-trail/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(trailData),
  });

  if (!response.ok) {
    const errorMessage = await readErrorMessage(response, 'Erro ao criar trilha');
    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return await response.json();
}

export async function deleteDevelopmentTrail(trailId) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/development-trail/${trailId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Erro ao deletar trilha de desenvolvimento');
  }

  return await response.json();
}

// Funções para usuário
export async function getCurrentUser() {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  const response = await fetch(`${API_URL}/api/v1/users/me`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Erro ao buscar dados do usuário');
  }

  return await response.json();
}

export async function logout() {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Token de autenticação não encontrado');
  }

  // Envia também o refresh token para o backend revogar a sessão inteira
  const refreshToken = localStorage.getItem('refresh_token');

  const response = await fetch(`${API_URL}/api/v1/auth/logout`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    // Mesmo se falhar, faz logout local
    return { message: 'Logout realizado' };
  }

  return await response.json();
}
