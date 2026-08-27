export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface CurrentUser {
  id: number;
  email: string;
  name: string;
  is_active: boolean;
  roles: string[];
}
