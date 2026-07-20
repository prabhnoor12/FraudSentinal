import { Component, signal } from '@angular/core';
import { api, ApiError } from '../api';

type UsageEvent = {
  id?: number;
  event_type?: string;
  metadata?: unknown;
  created_at?: string;
};

@Component({
  selector: 'fs-usage-page',
  template: `
    <section class="fs-page">
      <div class="fs-page-header">
        <h1>Usage</h1>
        <p class="fs-muted">Track usage events and analytics.</p>
      </div>

      <div class="fs-card">
        <div class="fs-card-header">
          <h2>Recent Usage Events</h2>
        </div>

        @if (loading()) {
          <div class="fs-skeleton">Loading…</div>
        } @else if (error()) {
          <div class="fs-alert is-error">{{ error() }}</div>
        } @else if (events().length === 0) {
          <div class="fs-muted">No usage events found.</div>
        } @else {
          <ul class="fs-list">
            @for (e of events(); track e.id ?? e.created_at ?? $index) {
              <li class="fs-list-item">
                <div class="fs-list-main">
                  <div class="fs-list-title">{{ e.event_type ?? 'usage_event' }}</div>
                  <div class="fs-list-meta">{{ e.created_at ?? '' }}</div>
                </div>
              </li>
            }
          </ul>
        }
      </div>
    </section>
  `,
})
export class UsagePage {
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly events = signal<UsageEvent[]>([]);

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const data = (await api.usage.listEvents()) as UsageEvent[];
      this.events.set((data ?? []).slice(0, 50));
    } catch (e) {
      const err = e as ApiError;
      this.error.set(err?.message ?? 'Failed to load usage events.');
    } finally {
      this.loading.set(false);
    }
  }
}

