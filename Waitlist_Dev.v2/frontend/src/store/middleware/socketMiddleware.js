// Actions
export const wsConnect = (url, key = 'default') => ({ type: 'WS_CONNECT', payload: { url, key } });
export const wsDisconnect = (key = 'default') => ({ type: 'WS_DISCONNECT', payload: { key } });
export const wsConnected = (key) => ({ type: 'WS_CONNECTED', payload: { key } });
export const wsDisconnected = (key) => ({ type: 'WS_DISCONNECTED', payload: { key } });
export const wsMessageReceived = (msg, key) => ({ type: 'WS_MESSAGE_RECEIVED', payload: { data: msg, key } });

const socketMiddleware = () => {
  const sockets = {};

  return store => next => action => {
    switch (action.type) {
      case 'WS_CONNECT':
        const { url, key } = action.payload;

        if (sockets[key]) {
          sockets[key].close();
        }

        // Determine protocol
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        // The payload is the path, e.g. '/ws/fleet/123/'
        // If the path already includes protocol, use it as is
        const fullUrl = url.startsWith('ws')
            ? url
            : `${protocol}${window.location.host}${url}`;

        const socket = new WebSocket(fullUrl);
        sockets[key] = socket;

        socket.onopen = () => {
          store.dispatch(wsConnected(key));
        };

        socket.onclose = () => {
          store.dispatch(wsDisconnected(key));
          delete sockets[key];
        };

        socket.onmessage = (event) => {
          try {
             const data = JSON.parse(event.data);
             store.dispatch(wsMessageReceived(data, key));
          } catch (e) {
             console.error("WS Parse Error", e);
          }
        };
        
        break;

      case 'WS_DISCONNECT':
        const disconnectKey = action.payload.key;
        if (sockets[disconnectKey]) {
          sockets[disconnectKey].close();
          delete sockets[disconnectKey];
        }
        break;

      default:
        return next(action);
    }
  };
};

export default socketMiddleware;
