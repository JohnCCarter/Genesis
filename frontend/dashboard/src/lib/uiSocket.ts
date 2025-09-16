import { io, Socket } from 'socket.io-client';
import { ensureToken, getApiBase } from './api';

let socket: Socket | null = null;
let connecting = false;

export function getUiSocket(): Socket {
  if (socket) return socket;
  if (connecting) return socket as any;
  connecting = true;
  const base = getApiBase();
  // Attach token in query for backend auth
  let url = base;
  const tk = (typeof window !== 'undefined') ? (localStorage.getItem('jwt') || localStorage.getItem('genesis_access_token')) : '';
  if (tk) url = `${base}${base.includes('?') ? '&' : '?'}token=${encodeURIComponent(tk)}`;
  const s = io(url, {
    path: '/ws/socket.io',
    autoConnect: true,
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 500,
  });
  socket = s;
  s.on('disconnect', () => { /* keep singleton; reconnect handled by client */ });
  return s;
}

export async function ensureUiSocketConnected(): Promise<Socket> {
  await ensureToken(true);
  const s = getUiSocket();
  if (s.connected) return s;
  return await new Promise<Socket>((resolve) => {
    s.once('connect', () => resolve(s));
    // trigger connect if not
    try { s.connect(); } catch {}
    // fallback resolve after timeout to not block UI
    setTimeout(() => resolve(s), 2000);
  });
}


