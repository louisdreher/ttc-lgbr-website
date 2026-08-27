import {
  Component,
  DestroyRef,
  EventEmitter,
  inject,
  Input,
  Output
} from '@angular/core';

import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive
} from '@angular/router';

import { filter } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { AuthService } from '../../core/auth/auth.service';


@Component({
  selector: 'app-admin-sidebar',

  imports: [
    RouterLink,
    RouterLinkActive
  ],

  templateUrl: './admin-sidebar.html',
  styleUrl: './admin-sidebar.css'
})
export class AdminSidebarComponent {

  readonly authService = inject(AuthService);

  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);


  @Input()
  open = false;


  @Output()
  navigate = new EventEmitter<void>();


  articlesOpen = false;


  constructor() {

    this.updateOpenGroups(this.router.url);

    this.router.events
      .pipe(
        filter(
          (event): event is NavigationEnd =>
            event instanceof NavigationEnd
        ),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(event => {
        this.updateOpenGroups(event.urlAfterRedirects);
      });
  }


  toggleArticles(): void {
    this.articlesOpen = !this.articlesOpen;
  }


  onNavigate(): void {
    this.navigate.emit();
  }


  private updateOpenGroups(url: string): void {

    this.articlesOpen =
      url.startsWith('/admin/articles');
  }
}