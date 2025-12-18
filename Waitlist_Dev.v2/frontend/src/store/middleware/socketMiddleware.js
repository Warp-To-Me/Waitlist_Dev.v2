// Actions
export const wsConnect = (url, channelKey) => ({ type: 'WS_CONNECT', payload: { url, channelKey } });
export const wsDisconnect = (channelKey) => ({ type: 'WS_DISCONNECT', payload: { channelKey } });
export const wsConnected = (channelKey) => ({ type: 'WS_CONNECTED', payload: { channelKey } });
export const wsDisconnected = (channelKey) => ({ type: 'WS_DISCONNECTED', payload: { channelKey } });
export const wsMessageReceived = (msg, channelKey) => ({ type: 'WS_MESSAGE_RECEIVED', payload: { msg, channelKey } });

const socketMiddleware = () => {
  // Map<channelKey, WebSocket>
  const sockets = new Map();
  // Map<channelKey, Boolean> - True if disconnect was requested by app
  const forcedClose = new Map();
  // Map<channelKey, Number> - Retry count for backoff
  const retryCounts = new Map();
  // Map<channelKey, TimeoutID> - Pending reconnect timers
  const reconnectTimers = new Map();

  return store => next => action => {
    switch (action.type) {
      case 'WS_CONNECT': {
        const { url, channelKey } = action.payload;
        
        // Clear any pending reconnects
        if (reconnectTimers.has(channelKey)) {
            clearTimeout(reconnectTimers.get(channelKey));
            reconnectTimers.delete(channelKey);
        }
        
        forcedClose.set(channelKey, false);

        if (sockets.has(channelKey)) {
          sockets.get(channelKey).close();
          sockets.delete(channelKey);
        }

        // Determine protocol
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        // The payload is the path, e.g. '/ws/fleet/123/'
        // If the path already includes protocol, use it as is
        const fullUrl = url.startsWith('ws') 
            ? url 
            : `${protocol}${window.location.host}${url}`;

        const socket = new WebSocket(fullUrl);
        sockets.set(channelKey, socket);

        socket.onopen = () => {
          store.dispatch(wsConnected(channelKey));
          // Reset retry count on successful connection
          retryCounts.set(channelKey, 0);
        };

        socket.onclose = () => {
          store.dispatch(wsDisconnected(channelKey));
          
          // Clean up map if it was this specific socket instance closing
          if (sockets.get(channelKey) === socket) {
              sockets.delete(channelKey);
          }

          // Automatic Reconnection Logic
          if (!forcedClose.get(channelKey)) {
              const retries = retryCounts.get(channelKey) || 0;
              // Exponential Backoff: 1s, 2s, 4s, 8s, 16s... capped at 30s
              const delay = Math.min(1000 * Math.pow(2, retries), 30000);
              
              console.log(`[WS] ${channelKey} disconnected unexpectedly. Reconnecting in ${delay}ms... (Attempt ${retries + 1})`);
              
              const timerId = setTimeout(() => {
                  retryCounts.set(channelKey, retries + 1);
                  store.dispatch(wsConnect(url, channelKey));
              }, delay);

              reconnectTimers.set(channelKey, timerId);
          }
        };

        socket.onmessage = (event) => {
          try {
             const data = JSON.parse(event.data);
             store.dispatch(wsMessageReceived(data, channelKey));
          } catch (e) {
             console.error("WS Parse Error", e);
          }
        };
        
        break;
      }

      case 'WS_DISCONNECT': {
        const { channelKey } = action.payload;
        
        // Mark as intentional disconnect
        forcedClose.set(channelKey, true);
        
        // Clear any pending reconnects
        if (reconnectTimers.has(channelKey)) {
            clearTimeout(reconnectTimers.get(channelKey));
            reconnectTimers.delete(channelKey);
        }

        if (sockets.has(channelKey)) {
          sockets.get(channelKey).close();
          sockets.delete(channelKey);
        }
        break;
      }

      default:
        return next(action);
    }
  };
};

export default socketMiddleware;
