import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  token = '';
  error = '';
  loading = false;

  private auth = inject(AuthService);
  private router = inject(Router);
  private http = inject(HttpClient);

  login(): void {
    if (!this.token.trim()) return;
    this.loading = true;
    this.error = '';

    this.http
      .get('/api/admin/kpi-data?page=1&page_size=1', {
        headers: new HttpHeaders({ 'X-Admin-Token': this.token.trim() }),
      })
      .subscribe({
        next: () => {
          this.auth.setToken(this.token.trim());
          this.router.navigate(['/dashboard']);
        },
        error: () => {
          this.error = 'Token incorrecto. Verifica e intenta de nuevo.';
          this.loading = false;
        },
      });
  }
}
