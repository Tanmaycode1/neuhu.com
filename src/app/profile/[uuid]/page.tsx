import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import userApi from 'src/services/api';

const ProfilePage = () => {
    const router = useRouter();
    const { uuid } = router.query; // Get the UUID from the URL
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchProfile = async () => {
            setLoading(true);
            try {
                if (uuid) {
                    // Fetch other user's profile
                    const userProfile = await userApi.getUserProfile(uuid as string);
                    setProfile(userProfile);
                } else {
                    // Fetch logged-in user's profile
                    const myProfile = await userApi.getProfile();
                    setProfile(myProfile);
                }
            } catch (err) {
                setError(err);
            } finally {
                setLoading(false);
            }
        };

        fetchProfile();
    }, [uuid]);

    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error loading profile: {error.message}</div>;

    return (
        <div>
            <h1>{profile.username}'s Profile</h1>
            <p>Name: {profile.first_name} {profile.last_name}</p>
            <p>Email: {profile.email}</p>
            <p>Bio: {profile.bio}</p>
            {/* Add more profile fields as needed */}
            {/* Optionally, add an edit button for the logged-in user's profile */}
            {!uuid && <button onClick={() => router.push('/profile/edit')}>Edit Profile</button>}
        </div>
    );
};

export default ProfilePage; 