import axios from 'axios';

interface ApiErrorPayload {
  message?: unknown;
  reason?: unknown;
}


function apiErrorPayload(error: unknown): ApiErrorPayload | null {
  if (!axios.isAxiosError(error) || !error.response?.data || typeof error.response.data !== 'object') {
    return null;
  }
  return error.response.data as ApiErrorPayload;
}


export function apiErrorMessage(error: unknown, fallback: string): string {
  const message = apiErrorPayload(error)?.message;
  return typeof message === 'string' && message.trim() ? message : fallback;
}


export function apiErrorReason(error: unknown): string | null {
  const reason = apiErrorPayload(error)?.reason;
  return typeof reason === 'string' && reason.trim() ? reason : null;
}


export function apiErrorStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}


export function errorCode(error: unknown): string | number | undefined {
  if (!error || typeof error !== 'object' || !('code' in error)) {
    return undefined;
  }
  const code = (error as { code?: unknown }).code;
  return typeof code === 'string' || typeof code === 'number' ? code : undefined;
}
