import { z } from 'zod';

const USERNAME_MIN_LENGTH = 3;
const USERNAME_MAX_LENGTH = 50;
const EMAIL_MAX_LENGTH = 100;
const NAME_MAX_LENGTH = 50;
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_BYTES = 72;

const namePattern = /^[\p{L}\p{M}]+(?:[ '\-][\p{L}\p{M}]+)*$/u;
const specialPattern = /[!@#$%^&*(),.?":{}|<>]/;

const passwordSchema = z
  .string()
  .min(PASSWORD_MIN_LENGTH, `Password must be at least ${PASSWORD_MIN_LENGTH} characters long`)
  .refine(
    (password) => new TextEncoder().encode(password).length <= PASSWORD_MAX_BYTES,
    `Password must be at most ${PASSWORD_MAX_BYTES} bytes long`
  )
  .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
  .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
  .regex(/\d/, 'Password must contain at least one number')
  .regex(specialPattern, 'Password must contain at least one special character');

export const signupSchema = z.object({
  username: z
    .string()
    .trim()
    .min(USERNAME_MIN_LENGTH, `Username must be at least ${USERNAME_MIN_LENGTH} characters long`)
    .max(USERNAME_MAX_LENGTH, `Username must be at most ${USERNAME_MAX_LENGTH} characters long`)
    .regex(/^[A-Za-z0-9_]+$/, 'Username may contain only letters, numbers, and underscores'),
  email: z
    .string()
    .trim()
    .max(EMAIL_MAX_LENGTH, `Email must be at most ${EMAIL_MAX_LENGTH} characters long`)
    .email('Invalid email address'),
  firstName: z
    .string()
    .trim()
    .min(1, 'First name is required')
    .max(NAME_MAX_LENGTH, `First name must be at most ${NAME_MAX_LENGTH} characters long`)
    .regex(namePattern, 'First name contains invalid characters'),
  lastName: z
    .string()
    .trim()
    .min(1, 'Last name is required')
    .max(NAME_MAX_LENGTH, `Last name must be at most ${NAME_MAX_LENGTH} characters long`)
    .regex(namePattern, 'Last name contains invalid characters'),
  password: passwordSchema,
  confirmPassword: z.string(),
}).superRefine((data, context) => {
  if (data.password !== data.confirmPassword) {
    context.addIssue({
      code: 'custom',
      message: "Passwords don't match",
      path: ['confirmPassword'],
    });
  }

  if (passwordUsesAccountDetails(data.password, [
    data.username,
    data.email,
    data.firstName,
    data.lastName,
  ])) {
    context.addIssue({
      code: 'custom',
      message: 'Password must not be based on your account details',
      path: ['password'],
    });
  }
});

export const resetPasswordSchema = z.object({
  password: passwordSchema,
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ['confirmPassword'],
});

export type SignupFormData = z.infer<typeof signupSchema>;
export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;

/** Normalize text before checking password similarity with account details. */
function normalizeWord(value: string): string {
  return value
    .normalize('NFKD')
    .toLocaleLowerCase()
    .replace(/\p{M}/gu, '')
    .replace(/[^\p{L}]/gu, '');
}

/** Return whether a password contains normalized username, name, or email fragments. */
function passwordUsesAccountDetails(password: string, accountValues: string[]): boolean {
  const normalizedPassword = normalizeWord(password);
  const commonAffixes = ['password', 'matcha', 'welcome', 'love', 'secure'];

  return accountValues.some((value) => {
    const normalizedValue = normalizeWord(value.split('@', 1)[0]);
    if (normalizedValue.length < 3) return false;
    if (normalizedPassword === normalizedValue) return true;

    return commonAffixes.some((affix) => (
      normalizedPassword === `${normalizedValue}${affix}` ||
      normalizedPassword === `${affix}${normalizedValue}`
    ));
  });
}
