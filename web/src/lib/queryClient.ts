import { QueryClient } from '@tanstack/react-query';

// Auth and the application provider must share the same cache so logout clears it.
export const queryClient = new QueryClient();
