import userApi from 'src/services/api'; // Ensure the import path is correct

// Inside your component or function
const postsResponse = await userApi.getUserPosts(profileResponse.data.id); 