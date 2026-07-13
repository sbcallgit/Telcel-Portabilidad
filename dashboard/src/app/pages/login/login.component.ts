import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  email = '';
  password = '';
  error = '';
  loading = false;

  private auth = inject(AuthService);
  private router = inject(Router);

  login(): void {
    if (!this.email.trim() || !this.password) return;
    this.loading = true;
    this.error = '';

    this.auth.login(this.email.trim(), this.password).subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: (err) => {
        this.error = err.status === 401
          ? 'Correo o contraseña incorrectos.'
          : 'Error de conexión. Intenta de nuevo.';
        this.loading = false;
      },
    });
  }
}
