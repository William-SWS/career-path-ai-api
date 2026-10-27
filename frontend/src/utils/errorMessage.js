// Lê o envelope de erro da API: { error: { status, code, message, details? } }.
// `details` (erros de validação por campo) tem prioridade sobre `message`.

export function extractErrorMessage(errorData, fallback) {
  const error = errorData?.error;

  if (Array.isArray(error?.details) && error.details.length > 0) {
    return error.details.map((detail) => detail.message).join(' ');
  }

  if (typeof error?.message === 'string' && error.message) {
    return error.message;
  }

  return fallback;
}

export async function readErrorMessage(response, fallback) {
  try {
    return extractErrorMessage(await response.json(), fallback);
  } catch {
    return fallback;
  }
}
