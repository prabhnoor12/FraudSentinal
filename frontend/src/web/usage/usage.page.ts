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
        <p class="fs-muted">Track usage events, activity volume, and recent analytics signals.</p>
      </div>

      <div class="fs-summary-grid">
        <div class="fs-summary-card">
          <span class="fs-summary-label">Visible events</span>
          <strong>{{ events().length }}</strong>
        </div>
        <div class="fs-summary-card">
          <span class="fs-summary-label">Unique event types</span>
          <strong>{{ uniqueEventTypeCount() }}</strong>
        </div>
        <div class="fs-summary-card">
          <span class="fs-summary-label">Latest activity</span>
          <strong>{{ latestEventLabel() }}</strong>
        </div>
      </div>

      <div class="fs-card">
        <div class="fs-card-header">
          <span class="fs-eyebrow">Event stream</span>
          <h2>Recent Usage Events</h2>
          <p class="fs-muted">A quick view of the latest tracked analytics and operational usage events.</p>
        </div>

        @if (loading()) {
          <div class="fs-skeleton">Loading...</div>
        } @else if (error()) {
          <div class="fs-alert is-error">{{ error() }}</div>
        } @else if (events().length === 0) {
          <div class="fs-empty-state">
            <strong>No usage events found</strong>
            <p class="fs-muted">Events will appear here once usage tracking data is available.</p>
          </div>
        } @else {
          <ul class="fs-list">
            @for (e of events(); track e.id ?? e.created_at ?? $index) {
              <li class="fs-list-item">
                <div class="fs-event-row">
                  <div class="fs-event-main">
                    <div class="fs-list-title">{{ e.event_type ?? 'usage_event' }}</div>
                    <div class="fs-list-meta">{{ e.created_at ?? 'Timestamp unavailable' }}</div>
                  </div>

                  <div class="fs-event-meta">
                    <div class="fs-event-stat">
                      <span class="fs-meta-label">Event ID</span>
                      <strong>{{ e.id ?? 'n/a' }}</strong>
                    </div>
                    <div class="fs-event-stat">
                      <span class="fs-meta-label">Metadata</span>
                      <strong>{{ metadataLabel(e.metadata) }}</strong>
                    </div>
                  </div>
                </div>
              </li>
            }
          </ul>
        }
      </div>
    </section>
  `,
  styleUrl: './usage.page.scss',
})
export class UsagePage {
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly events = signal<UsageEvent[]>([]);

  constructor() {
    void this.load();
  }

  protected uniqueEventTypeCount(): number {
    return new Set(this.events().map((event) => event.event_type ?? 'usage_event')).size;
  }

  protected latestEventLabel(): string {
    return this.events()[0]?.created_at ?? 'No data';
  }

  protected metadataLabel(metadata: unknown): string {
    if (!metadata) return 'none';
    if (typeof metadata === 'object') return 'structured payload';
    return String(metadata);
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
