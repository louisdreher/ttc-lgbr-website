import {
  Component,
  EventEmitter,
  inject,
  Input,
  Output
} from '@angular/core';

import {
  Router,
  RouterLink
} from '@angular/router';

import { AuthService } from '../../../core/auth/auth.service';


@Component({
  selector: 'app-user-menu',
  imports: [
    RouterLink
  ],
  templateUrl: './user-menu.html',
  styleUrl: './user-menu.css'
})
export class UserMenuComponent {

  readonly authService = inject(AuthService);

  private readonly router = inject(Router);


  @Input()
  variant: 'desktop' | 'mobile' = 'desktop';


  @Input()
  context: 'public' | 'intern' | 'admin' = 'public';


  @Output()
  navigate = new EventEmitter<void>();


  menuOpen = false;


  toggleMenu(): void {
    this.menuOpen = !this.menuOpen;
  }


  closeMenu(): void {
    this.menuOpen = false;
  }


  onNavigate(): void {
    this.closeMenu();
    this.navigate.emit();
  }


  logout(): void {

    this.closeMenu();

    this.authService.logout().subscribe({
      next: () => {
        this.navigate.emit();

        void this.router.navigate(['/']);
      }
    });
  }
}