"use client";

import { useRouter } from 'next/navigation';
import { 
  LogOut, 
  Search, 
  MessageSquare, 
  User, 
  PlusSquare, 
  Home,
  Mic,
  Newspaper,
  Moon,
  Sun
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'react-hot-toast';
import { useTheme } from '@/context/ThemeContext';
import { motion } from 'framer-motion';
import { PostCard } from '@/components/posts/PostCard';
import { Highlights } from '@/components/dashboard/Highlights';
import { authApi, ApiError } from '@/services/api';
import { CaughtUpAnimation } from '@/components/dashboard/CaughtUpAnimation';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import { userApi } from '@/services/api';

// Mock posts data
const mockPosts = [
  {
    id: 1,
    type: 'news',
    title: 'The Future of AI in Business',
    excerpt: 'Exploring how artificial intelligence is transforming modern business practices...',
    author: 'John Doe',
    timestamp: '2h ago',
    likes: 234,
    comments: [
      {
        id: '1',
        user: { name: 'Alice Johnson' },
        content: 'This is fascinating!',
        timestamp: '1h ago'
      },
      {
        id: '2',
        user: { name: 'Bob Smith' },
        content: 'Great insights!',
        timestamp: '30m ago'
      }
    ]
  },
  {
    id: 2,
    type: 'audio',
    title: 'Market Analysis: Q1 2024',
    duration: '15:30',
    author: 'Jane Smith',
    timestamp: '4h ago',
    likes: 156,
    comments: [
      {
        id: '1',
        user: { name: 'Mike Wilson' },
        content: 'Very informative!',
        timestamp: '2h ago'
      }
    ]
  },
  // Add more mock posts...
];

// Add these mock data at the top with existing mock data
const trendingTopics = [
  { id: 1, name: 'Business', postCount: 2453 },
  { id: 2, name: 'Technology', postCount: 1832 },
  { id: 3, name: 'Finance', postCount: 1654 },
  { id: 4, name: 'Startups', postCount: 1243 },
  { id: 5, name: 'AI & ML', postCount: 986 },
];

const suggestedAccounts = [
  {
    id: 1,
    name: 'Sarah Johnson',
    role: 'Tech Analyst',
    avatar: '/avatars/sarah.jpg', // You'll need to add these images
    followers: 12400
  },
  {
    id: 2,
    name: 'Michael Chen',
    role: 'Investment Strategist',
    avatar: '/avatars/michael.jpg',
    followers: 8900
  },
  {
    id: 3,
    name: 'Emma Davis',
    role: 'Business Journalist',
    avatar: '/avatars/emma.jpg',
    followers: 15600
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const [currentUser, setCurrentUser] = useState<{
    username: string;
    name: string;
    avatar?: string;
  } | null>(null);

  useEffect(() => {
    const loadUser = async () => {
      try {
        const response = await userApi.getProfile();
        setCurrentUser(response.data);
      } catch (error) {
        console.error('Error loading user profile:', error);
        toast.error('Failed to load user profile');
      }
    };

    loadUser();
  }, []);

  const handleLogout = async () => {
    try {
      // Try to logout from backend
      await authApi.logout();
      
      // If successful, clear storage and redirect
      localStorage.clear();
      toast.success('Logged out successfully');
      router.push('/');
    } catch (error: any) {
      console.error('Logout error:', error);
      
      // Always clear local storage
      localStorage.clear();
      
      if (error instanceof ApiError) {
        toast.error(error.userMessage);
      } else {
        toast.error('Error during logout, but you have been logged out locally');
      }
      
      // Redirect after a short delay to show the error message
      setTimeout(() => {
        router.push('/');
      }, 1500);
    }
  };

  const handleAvatarUpload = async (file: File) => {
    try {
        const response = await userApi.updateAvatar(file);
        setCurrentUser((prev) => ({
            ...prev,
            avatar: response.data.avatar_url, // Update the avatar in the state
        }));
        toast.success('Avatar updated successfully');
    } catch (error) {
        toast.error('Failed to update avatar');
    }
  };

  // Call this function when the user selects a new avatar
  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
        handleAvatarUpload(file); // Call the upload function
    }
  };

  // Update the navigation items in the sidebar
  const navigationItems = [
    { name: 'Home', href: '/dashboard', icon: Home },
    { name: 'Search', href: '/search', icon: Search },
    { name: 'Create Post', href: '/create-post', icon: PlusSquare },
    { name: 'Messages', href: '/messages', icon: MessageSquare },
    { name: 'Profile', href: '/profile', icon: User }, // Updated to point to /profile
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex">
      {/* Mobile Header - Visible on small screens */}
      <div className="lg:hidden fixed top-0 inset-x-0 h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 z-50">
        <div className="flex items-center justify-between px-4 h-full">
          <span className="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-primary-600 to-primary-500 dark:from-primary-400 dark:to-primary-300">
            Neuhu
          </span>
          {/* Mobile menu button */}
          <Button variant="ghost" size="icon" className="lg:hidden">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </Button>
        </div>
      </div>

      {/* Sidebar - Hidden on mobile, shown on desktop */}
      <div className="hidden lg:flex w-64 flex-col fixed inset-y-0">
        <div className="flex-1 flex flex-col min-h-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700">
          {/* Logo */}
          <div className="flex items-center h-16 flex-shrink-0 px-4 border-b border-gray-200 dark:border-gray-700">
            <span className="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-primary-600 to-primary-500 dark:from-primary-400 dark:to-primary-300">
              Neuhu
            </span>
          </div>

          {/* Sidebar content */}
          <div className="flex-1 flex flex-col pt-5 pb-4 overflow-y-auto">
            <nav className="flex-1 px-3 space-y-2">
              {navigationItems.map((item) => (
                <Link key={item.name} href={item.href}>
                  <Button 
                    variant="ghost" 
                    className="w-full justify-start text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50"
                  >
                    <item.icon className="mr-3 h-5 w-5" />
                    {item.name}
                  </Button>
                </Link>
              ))}
            </nav>

            {/* User Profile Section */}
            <div className="flex-shrink-0 flex border-t border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center w-full">
                <Link 
                  href="/profile" // Updated to point to /profile
                  className="flex items-center flex-1"
                >
                  <div className="flex-shrink-0">
                    <div className="h-10 w-10 rounded-full bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center">
                      {currentUser?.avatar ? (
                        <img 
                          src={currentUser.avatar}
                          alt={currentUser.name}
                          className="h-10 w-10 rounded-full object-cover"
                        />
                      ) : (
                        <User className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                      )}
                    </div>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
                      {currentUser?.name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      @{currentUser?.username}
                    </p>
                  </div>
                </Link>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleTheme}
                  >
                    {theme === 'dark' ? (
                      <Sun className="h-5 w-5" />
                    ) : (
                      <Moon className="h-5 w-5" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleLogout}
                  >
                    <LogOut className="h-5 w-5" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="lg:pl-64 flex flex-col flex-1">
        <main className="flex-1 pb-16 pt-16 lg:pt-0">
          <div className="px-4 sm:px-6 lg:px-8 py-4">
            <div className="max-w-6xl mx-auto">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Posts Feed */}
                <div className="lg:col-span-2 space-y-6">
                  {/* Stories/Highlights Section */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl p-4">
                    <Highlights />
                  </div>

                  {/* Latest For You Section */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                        Latest For You
                      </h2>
                      <Button variant="ghost" className="text-primary-600 dark:text-primary-400">
                        See all
                      </Button>
                    </div>
                    
                    {mockPosts.slice(0, 2).map((post) => (
                      <PostCard key={post.id} post={post} />
                    ))}
                  </div>

                  {/* Trending Posts Section */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                        Trending Posts
                      </h2>
                      <Button variant="ghost" className="text-primary-600 dark:text-primary-400">
                        See all
                      </Button>
                    </div>
                    
                    {mockPosts.slice(2).map((post) => (
                      <PostCard key={post.id} post={post} />
                    ))}
                  </div>

                  {/* Caught Up Animation */}
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center py-8 space-y-4"
                  >
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-100 dark:bg-primary-900/50">
                      <motion.div
                        animate={{ 
                          scale: [1, 1.2, 1],
                          rotate: [0, 360]
                        }}
                        transition={{ 
                          duration: 2,
                          repeat: Infinity,
                          repeatType: "reverse"
                        }}
                      >
                        <svg
                          className="w-8 h-8 text-primary-600 dark:text-primary-400"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      </motion.div>
                    </div>
                    <div className="space-y-2">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                        You're All Caught Up!
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        You've seen all new posts from the last 3 days
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      className="mt-4"
                    >
                      View older posts
                    </Button>
                  </motion.div>
                </div>

                {/* Right Sidebar */}
                <div className="space-y-6">
                  {/* Trending Topics */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                      <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Trending Topics
                      </h2>
                    </div>
                    <div className="p-4">
                      <div className="space-y-4">
                        {trendingTopics.map((topic) => (
                          <div 
                            key={topic.id}
                            className="flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 p-2 rounded-lg transition-colors duration-150"
                          >
                            <div className="flex items-center space-x-3">
                              <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center">
                                <span className="text-xs font-medium text-primary-600 dark:text-primary-400">
                                  #{topic.id}
                                </span>
                              </div>
                              <div>
                                <p className="font-medium text-gray-900 dark:text-white">
                                  {topic.name}
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                  {topic.postCount.toLocaleString()} posts
                                </p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Suggested Accounts */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                      <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Suggested Accounts
                      </h2>
                    </div>
                    <div className="p-4">
                      <div className="space-y-4">
                        {suggestedAccounts.map((account) => (
                          <div 
                            key={account.id}
                            className="flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 p-2 rounded-lg transition-colors duration-150"
                          >
                            <div className="flex items-center space-x-3">
                              <div className="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center">
                                <User className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                              </div>
                              <div>
                                <p className="font-medium text-gray-900 dark:text-white">
                                  {account.name}
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                  {account.role}
                                </p>
                              </div>
                            </div>
                            <Button 
                              variant="outline" 
                              size="sm"
                              className="text-primary-600 dark:text-primary-400 border-primary-200 dark:border-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/50"
                            >
                              Follow
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Quick Stats */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center">
                        <p className="text-2xl font-bold text-primary-600 dark:text-primary-400">
                          2.4K
                        </p>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          Active Users
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="text-2xl font-bold text-primary-600 dark:text-primary-400">
                          1.8K
                        </p>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          New Posts Today
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Mobile Navigation - Fixed at bottom */}
      <div className="lg:hidden fixed bottom-0 inset-x-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
        <nav className="flex justify-around p-3">
          <Link href="/dashboard">
            <Button variant="ghost" size="icon">
              <Home className="h-6 w-6" />
            </Button>
          </Link>
          <Link href="/search">
            <Button variant="ghost" size="icon">
              <Search className="h-6 w-6" />
            </Button>
          </Link>
          <Link href="/create-post">
            <Button variant="ghost" size="icon">
              <PlusSquare className="h-6 w-6" />
            </Button>
          </Link>
          <Link href="/messages">
            <Button variant="ghost" size="icon">
              <MessageSquare className="h-6 w-6" />
            </Button>
          </Link>
          <Link href="/profile">
            <Button variant="ghost" size="icon">
              <User className="h-6 w-6" />
            </Button>
          </Link>
        </nav>
      </div>

      {/* Add this to the mobile view section */}
      <div className="lg:hidden">
        <CaughtUpAnimation />
      </div>
    </div>
  );
} 