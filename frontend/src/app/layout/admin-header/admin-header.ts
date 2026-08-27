import {
  Component,
  EventEmitter,
  Output
} from '@angular/core';

import { RouterLink } from '@angular/router';

import { UserMenuComponent } from '../shared/user-menu/user-menu';


@Component({
  selector: 'app-admin-header',

  imports: [
    RouterLink,
    UserMenuComponent
  ],

  templateUrl: './admin-header.html',
  styleUrl: './admin-header.css'
})
export class AdminHeaderComponent {

  @Output()
  menuToggle = new EventEmitter<void>();


  toggleMenu(): void {
    this.menuToggle.emit();
  }
}