import { Injectable } from '@angular/core';

const TOKEN_KEY = 'kpi_admin_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  getToken(): string {
    return localStorage.getItem(TOKEN_KEY) ?? '';
  }

  setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
  }
}
