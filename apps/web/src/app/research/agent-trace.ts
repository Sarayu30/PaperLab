import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Run } from './research-api';

@Component({
  selector: 'paperlab-agent-trace',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (usage()?.agent_trace?.length) {
      <details [open]="live()">
        <summary>
          Agent actions · {{ usage()?.model_calls || 0 }} model calls ·
          {{ usage()?.tool_calls || 0 }} tool calls
        </summary>
        <p>Recorded actions and checks. Generated code has not been executed.</p>
        <ol aria-label="Agent action history">
          @for (event of usage()?.agent_trace; track event.sequence) {
            <li>
              <span>{{ event.sequence }}</span>
              <div>
                <strong>{{ event.agent }}</strong>
                <small>{{ event.kind.replaceAll('_', ' ') }}</small>
                <p>{{ event.detail }}</p>
              </div>
            </li>
          }
        </ol>
        @if (usage()?.incomplete_usage) {
          <p>Some provider usage is unknown; the conservative cost reservation is retained.</p>
        }
      </details>
    }
  `,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    details {
      margin: 16px 0;
      padding: 16px;
      border: 1px solid var(--line, #394434);
    }
    summary {
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
    }
    p,
    small {
      font-size: 12px;
      line-height: 1.6;
      overflow-wrap: anywhere;
    }
    p {
      margin: 6px 0 0;
    }
    ol {
      list-style: none;
      padding: 0;
      max-height: 300px;
      overflow: auto;
    }
    li {
      display: flex;
      gap: 12px;
      padding: 10px 0;
      border-top: 1px solid var(--line, #394434);
    }
    li > span {
      opacity: 0.6;
      font: 12px monospace;
      min-width: 20px;
    }
    li > div {
      min-width: 0;
    }
    strong,
    small {
      display: block;
    }
    strong {
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    small {
      opacity: 0.65;
    }
  `,
})
export class AgentTrace {
  readonly usage = input<Run['usage']>();
  readonly live = input(false);
}
