// Actions
export const wsConnect = (url, channelKey) => ({ type: 'WS_CONNECT', payload: { url, channelKey } });
export const wsDisconnect = (channelKey) => ({ type: 'WS_DISCONNECT', payload: { channelKey } });
export const wsConnected = (channelKey) => ({ type: 'WS_CONNECTED', payload: { channelKey } });
export const wsDisconnected = (channelKey) => ({ type: 'WS_DISCONNECTED', payload: { channelKey } });
export const wsMessageReceived = (msg, channelKey) => ({ type: 'WS_MESSAGE_RECEIVED', payload: { msg, channelKey } });

const socketMiddleware = () => {
  // Map<channelKey, WebSocket>
  const sockets = new Map();

  return store => next => action => {
    switch (action.type) {
      case 'WS_CONNECT': {
        const { url, channelKey } = action.payload;
        
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
        };

        socket.onclose = () => {
          store.dispatch(wsDisconnected(channelKey));
          // Clean up map if it was this specific socket instance closing
          if (sockets.get(channelKey) === socket) {
              sockets.delete(channelKey);
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
