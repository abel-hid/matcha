'use client';

import { useEffect, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';

import { useAuth } from '@/app/context/AuthContext';
import { apiErrorMessage } from '@/app/lib/apiError';
import { signupSchema, type SignupFormData } from '@/app/lib/authValidation';

import AuthShowcase from './Authshowcase';

const inputClasses =
  'mt-1.5 w-full rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30';

const labelClasses = 'block text-xs font-medium uppercase tracking-wide text-[#9C8FA8]';


export default function SignupForm() {
  const { signup, user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!authLoading && user) {
      router.replace('/');
    }
  }, [authLoading, user, router]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
  });

  
  const onSubmit = async (data: SignupFormData) => {
    setError('');
    setLoading(true);

    try {
      await signup(data);
      setSuccess(true);
      setTimeout(() => router.push('/login'), 3000);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };
  if (authLoading || user) {
    return <div className="min-h-[calc(100vh-8rem)] bg-[#15101C]" />;
  }

  if (success) {
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center bg-[#15101C] px-6">
        <div className="w-full max-w-sm rounded-xl border border-[#332844] bg-[#1E1728] p-8 text-center">
          <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-[#FF4D7E]/15">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M5 13l4 4L19 7"
                stroke="#FF4D7E"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className="font-serif text-2xl text-[#F5EFE9]">You&apos;re in.</h2>
          <p className="mt-2 text-sm text-[#9C8FA8]">
            Check your email to verify your account.
          </p>
          <p className="mt-5 text-xs uppercase tracking-wide text-[#6E6180]">
            Redirecting to login…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] bg-[#15101C]">
      <AuthShowcase
        eyebrow="Join"
        headline="Where real conversations start."
        subhead="Create an account and find your people."
      />

      <div className="flex flex-1 items-center justify-center px-6 py-14">
        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h1 className="font-serif text-3xl text-[#F5EFE9]">Create account</h1>
            <p className="mt-2 text-sm text-[#9C8FA8]">Join the community.</p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label htmlFor="username" className={labelClasses}>Username</label>
              <input
                id="username"
                type="text"
                {...register('username')}
                className={inputClasses}
                placeholder="Choose a username"
              />
              {errors.username && (
                <p className="mt-1 text-sm text-[#FF8A80]">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="email" className={labelClasses}>Email</label>
              <input
                id="email"
                type="email"
                {...register('email')}
                className={inputClasses}
                placeholder="Enter your email"
              />
              {errors.email && (
                <p className="mt-1 text-sm text-[#FF8A80]">{errors.email.message}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="firstName" className={labelClasses}>First name</label>
                <input
                  id="firstName"
                  type="text"
                  {...register('firstName')}
                  className={inputClasses}
                  placeholder="John"
                />
                {errors.firstName && (
                  <p className="mt-1 text-sm text-[#FF8A80]">{errors.firstName.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="lastName" className={labelClasses}>Last name</label>
                <input
                  id="lastName"
                  type="text"
                  {...register('lastName')}
                  className={inputClasses}
                  placeholder="Doe"
                />
                {errors.lastName && (
                  <p className="mt-1 text-sm text-[#FF8A80]">{errors.lastName.message}</p>
                )}
              </div>
            </div>

            <div>
              <label htmlFor="password" className={labelClasses}>Password</label>
              <input
                id="password"
                type="password"
                {...register('password')}
                className={inputClasses}
                placeholder="Create a password"
              />
              {errors.password && (
                <p className="mt-1 text-sm text-[#FF8A80]">{errors.password.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="confirmPassword" className={labelClasses}>Confirm password</label>
              <input
                id="confirmPassword"
                type="password"
                {...register('confirmPassword')}
                className={inputClasses}
                placeholder="Confirm your password"
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-sm text-[#FF8A80]">{errors.confirmPassword.message}</p>
              )}
            </div>

            {error && (
              <div className="rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-[#FF4D7E] py-3 font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Creating account…' : 'Create account'}
            </button>

            <p className="text-center text-sm text-[#9C8FA8]">
              Already have an account?{' '}
              <Link href="/login" className="font-medium text-[#F2C879] hover:text-[#F5D998]">
                Sign in
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
