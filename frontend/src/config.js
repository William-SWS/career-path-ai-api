// URL base da API. Em desenvolvimento aponta para o backend local; em outro ambiente,
// defina VITE_API_URL (o Vite a embute no build, então ela não pode conter segredos).
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
