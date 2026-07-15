'use client';

import { useAuth } from '@/app/context/AuthContext';

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h1 className="text-3xl font-bold text-gray-900">
          Welcome back, {user?.firstName || user?.username}! 👋
        </h1>
        <p className="mt-2 text-gray-600">
          This is your dashboard. Start finding your perfect match!
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900">Profile Views</h3>
          <p className="text-3xl font-bold text-blue-600 mt-2">0</p>
          <p className="text-sm text-gray-500 mt-1">People have viewed your profile</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900">Likes</h3>
          <p className="text-3xl font-bold text-red-600 mt-2">0</p>
          <p className="text-sm text-gray-500 mt-1">People who liked you</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900">Matches</h3>
          <p className="text-3xl font-bold text-green-600 mt-2">0</p>
          <p className="text-sm text-gray-500 mt-1">Mutual connections</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Complete Your Profile
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm font-medium text-gray-700">Personal Info</p>
            <p className="text-xs text-gray-500">Add your details</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm font-medium text-gray-700">Interests</p>
            <p className="text-xs text-gray-500">Add tags</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm font-medium text-gray-700">Location</p>
            <p className="text-xs text-gray-500">Set your location</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-sm font-medium text-gray-700">Photos</p>
            <p className="text-xs text-gray-500">Upload pictures</p>
          </div>
        </div>
      </div>
    </div>
  );
}