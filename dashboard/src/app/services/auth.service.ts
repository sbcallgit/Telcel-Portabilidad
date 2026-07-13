import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

const TOKEN_KEY = 'kpi_jwt';
const NOMBRE_KEY = 'kpi_nombre';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  nombre: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>('/api/auth/login', { email, password }).pipe(
      tap(res => {
        localStorage.setItem(TOKEN_KEY, res.access_token);
        localStorage.setItem(NOMBRE_KEY, res.nombre);
      })
    );
  }

  getToken(): string {
    return localStorage.getItem(TOKEN_KEY) ?? '';
  }

  getNombre(): string {
    return localStorage.getItem(NOMBRE_KEY) ?? '';
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(NOMBRE_KEY);
  }
}
