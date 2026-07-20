import { Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { api, ApiError } from '../api';

type RecentEvent = {
  id?: number;
  created_at?: string;
  event_type?: string;
  action?: string;
  resource_type?: string | null;
  resource_id?: string | null;
};

@Component({
  selector: 'fs-dashboard-page',
  imports: [RouterLink],
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Dashboard</h1>
        <p class="fs-muted">Overview of recent activity.</p>
      </div>

      <div class="fs-grid">
        <div class="fs-card">
          <div class="fs-card-header">
            <h2>Recent System Events</h2>
          </div>

          @if (loading()) {
            <div class="fs-skeleton">Loading…</div>
          } @else if (error()) {
            <div class="fs-alert is-error">{{ error() }}</div>
          } @else if (events().length === 0) {
            <div class="fs-muted">No recent events found.</div>
          } @else {
            <ul class="fs-list">
              @for (e of events(); track e.id ?? e.created_at ?? $index) {
                <li class="fs-list-item">
                  <div class="fs-list-main">
                    <div class="fs-list-title">
                      {{ e.event_type ?? 'event' }} · {{ e.action ?? 'action' }}
                    </div>
                    <div class="fs-list-meta">
                      {{ e.created_at ?? '' }}
                      @if (e.resource_type) {
                        · {{ e.resource_type }}
                      }
                      @if (e.resource_id) {
                        #{{ e.resource_id }}
                      }
                    </div>
                  </div>
                </li>
              }
            </ul>
          }
        </div>

        <div class="fs-card">
          <div class="fs-card-header">
            <h2>Quick Links</h2>
          </div>
          <div class="fs-stack">
            <a class="fs-link-card" routerLink="/usage">Usage analytics</a>
            <a class="fs-link-card" routerLink="/audit">Audit logs</a>
            <a class="fs-link-card" routerLink="/settings">Account settings</a>
          </div>
        </div>
      </div>
    </section>
  `,
})
export class DashboardPage {
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly events = signal<RecentEvent[]>([]);

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const logs = (await api.audit.list({ limit: 10, offset: 0 })) as RecentEvent[];
      this.events.set(logs ?? []);
    } catch (e) {
      const err = e as ApiError;
      if (err?.status === 403) {
        this.events.set([]);
        this.error.set('Audit events require admin access.');
      } else {
        this.error.set(err?.message ?? 'Failed to load recent events.');
      }
    } finally {
      this.loading.set(false);
    }
  }
}
