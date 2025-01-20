import React, { useEffect, useState } from 'react';
import userApi from 'src/services/api';
import { useRouter } from 'next/router';

const EditProfilePage = () => {
    const router = useRouter();
    const [profileData, setProfileData] = useState({
        first_name: '',
        last_name: '',
        bio: '',
        // Add other fields as necessary
    });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchProfile = async () => {
            setLoading(true);
            try {
                const myProfile = await userApi.getProfile();
                setProfileData(myProfile);
            } catch (err) {
                setError(err);
            } finally {
                setLoading(false);
            }
        };

        fetchProfile();
    }, []);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setProfileData((prev) => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await userApi.updateProfile(profileData);
            router.push(`/profile`); // Redirect to the profile page after saving
        } catch (err) {
            setError(err);
        }
    };

    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error loading profile: {error.message}</div>;

    return (
        <form onSubmit={handleSubmit}>
            <h1>Edit Profile</h1>
            <label>
                First Name:
                <input type="text" name="first_name" value={profileData.first_name} onChange={handleChange} />
            </label>
            <label>
                Last Name:
                <input type="text" name="last_name" value={profileData.last_name} onChange={handleChange} />
            </label>
            <label>
                Bio:
                <textarea name="bio" value={profileData.bio} onChange={handleChange} />
            </label>
            {/* Add more fields as necessary */}
            <button type="submit">Save Changes</button>
        </form>
    );
};

export default EditProfilePage; 