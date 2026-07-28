export interface User {
  id: number;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  birthDate?: string | null;
  age?: number | null;
  gender?: 'male' | 'female' | 'non-binary' | null;
  sexualPreferences?: ('male' | 'female' | 'non-binary')[];
  biography?: string;
  tags?: string[];
  profilePicture?: string;
  fameRating?: number;
  isOnline?: boolean;
  lastActivity?: string;
}

export interface AuthResponse {
  user: User;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface SignupCredentials {
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  password: string;
  confirmPassword: string;
}