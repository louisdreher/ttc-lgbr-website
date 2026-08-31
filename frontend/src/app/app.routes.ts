import { Routes } from '@angular/router';

import { PublicLayoutComponent } from './layout/public-layout/public-layout';
import { InternLayoutComponent } from './layout/intern-layout/intern-layout';
import { AdminLayoutComponent } from './layout/admin-layout/admin-layout';

import { Home } from './pages/home/home';
import { News } from './pages/news/news';
import { Teams } from './pages/teams/teams';
import { Training } from './pages/training/training';
import { Contact } from './pages/contact/contact';

import { InternDashboard } from './intern/dashboard/dashboard';
import { InternArticles } from './intern/articles/articles';
import { InternTeams } from './intern/teams/teams';
import { InternEvents } from './intern/events/events';

import { AdminDashboard } from './admin/dashboard/dashboard';

import { AdminArticles } from './admin/articles/articles';
import { AdminArticleCreate } from './admin/articles/create/create';
import { AdminArticleDrafts } from './admin/articles/drafts/drafts';
import { AdminArticleList } from './admin/articles/list/list';
import { AdminNewsletter } from './admin/articles/newsletter/newsletter';

import { AdminTeams } from './admin/teams/teams';
import { AdminEvents } from './admin/events/events';
import { EventForm } from './admin/events/form/event-form';
import { AdminUsers } from './admin/users/users';

import { Login } from './auth/login/login';

import { authGuard, roleGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  // Öffentliche Website
  {
    path: '',
    component: PublicLayoutComponent,

    children: [
      {
        path: '',
        component: Home,
      },
      {
        path: 'news',
        component: News,
      },
      {
        path: 'mannschaften',
        component: Teams,
      },
      {
        path: 'training',
        component: Training,
      },
      {
        path: 'kontakt',
        component: Contact,
      },
      {
        path: 'termine',
        loadComponent: () => import('./pages/events/events').then((module) => module.PublicEvents),
      },
      {
        path: 'login',
        component: Login,
      },
    ],
  },

  // Interner Bereich
  {
    path: 'intern',
    component: InternLayoutComponent,
    canActivate: [authGuard],

    children: [
      {
        path: '',
        component: InternDashboard,
      },
      {
        path: 'articles',
        component: InternArticles,
        canActivate: [roleGuard('ADMIN', 'EDITOR')],
      },
      {
        path: 'teams',
        component: InternTeams,
      },
      {
        path: 'events',
        component: InternEvents,
      },
    ],
  },

  // Administration / CMS
  {
    path: 'admin',
    component: AdminLayoutComponent,

    canActivate: [authGuard, roleGuard('ADMIN', 'EDITOR', 'TEAM_REPORTER')],

    children: [
      {
        path: '',
        component: AdminDashboard,
      },
      {
        path: 'articles',
        component: AdminArticles,

        children: [
          {
            path: '',
            redirectTo: 'list',
            pathMatch: 'full',
          },
          {
            path: 'new',
            component: AdminArticleCreate,
          },
          {
            path: 'drafts',
            component: AdminArticleDrafts,
          },
          {
            path: 'list',
            component: AdminArticleList,
            canActivate: [roleGuard('ADMIN', 'EDITOR')],
          },
          {
            path: 'newsletter',
            component: AdminNewsletter,
            canActivate: [roleGuard('ADMIN', 'EDITOR')],
          },
        ],
      },
      {
        path: 'teams',
        component: AdminTeams,
        canActivate: [roleGuard('ADMIN', 'EDITOR')],
      },
      {
        path: 'events',
        component: AdminEvents,
        canActivate: [roleGuard('ADMIN', 'EDITOR')],
        children: [
          { path: 'new', component: EventForm },
          { path: ':id/edit', component: EventForm },
        ],
      },
      {
        path: 'users',
        component: AdminUsers,
        canActivate: [roleGuard('ADMIN')],
      },
    ],
  },
];
