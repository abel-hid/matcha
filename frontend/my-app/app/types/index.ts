export interface Photo {
  id: number;
  url: string;
  isPrimary: boolean;
  position: number;
}

export interface UserLocation {
  name: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface User {
  id: number;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  birthDate: string | null;
  age: number | null;
  gender: 'male' | 'female' | 'non-binary' | null;
  sexualPreferences: ('male' | 'female' | 'non-binary')[];
  biography: string | null;
  tags: string[];
  profilePicture: string | null;
  photos: Photo[];
  fameRating: number;
  isOnline: boolean;
  lastActivity: string | null;
  location: UserLocation | null;
  isProfileComplete: boolean;
  missingProfileFields: string[];
  isVerified?: boolean;
  gpsConsent?: boolean;
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
