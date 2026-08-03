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

export interface TagOption {
  id: number;
  name: string;
}

export interface DiscoverProfile {
  id: number;
  username: string;
  firstName: string;
  lastName: string;
  age: number;
  gender: 'male' | 'female' | 'non-binary';
  profilePicture: string | null;
  fameRating: number;
  tags: string[];
  isOnline: boolean;
  lastActivity: string | null;
  location: {
    name: string;
  };
  distanceKm: number;
  commonTagCount: number;
}

export interface DiscoverFilters {
  minAge: number;
  maxAge: number;
  minFame: number;
  maxFame: number;
  location: string;
  tagIds: number[];
  sort: 'recommended' | 'age' | 'distance' | 'fame' | 'commonTags';
  order: 'asc' | 'desc';
}

export interface DiscoverResponse {
  profiles: DiscoverProfile[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
  criteria: DiscoverFilters;
}

export interface MapLocation {
  name: string;
  latitude: number;
  longitude: number;
}

export interface MapProfile extends Omit<DiscoverProfile, 'location'> {
  location: MapLocation;
}

export interface MapResponse {
  currentUserLocation: MapLocation;
  profiles: MapProfile[];
  total: number;
  truncated: boolean;
  criteria: DiscoverFilters;
}

export interface ChatUser {
  id: number;
  username: string;
  firstName: string;
  lastName: string;
  profilePicture: string | null;
  isOnline: boolean;
  lastActivity: string | null;
}

export interface ChatMessage {
  id: number;
  senderId: number;
  receiverId: number;
  content: string;
  isRead: boolean;
  createdAt: string;
}

export interface ConversationSummary {
  user: ChatUser;
  canMessage: boolean;
  unreadCount: number;
  lastMessage: ChatMessage | null;
}

export interface ConversationsResponse {
  conversations: ConversationSummary[];
  unreadCount: number;
}

export interface ConversationResponse {
  partner: ChatUser;
  canMessage: boolean;
  messages: ChatMessage[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}


export interface CallUser {
  id: number;
  username: string;
  firstName: string;
  lastName: string;
  profilePicture: string | null;
}

export type DateEventUser = CallUser;

export interface DateEvent {
  id: number;
  proposer: DateEventUser;
  recipient: DateEventUser;
  scheduledFor: string;
  location: string;
  note: string | null;
  status: 'pending' | 'accepted' | 'declined' | 'cancelled';
  createdAt: string;
  updatedAt: string;
}
