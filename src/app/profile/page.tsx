import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import userApi from '@/services/api';
import { Button } from '@/components/ui/button';
import { toast } from 'react-hot-toast';

const ProfilePage = () => {
    const router = useRouter();
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchProfile = async () => {
            setLoading(true);
            try {
                const myProfile = await userApi.getProfile();
                setProfile(myProfile);
            } catch (err) {
                setError(err);
                toast.error('Failed to load profile');
            } finally {
                setLoading(false);
            }
        };

        fetchProfile();
    }, []);

    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error loading profile: {error.message}</div>;

    return (
        <div className="max-w-2xl mx-auto p-4">
            <h1 className="text-2xl font-bold">{profile.username}'s Profile</h1>
            <div className="mt-4">
                <p><strong>Name:</strong> {profile.first_name} {profile.last_name}</p>
                <p><strong>Email:</strong> {profile.email}</p>
                <p><strong>Bio:</strong> {profile.bio}</p>
                {/* Add more profile fields as needed */}
            </div>
            <Button onClick={() => router.push('/profile/edit')} className="mt-4">
                Edit Profile
            </Button>
        </div>
    );
};

export default ProfilePage; 