/**
 * SSE (Server-Sent Events) log stream utility.
 * Uses EventSource for real-time log streaming from the backend.
 */

export type LogHandler = (line: string) => void

let eventSource: EventSource | null = null

export function connectLogStream(onMessage: LogHandler, onError?: () => void): void {
  disconnectLogStream()

  eventSource = new EventSource('/api/logs')

  eventSource.onmessage = (event) => {
    if (event.data) {
      onMessage(event.data)
    }
  }

  eventSource.onerror = () => {
    if (onError) onError()
    // EventSource will auto-reconnect
  }
}

export function disconnectLogStream(): void {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}
