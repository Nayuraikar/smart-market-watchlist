export interface UserOut {
  id: string;
  email: string;
  created_at: string;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
}
