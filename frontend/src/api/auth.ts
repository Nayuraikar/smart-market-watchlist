import { apiClient } from './client';
import { UserOut, TokenOut } from '../types/auth';

export const authApi = {
  register: async (data: { email: string; password: string }): Promise<UserOut> => {
    const response = await apiClient.post<UserOut>('/auth/register', data);
    return response.data;
  },
  login: async (data: { email: string; password: string }): Promise<TokenOut> => {
    const response = await apiClient.post<TokenOut>('/auth/login', data);
    return response.data;
  },
  me: async (): Promise<UserOut> => {
    const response = await apiClient.get<UserOut>('/auth/me');
    return response.data;
  },
};
