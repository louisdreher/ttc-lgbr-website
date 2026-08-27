import { Component } from '@angular/core';
import { RouterOutlet, RouterLink } from '@angular/router';

@Component({
  selector: 'app-intern-layout',
  imports: [RouterOutlet, RouterLink],
  templateUrl: './intern-layout.html',
  styleUrl: './intern-layout.css',
})
export class InternLayoutComponent {}
