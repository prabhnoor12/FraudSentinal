import { Routes } from '@angular/router';
import { authGuard } from '../web/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    children: [
      {
        path: 'sign-in',
        loadComponent: () => import('../web/login/sign-in.page').then((m) => m.SignInPage),
      },
      {
        path: 'sign-up',
        loadComponent: () => import('../web/login/sign-up.page').then((m) => m.SignUpPage),
      },
      { path: '', pathMatch: 'full', redirectTo: 'sign-in' },
    ],
  },
  {
    path: '',
    loadComponent: () => import('../web/web-layout').then((m) => m.WebLayout),
    children: [
      {
        path: 'dashboard',
        canActivate: [authGuard],
        loadComponent: () => import('../web/dashboard/dashboard.page').then((m) => m.DashboardPage),
      },
      {
        path: 'usage',
        canActivate: [authGuard],
        loadComponent: () => import('../web/usage/usage.page').then((m) => m.UsagePage),
      },
      {
        path: 'audit',
        canActivate: [authGuard],
        loadComponent: () => import('../web/audit/audit.page').then((m) => m.AuditPage),
      },
      {
        path: 'billing',
        canActivate: [authGuard],
        loadComponent: () => import('../web/billing/billing.page').then((m) => m.BillingPage),
      },
      {
        path: 'settings',
        canActivate: [authGuard],
        loadComponent: () => import('../web/settings/settings.page').then((m) => m.SettingsPage),
      },
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
