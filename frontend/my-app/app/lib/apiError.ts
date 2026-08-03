import axios from 'axios';

interface ApiErrorPayload {
  message?: unknown;
  reason?: unknown;
}

/** Extract the JSON error payload only when the failure came from Axios. */
function apiErrorPayload(error: unknown): ApiErrorPayload | null {
  if (!axios.isAxiosError(error) || !error.response?.data || typeof error.response.data !== 'object') {
    return null;
  }
  return error.response.data as ApiErrorPayload;
}

/** Return a safe API message without weakening catch variables to `any`. */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const message = apiErrorPayload(error)?.message;
  return typeof message === 'string' && message.trim() ? message : fallback;
}

/** Return a structured token/error reason when the backend supplied one. */
export function apiErrorReason(error: unknown): string | null {
  const reason = apiErrorPayload(error)?.reason;
  return typeof reason === 'string' && reason.trim() ? reason : null;
}

/** Return the HTTP status for branching while keeping unknown failures type-safe. */
export function apiErrorStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

/** Return a browser/library error code without assuming a concrete error class. */
export function errorCode(error: unknown): string | number | undefined {
  if (!error || typeof error !== 'object' || !('code' in error)) {
    return undefined;
  }
  const code = (error as { code?: unknown }).code;
  return typeof code === 'string' || typeof code === 'number' ? code : undefined;
}
