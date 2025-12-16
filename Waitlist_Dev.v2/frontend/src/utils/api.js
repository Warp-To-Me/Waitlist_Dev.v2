// centralized fetch wrapper to handle global errors (like 403)

export const apiCall = async (url, options = {}) => {
    // Default headers if not provided (e.g. CSRF or Content-Type)
    // For now we trust the caller to set specific headers if needed,
    // but we can add defaults here.

    const response = await fetch(url, options);

    if (response.status === 403) {
        // Redirect to access denied page
        // We use window.location because we are outside React context
        window.location.href = '/access_denied';

        // Return a rejected promise so the caller knows it failed
        // but the redirect happens immediately.
        throw new Error("Access Denied (403)");
    }

    return response;
};
