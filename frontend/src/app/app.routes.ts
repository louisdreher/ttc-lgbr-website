import { Routes } from '@angular/router';

import { PublicLayoutComponent } from './layout/public-layout/public-layout';
import { InternLayoutComponent } from './layout/intern-layout/intern-layout';
import { AdminLayoutComponent } from './layout/admin-layout/admin-layout';

import { Home } from './pages/home/home';
import { Teams } from './pages/teams/teams';
import { Training } from './pages/training/training';
import { Contact } from './pages/contact/contact';

import { InternDashboard } from './intern/dashboard/dashboard';
import { InternTeams } from './intern/teams/teams';
import { InternEvents } from './intern/events/events';

import { AdminDashboard } from './admin/dashboard/dashboard';

import { articleLeaveGuard } from './admin/articles/editor/article-leave.guard';

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
        loadComponent: () => import('./pages/news/news').then((module) => module.News),
        title: 'Aktuelles | TTC',
      },
      {
        path: 'news/:slug',
        loadComponent: () =>
          import('./core/articles/article-detail').then((module) => module.ArticleDetail),
        title: 'Beitrag | TTC',
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
        loadComponent: () =>
          import('./intern/articles/articles').then((module) => module.InternArticles),
        title: 'Beiträge für Mitglieder | TTC',
      },
      {
        path: 'articles/:slug',
        loadComponent: () =>
          import('./core/articles/article-detail').then((module) => module.ArticleDetail),
        data: { members: true },
        title: 'Beitrag | TTC Intern',
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
        loadComponent: () =>
          import('./admin/articles/articles').then((module) => module.AdminArticles),

        children: [
          {
            path: '',
            redirectTo: 'drafts',
            pathMatch: 'full',
          },
          {
            path: 'new',
            loadComponent: () =>
              import('./admin/articles/create/create').then((module) => module.AdminArticleCreate),
            title: 'Neuer Beitrag | TTC',
          },
          {
            path: 'drafts',
            loadComponent: () =>
              import('./admin/articles/drafts/drafts').then((module) => module.AdminArticleDrafts),
            title: 'Meine Beiträge | TTC',
          },
          {
            path: 'list',
            loadComponent: () =>
              import('./admin/articles/list/list').then((module) => module.AdminArticleList),
            canActivate: [roleGuard('ADMIN', 'EDITOR')],
            title: 'Redaktion | TTC',
          },
          {
            path: 'write',
            loadComponent: () =>
              import('./admin/articles/editor/article-editor').then(
                (module) => module.ArticleEditor,
              ),
            canDeactivate: [articleLeaveGuard],
            title: 'Beitrag schreiben | TTC',
          },
          {
            path: 'event/:eventId',
            loadComponent: () =>
              import('./admin/articles/editor/article-editor').then(
                (module) => module.ArticleEditor,
              ),
            canDeactivate: [articleLeaveGuard],
            title: 'Bericht schreiben | TTC',
          },
          {
            path: ':id/edit',
            loadComponent: () =>
              import('./admin/articles/editor/article-editor').then(
                (module) => module.ArticleEditor,
              ),
            canDeactivate: [articleLeaveGuard],
            title: 'Beitrag | TTC Redaktion',
          },
          {
            path: 'newsletter',
            loadComponent: () =>
              import('./admin/articles/newsletter/newsletter').then(
                (module) => module.AdminNewsletter,
              ),
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
        path: 'mytt',
        loadComponent: () => import('./admin/mytt/mytt').then((module) => module.AdminMytt),
        canActivate: [roleGuard('ADMIN')],
      },
      {
        path: 'users',
        component: AdminUsers,
        canActivate: [roleGuard('ADMIN')],
      },
    ],
  },
];
