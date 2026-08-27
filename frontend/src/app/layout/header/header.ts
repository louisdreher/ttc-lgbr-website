import { Component, HostListener } from '@angular/core';
import {
  RouterLink,
  RouterLinkActive
} from '@angular/router';

import { UserMenuComponent } from '../shared/user-menu/user-menu';


@Component({
  selector: 'app-header',
  imports: [
    RouterLink,
    RouterLinkActive,
    UserMenuComponent
  ],
  templateUrl: 'header.html',
  styleUrl: 'header.css'
})
export class HeaderComponent {

  isScrolled = false;

  mobileMenuOpen = false;
  openMobileDropdown: string | null = null;


  @HostListener('window:scroll')
  onWindowScroll(): void {

    const scrollPosition = window.scrollY;

    if (!this.isScrolled && scrollPosition > 100) {
      this.isScrolled = true;
    }

    if (this.isScrolled && scrollPosition < 10) {
      this.isScrolled = false;
    }
  }


  toggleMobileMenu(): void {

    this.mobileMenuOpen = !this.mobileMenuOpen;

    if (!this.mobileMenuOpen) {
      this.openMobileDropdown = null;
    }
  }


  toggleMobileDropdown(dropdown: string): void {

    if (this.openMobileDropdown === dropdown) {
      this.openMobileDropdown = null;
    } else {
      this.openMobileDropdown = dropdown;
    }
  }


  closeMobileMenu(): void {
    this.mobileMenuOpen = false;
    this.openMobileDropdown = null;
  }
}