// Actions
export const wsConnect = (url) => ({ type: 'WS_CONNECT', payload: url });
export const wsDisconnect = () => ({ type: 'WS_DISCONNECT' });
export const wsConnected = () => ({ type: 'WS_CONNECTED' });
export const wsDisconnected = () => ({ type: 'WS_DISCONNECTED' });
export const wsMessageReceived = (msg) => ({ type: 'WS_MESSAGE_RECEIVED', payload: msg });

const socketMiddleware = () => {
  let socket = null;

  return store => next => action => {
    switch (action.type) {
      case 'WS_CONNECT':
        if (socket !== null) {
          socket.close();
        }

        // Determine protocol
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        // The payload is the path, e.g. '/ws/fleet/123/'
        // If the path already includes protocol, use it as is
        const url = action.payload.startsWith('ws') 
            ? action.payload 
            : `${protocol}${window.location.host}${action.payload}`;

        socket = new WebSocket(url);

        socket.onopen = () => {
          store.dispatch(wsConnected());
        };

        socket.onclose = () => {
          store.dispatch(wsDisconnected());
        };

        socket.onmessage = (event) => {
          try {
             const data = JSON.parse(event.data);
             store.dispatch(wsMessageReceived(data));
          } catch (e) {
             console.error("WS Parse Error", e);
          }
        };
        
        break;

      case 'WS_DISCONNECT':
        if (socket !== null) {
          socket.close();
        }
        socket = null;
        break;

      default:
        return next(action);
    }
  };
};

export default socketMiddleware;
