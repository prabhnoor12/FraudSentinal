import { Component, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { api, getAccessToken } from './api';

@Component({
  selector: 'fs-web-layout',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="fs-app">
      <header class="fs-header">
        <div class="fs-container fs-header-inner">
          <a class="fs-brand" routerLink="/dashboard">FraudSentinal</a>

          <nav class="fs-nav">
            <a routerLink="/dashboard" routerLinkActive="is-active">Dashboard</a>
            <a routerLink="/review-cases" routerLinkActive="is-active">Review Cases</a>
            <a routerLink="/fraud-rules" routerLinkActive="is-active">Fraud Rules</a>
            <a routerLink="/usage" routerLinkActive="is-active">Usage</a>
            <a routerLink="/audit" routerLinkActive="is-active">Audit</a>
            <a routerLink="/billing" routerLinkActive="is-active">Billing</a>
            <a routerLink="/settings" routerLinkActive="is-active">Settings</a>
          </nav>

          <div class="fs-header-actions">
            @if (isAuthed()) {
              <button class="fs-button is-secondary" type="button" (click)="logout()">
                Sign out
              </button>
            } @else {
              <a class="fs-button is-secondary" routerLink="/login/sign-in">Sign in</a>
            }
          </div>
        </div>
      </header>

      <main class="fs-main">
        <div class="fs-container">
          <router-outlet />
        </div>
      </main>

      <footer class="fs-footer">
        <div class="fs-container fs-footer-inner">© {{ year() }} FraudSentinal</div>
      </footer>
    </div>
  `,
})
export class WebLayout {
  private readonly router: Router;

  protected readonly year = signal(new Date().getFullYear());
  protected readonly isAuthed = signal(Boolean(getAccessToken()));
  protected readonly isBusy = signal(false);

  constructor(router: Router) {
    this.router = router;
  }

  async logout(): Promise<void> {
    if (this.isBusy()) return;
    this.isBusy.set(true);
    try {
      await api.auth.logout();
      this.isAuthed.set(false);
      await this.router.navigate(['/login', 'sign-in']);
    } finally {
      this.isBusy.set(false);
    }
  }
}
