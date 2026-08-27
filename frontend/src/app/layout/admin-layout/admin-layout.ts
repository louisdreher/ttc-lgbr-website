import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AdminHeaderComponent } from '../admin-header/admin-header';
import { AdminSidebarComponent } from '../admin-sidebar/admin-sidebar';


@Component({
  selector: 'app-admin-layout',

  imports: [
    RouterOutlet,
    AdminHeaderComponent,
    AdminSidebarComponent
  ],

  templateUrl: './admin-layout.html',
  styleUrl: './admin-layout.css'
})
export class AdminLayoutComponent {

  sidebarOpen = false;


  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }


  closeSidebar(): void {
    this.sidebarOpen = false;
  }
}