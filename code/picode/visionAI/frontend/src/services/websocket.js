const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const host = window.location.host;
const wsUrl = `${protocol}//${host}/ws`;

class WebSocketService {
  constructor() {
    this.socket = null;
    this.callbacks = [];
  }

  ensureConnected() {
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.socket = new WebSocket(wsUrl);
    this.socket.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return; // ignore non-JSON messages
      }
      const keys = Object.keys(data);
      for (const key of keys) {
        const callbacks = this.callbacks.filter((cb) => cb.message === key);
        callbacks.forEach((cb) => cb.callback(data[key]));
      }
    };
  }

  /**
   * Register a callback for a message key.
   * Calling onMessage with the same key replaces the existing callback for
   * that key, preventing duplicate registrations on remount.
   */
  onMessage(message, callback) {
    // Remove any existing registration for this key before adding
    this.callbacks = this.callbacks.filter((cb) => cb.message !== message);
    this.callbacks.push({ message, callback });
    this.ensureConnected();
  }

  offMessage(message) {
    this.callbacks = this.callbacks.filter((cb) => cb.message !== message);
  }

  close() {
    if (this.socket) this.socket.close();
    this.socket = null;
  }
}

const webSocketService = new WebSocketService();

export { webSocketService };
